"""CapelHouse — preparación musical por género, estrellas y color."""
import argparse
import json
import logging
import math
import os
import subprocess
import sys
from pathlib import Path

from mutagen import File as audio_metadata
from PySide6.QtCore import QEvent, QPointF, QSignalBlocker, QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFontDatabase, QIcon, QKeyEvent, QPainter, QPolygonF, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView, QSizePolicy, QDialog,
)

from library import Library, COLORS
from rekordbox_export import export_library, publish_library
from rekordbox_bridge import default_bridge_dir, inspect_connection, configure_connection, inspect_tracks
from rekordbox_sync import apply_classification
from tasks import Task

BASE = Path(__file__).resolve().parent
VERSION = "2.1.0"
RB_STATES = {
    "pending": "No importada", "not_imported": "No importada", "imported": "Pendiente de análisis",
    "analyzing": "Analizando", "ready": "Lista", "metadata_mismatch": "Revisar clasificación",
    "missing": "Archivo no localizado", "unverifiable": "Sin verificar",
}


def config_location():
    user_config = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CapelHouse" / "configuracion_dj.json"
    if getattr(sys, "frozen", False) or user_config.with_name("library.json").exists():
        return user_config
    return BASE / "configuracion_dj.json"


def clock(milliseconds):
    seconds = max(0, int(milliseconds // 1000))
    return f"{seconds // 60}:{seconds % 60:02}"


def star_icon(filled):
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#e6b84a"))
    painter.setBrush(QColor("#e6b84a") if filled else Qt.NoBrush)
    points = [QPointF(14 + (12 if i % 2 == 0 else 5) * math.sin(i * math.pi / 5),
                      14 - (12 if i % 2 == 0 else 5) * math.cos(i * math.pi / 5)) for i in range(10)]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return QIcon(pixmap)


class App(QMainWindow):
    def __init__(self, config_path=None):
        super().__init__()
        self.library = Library(Path(config_path) if config_path else config_location())
        self.current = None
        self.current_record = None
        self.current_rating = 0
        self.drafts = {}
        self.pending = []
        self.busy = False
        self.job = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.last_export = None
        self.rb_states = {}
        self.connection_dialog = None
        self.rb_timer = QTimer(self)
        self.rb_timer.setInterval(12000)
        self.rb_timer.timeout.connect(self.refresh_rekordbox_status)
        self.theme_changed = False
        self.dark = self.library.config.get("dark_mode", True)
        self.ui_font = "Segoe UI"
        regular_font = BASE / "Barlow_Condensed,Mr_Dafoe" / "Barlow_Condensed" / "BarlowCondensed-Regular.ttf"
        font_id = QFontDatabase.addApplicationFont(str(regular_font))
        if font_id >= 0:
            self.ui_font = QFontDatabase.applicationFontFamilies(font_id)[0]
        self.setWindowTitle(f"CapelHouse {VERSION} · Prepara tu música")
        self.resize(1360, 850)
        self.setMinimumSize(1000, 680)
        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.errorOccurred.connect(self.playback_error)
        self.build_ui()
        self.apply_theme()
        self.refresh_paths()
        self.render_prepared()
        QApplication.instance().installEventFilter(self)
        QTimer.singleShot(0, self.refresh_pending)

    def build_ui(self):
        file_menu = self.menuBar().addMenu("Biblioteca")
        open_config = QAction("Abrir biblioteca guardada…", self)
        open_config.triggered.connect(self.open_library_config)
        file_menu.addAction(open_config)
        file_menu.addAction("Ver carpeta de configuración", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.config_path.parent))))
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        logo = QLabel()
        pixmap = QPixmap(str(BASE / "logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.setWindowIcon(QIcon(pixmap))
        header.addWidget(logo)
        names = QVBoxLayout()
        brand = QLabel("CapelHouse")
        brand.setObjectName("brand")
        font = BASE / "Mr_Dafoe" / "MrDafoe-Regular.ttf"
        if font.exists():
            font_id = QFontDatabase.addApplicationFont(str(font))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                brand.setStyleSheet(f"font-family: '{families[0]}'; font-size:38px;")
        names.addWidget(brand)
        names.addWidget(QLabel("By Capelgeuse · Tu selección empieza escuchando"))
        header.addLayout(names, 1)
        theme = QPushButton("Cambiar tema")
        theme.clicked.connect(self.toggle_theme)
        header.addWidget(theme)
        archive_button = QPushButton("Exportar respaldo")
        archive_button.clicked.connect(self.export)
        header.addWidget(archive_button)
        self.export_button = QPushButton("Enviar a Rekordbox")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self.send_to_rekordbox)
        header.addWidget(self.export_button)
        layout.addLayout(header)
        self.path_box = QGroupBox("Tu biblioteca")
        locations = QHBoxLayout(self.path_box)
        entry = QPushButton("Elegir entrada")
        entry.clicked.connect(self.choose_input)
        locations.addWidget(entry)
        self.input_label = QLabel()
        locations.addWidget(self.input_label, 1)
        dest = QPushButton("Elegir destino")
        dest.clicked.connect(self.choose_library)
        locations.addWidget(dest)
        self.library_label = QLabel()
        locations.addWidget(self.library_label, 1)
        layout.addWidget(self.path_box)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.tabs = QTabWidget()
        pending_tab = QWidget()
        pl = QVBoxLayout(pending_tab)
        self.pending_search = QLineEdit()
        self.pending_search.setPlaceholderText("Buscar entre las nuevas canciones…")
        self.pending_search.textChanged.connect(self.filter_pending)
        pl.addWidget(self.pending_search)
        self.pending_table = self.make_table(["Canción", "Carpeta"])
        self.pending_table.itemSelectionChanged.connect(self.select_pending)
        pl.addWidget(self.pending_table, 1)
        pending_actions = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.refresh_pending)
        pending_actions.addWidget(refresh)
        skip = QPushButton("Omitir")
        skip.clicked.connect(self.skip_current)
        pending_actions.addWidget(skip)
        restore = QPushButton("Recuperar omitidas")
        restore.clicked.connect(self.restore_skipped)
        pending_actions.addWidget(restore)
        pl.addLayout(pending_actions)
        self.tabs.addTab(pending_tab, "Por escuchar")

        prepared_tab = QWidget()
        rl = QVBoxLayout(prepared_tab)
        self.prepared_search = QLineEdit()
        self.prepared_search.setPlaceholderText("Buscar canción o artista…")
        self.prepared_search.textChanged.connect(self.render_prepared)
        rl.addWidget(self.prepared_search)
        filters = QHBoxLayout()
        self.genre_filter = QComboBox()
        self.color_filter = QComboBox()
        self.rating_filter = QComboBox()
        self.color_filter.addItems(["Todos los colores", *COLORS])
        self.rating_filter.addItems(["Todas las estrellas", "Sin estrellas", "1 ★", "2 ★", "3 ★", "4 ★", "5 ★"])
        for widget in (self.genre_filter, self.color_filter, self.rating_filter):
            widget.currentIndexChanged.connect(self.render_prepared)
            filters.addWidget(widget)
        rl.addLayout(filters)
        self.prepared_table = self.make_table(["Canción", "Género", "Estrellas", "Color", "Rekordbox"])
        self.prepared_table.itemSelectionChanged.connect(self.select_prepared)
        rl.addWidget(self.prepared_table, 1)
        self.export_filtered = QCheckBox("Exportar solo las canciones visibles con estos filtros")
        self.export_filtered.setChecked(True)
        rl.addWidget(self.export_filtered)
        self.check_rb_button = QPushButton("Comprobar estado en Rekordbox")
        self.check_rb_button.clicked.connect(self.refresh_rekordbox_status)
        rl.addWidget(self.check_rb_button)
        self.tabs.addTab(prepared_tab, "Preparadas")
        self.tabs.currentChanged.connect(self.tab_changed)
        split.addWidget(self.tabs)

        self.inspector = QGroupBox("Escucha y decide")
        self.inspector.setMinimumWidth(350)
        il = QVBoxLayout(self.inspector)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(6, 6, 6, 6)
        pv.setSpacing(6)
        track_heading = QHBoxLayout()
        self.cover = QLabel("CH")
        self.cover.setObjectName("cover")
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setFixedSize(52, 52)
        track_heading.addWidget(self.cover)
        track_labels = QVBoxLayout()
        self.song = QLabel("Elige una canción para empezar")
        self.song.setObjectName("song")
        self.song.setWordWrap(True)
        self.song.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        track_labels.addWidget(self.song)
        self.artist = QLabel("Género + estrellas + color, a tu manera")
        self.artist.setWordWrap(True)
        self.artist.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        track_labels.addWidget(self.artist)
        track_heading.addLayout(track_labels, 1)
        pv.addLayout(track_heading)
        self.play_button = QPushButton("Reproducir")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self.toggle_playback)
        pv.addWidget(self.play_button)
        transport = QHBoxLayout()
        for text, delta in (("−5 s", -5000), ("+5 s", 5000)):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, d=delta: self.seek(d))
            transport.addWidget(button)
        self.time_label = QLabel("0:00 / 0:00")
        transport.addWidget(self.time_label)
        pv.addLayout(transport)
        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.sliderMoved.connect(self.player.setPosition)
        pv.addWidget(self.progress)
        volume = QHBoxLayout()
        volume.addWidget(QLabel("Volumen"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(75)
        self.audio.setVolume(.75)
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
        volume.addWidget(self.volume)
        pv.addLayout(volume)
        genre_row = QHBoxLayout()
        genre_row.addWidget(QLabel("Género"))
        self.genre_combo = QComboBox()
        self.genre_combo.addItems(self.library.genres)
        genre_row.addWidget(self.genre_combo, 1)
        edit = QPushButton("Editar")
        edit.clicked.connect(self.edit_genres)
        genre_row.addWidget(edit)
        pv.addLayout(genre_row)
        pv.addWidget(QLabel("Estrellas"))
        stars = QHBoxLayout()
        self.star_buttons = []
        for number in range(1, 6):
            button = QPushButton()
            button.setObjectName("star")
            button.setIcon(star_icon(False))
            button.setAccessibleName(f"{number} estrellas")
            button.setToolTip(f"{number} estrellas · tecla {number}")
            button.clicked.connect(lambda checked=False, n=number: self.set_rating(n))
            self.star_buttons.append(button)
            stars.addWidget(button)
        clear = QPushButton("Limpiar")
        clear.clicked.connect(lambda: self.set_rating(0))
        stars.addWidget(clear)
        pv.addLayout(stars)
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color"))
        self.color_combo = QComboBox()
        for name, rgb in COLORS.items():
            icon = QPixmap(16, 16)
            icon.fill(QColor(*rgb) if rgb else QColor("#777777"))
            self.color_combo.addItem(QIcon(icon), name)
        color_row.addWidget(self.color_combo, 1)
        pv.addLayout(color_row)
        self.preview = QLabel("Destino: elige una biblioteca y un género")
        self.preview.setWordWrap(True)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        pv.addWidget(self.preview)
        self.save_button = QPushButton("Guardar y siguiente")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.classify)
        self.autoplay = QCheckBox("Reproducir la siguiente automáticamente")
        self.autoplay.setChecked(True)
        pv.addStretch(1)
        scroll.setWidget(panel)
        il.addWidget(scroll)
        il.addWidget(self.save_button)
        il.addWidget(self.autoplay)
        split.addWidget(self.inspector)
        split.setSizes([800, 430])
        layout.addWidget(split, 1)
        self.status = QLabel("Selecciona tu carpeta de entrada y el destino de la biblioteca.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        shortcuts = QLabel("Espacio: reproducir/pausar   ·   1–5: estrellas   ·   0: limpiar   ·   Enter: guardar   ·   Izq / Der: 5 s")
        shortcuts.setObjectName("muted")
        shortcuts.setWordWrap(True)
        layout.addWidget(shortcuts)
        self.genre_combo.currentTextChanged.connect(self.update_preview)
        self.sync_genre_filter()

    def make_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return table

    def apply_theme(self):
        bg, panel, text, muted, edge, row = (("#111315", "#1b1f23", "#f4f1eb", "#a7adb5", "#343b44", "#22272d") if self.dark else ("#f2f1ec", "#ffffff", "#172027", "#62707a", "#d4d9de", "#f6f7f9"))
        self.setStyleSheet(f"""
        QMainWindow, QTabWidget::pane {{ background:{bg}; }}
        QWidget {{ color:{text}; font-family:'{self.ui_font}'; font-size:15px; }}
        QWidget#qt_tabwidget_stackedwidget {{ background:{bg}; }}
        QLabel#brand {{ font-size:30px; font-weight:600; }}
        QLabel#song {{ font-size:19px; font-weight:600; }}
        QLabel#muted {{ color:{muted}; }}
        QGroupBox {{ background:{panel}; border:1px solid {edge}; border-radius:10px; margin-top:10px; padding:12px; font-weight:600; }}
        QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 4px; }}
        QScrollArea {{ border:0; background:{panel}; }} QScrollArea > QWidget > QWidget {{ background:{panel}; }}
        QPushButton {{ background:{panel}; border:1px solid {edge}; border-radius:7px; padding:8px 12px; min-height:18px; }}
        QPushButton:hover {{ border-color:#e6b84a; }} QPushButton:disabled {{ color:{muted}; }}
        QPushButton#primary {{ background:#e6b84a; color:#172027; font-weight:700; }}
        QPushButton#star {{ color:#e6b84a; font-size:24px; padding:3px; }}
        QLineEdit, QComboBox {{ background:{panel}; border:1px solid {edge}; border-radius:6px; padding:6px; min-height:20px; }}
        QComboBox QAbstractItemView {{ background:{panel}; color:{text}; selection-background-color:#806b36; }}
        QTableWidget {{ background:{panel}; alternate-background-color:{row}; border:0; gridline-color:{edge}; selection-background-color:#66572f; selection-color:#ffffff; }}
        QHeaderView::section {{ background:{row}; color:{muted}; border:0; padding:9px 6px; }}
        QTableWidget::item {{ padding:6px; }}
        QCheckBox {{ spacing:6px; background:transparent; }}
        QTabBar::tab {{ background:{panel}; padding:10px 16px; border-bottom:2px solid {edge}; }}
        QTabBar::tab:selected {{ border-bottom-color:#e6b84a; }}
        QLabel#cover {{ background:{row}; color:#e6b84a; border-radius:10px; font-size:24px; }}
        QSlider::groove:horizontal {{ background:{edge}; height:5px; }} QSlider::handle:horizontal {{ background:#e6b84a; width:13px; margin:-5px 0; border-radius:6px; }}
        QMessageBox {{ background:{panel}; }} QInputDialog {{ background:{panel}; }}
        """)

    def toggle_theme(self):
        self.dark = not self.dark
        self.theme_changed = True
        self.library.config["dark_mode"] = self.dark
        self.apply_theme()

    def open_library_config(self):
        if self.busy:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Abrir biblioteca de CapelHouse", "", "Configuración (*.json)")
        if filename:
            try:
                loaded = Library(Path(filename))
                self.clear_current()
                self.library = loaded
                self.rb_states.clear()
                self.dark = loaded.config.get("dark_mode", self.dark)
                self.apply_theme()
                self.drafts.clear()
                self.genre_combo.clear()
                self.genre_combo.addItems(loaded.genres)
                self.sync_genre_filter()
                self.refresh_paths()
                self.render_prepared()
                self.refresh_pending()
            except Exception as error:
                self.show_error(str(error))

    def refresh_paths(self):
        for label, path in ((self.input_label, self.library.input_path), (self.library_label, self.library.library_path)):
            value = str(path) if path else "Sin seleccionar"
            label.setText(value if len(value) < 45 else "…" + value[-44:])
            label.setToolTip(value)
        self.update_preview()

    def choose_input(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona USB, Descargas o carpeta de entrada")
        if path:
            try:
                self.library.set_paths(input_path=Path(path))
                self.refresh_paths()
                self.refresh_pending()
            except Exception as error:
                self.show_error(str(error))

    def choose_library(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona la biblioteca donde guardar por género")
        if path:
            try:
                self.library.set_paths(library_path=Path(path))
                self.refresh_paths()
                self.refresh_pending()
            except Exception as error:
                self.show_error(str(error))

    def run_job(self, function, args, callback, message):
        if self.busy:
            return
        self.busy = True
        self.status.setText(message)
        for widget in (self.tabs, self.inspector, self.path_box, self.export_button):
            widget.setEnabled(False)
        self.job = Task(function, *args)
        self.job.signals.done.connect(lambda result: self.job_done(callback, result))
        self.job.signals.failed.connect(self.job_failed)
        self.pool.start(self.job)

    def unlock(self):
        self.busy = False
        for widget in (self.tabs, self.inspector, self.path_box, self.export_button):
            widget.setEnabled(True)

    def job_done(self, callback, result):
        self.unlock()
        try:
            callback(result)
        except Exception as error:
            self.show_error(str(error))

    def job_failed(self, message):
        self.unlock()
        self.show_error(message)

    def show_error(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "CapelHouse", message)

    def refresh_pending(self):
        self.remember_draft()
        self.run_job(self.library.scan, (), self.pending_loaded, "Buscando canciones…")

    def pending_loaded(self, paths):
        self.pending = paths
        self.filter_pending()
        self.status.setText(f"{len(paths)} canciones pendientes · {len(self.library.tracks)} preparadas")
        if not self.library.input_path or not self.library.input_path.is_dir():
            self.status.setText("Elige una carpeta de entrada disponible para comenzar.")

    def filter_pending(self):
        query = self.pending_search.text().casefold()
        paths = [path for path in self.pending if query in path.name.casefold()]
        with QSignalBlocker(self.pending_table):
            self.pending_table.setRowCount(len(paths))
            for row, path in enumerate(paths):
                item = QTableWidgetItem(path.name)
                item.setData(Qt.UserRole, str(path))
                item.setToolTip(str(path))
                self.pending_table.setItem(row, 0, item)
                self.pending_table.setItem(row, 1, QTableWidgetItem(path.parent.name))
            if paths:
                self.pending_table.selectRow(0)
        self.tabs.setTabText(0, f"Por escuchar ({len(paths)})")
        if paths:
            self.select_pending()
        elif self.tabs.currentIndex() == 0:
            self.clear_current()

    def select_pending(self):
        row = self.pending_table.currentRow()
        item = self.pending_table.item(row, 0)
        if item and self.tabs.currentIndex() == 0:
            self.open_track(Path(item.data(Qt.UserRole)))

    def sync_genre_filter(self):
        value = self.genre_filter.currentText()
        with QSignalBlocker(self.genre_filter):
            self.genre_filter.clear()
            self.genre_filter.addItems(["Todos los géneros", *sorted(set(self.library.genres + [r.get('genre', '') for r in self.library.tracks]) - {''})])
            self.genre_filter.setCurrentIndex(max(0, self.genre_filter.findText(value)))

    def visible_records(self):
        query = self.prepared_search.text().casefold()
        genre, color = self.genre_filter.currentText(), self.color_filter.currentText()
        rating = self.rating_filter.currentIndex() - 1
        return [record for record in self.library.tracks
                if (not query or query in f"{record.get('name', '')} {record.get('artist', '')}".casefold())
                and (self.genre_filter.currentIndex() <= 0 or record.get("genre") == genre)
                and (self.color_filter.currentIndex() <= 0 or record.get("color", "Sin color") == color)
                and (rating < 0 or record.get("rating", 0) == rating)]

    def render_prepared(self, *args):
        records = self.visible_records()
        selected = self.prepared_table.item(self.prepared_table.currentRow(), 0)
        selected_id = selected.data(Qt.UserRole) if selected else None
        selected_row = next((i for i, r in enumerate(records) if r["id"] == selected_id), 0)
        with QSignalBlocker(self.prepared_table):
            self.prepared_table.setRowCount(len(records))
            for row, record in enumerate(records):
                exists = Path(record["path"]).is_file()
                state = self.rb_states.get(record["id"], {})
                rb_text = RB_STATES.get(state.get("state"), "Sin verificar") if exists else "Archivo no localizado"
                values = [record.get("name", ""), record.get("genre", ""), f"{record.get('rating', 0)} / 5", record.get("color", "Sin color"), rb_text]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.UserRole, record["id"])
                    item.setToolTip(record["path"])
                    if col == 4 and state.get("detail"):
                        item.setToolTip(state["detail"])
                    if col == 3:
                        rgb = COLORS.get(value)
                        if rgb:
                            item.setForeground(QColor(*rgb))
                    self.prepared_table.setItem(row, col, item)
            if records:
                self.prepared_table.selectRow(selected_row)
        self.tabs.setTabText(1, f"Preparadas ({len(records)})")
        if self.tabs.currentIndex() == 1:
            if records:
                chosen = records[selected_row]
                if not self.current_record or self.current_record["id"] != chosen["id"]:
                    self.open_track(Path(chosen["path"]), chosen)
            else:
                self.clear_current()

    def select_prepared(self):
        item = self.prepared_table.item(self.prepared_table.currentRow(), 0)
        if item and self.tabs.currentIndex() == 1:
            record = next((r for r in self.library.tracks if r["id"] == item.data(Qt.UserRole)), None)
            if record:
                self.open_track(Path(record["path"]), record)

    def tab_changed(self, index):
        if index == 0:
            self.select_pending()
        else:
            self.select_prepared()
            if self.prepared_table.currentRow() < 0:
                if self.prepared_table.rowCount():
                    self.prepared_table.selectRow(0)
                else:
                    self.clear_current()

    def remember_draft(self):
        if self.current:
            self.drafts[str(self.current)] = (self.genre_combo.currentText(), self.current_rating, self.color_combo.currentText())

    def open_track(self, path, record=None):
        self.remember_draft()
        self.player.stop()
        self.current, self.current_record = path, record
        self.player.setSource(QUrl.fromLocalFile(str(path)) if path.is_file() else QUrl())
        self.song.setText(record.get("title", path.stem) if record else path.stem)
        self.artist.setText(record.get("artist") or path.name if record else path.name)
        self.cover.clear()
        self.cover.setText("CH")
        genre, rating, color = self.drafts.get(str(path), (record.get("genre", "") if record else self.genre_combo.currentText(), record.get("rating", 0) if record else 0, record.get("color", "Sin color") if record else "Sin color"))
        if genre:
            if self.genre_combo.findText(genre) < 0:
                self.genre_combo.addItem(genre)
            self.genre_combo.setCurrentText(genre)
        self.set_rating(rating)
        self.color_combo.setCurrentText(color)
        self.save_button.setText("Actualizar preparación" if record else "Guardar y siguiente")
        self.update_preview()
        self.load_cover(path)

    def clear_current(self):
        self.remember_draft()
        self.player.stop()
        self.player.setSource(QUrl())
        self.current = self.current_record = None
        self.song.setText("Selecciona una canción")
        self.cover.clear()
        self.cover.setText("CH")
        self.artist.setText("Género, estrellas y color se eligen por separado")

    def load_cover(self, path):
        try:
            raw = audio_metadata(path)
            pictures = getattr(raw, "pictures", [])
            data = pictures[0].data if pictures else None
            if not data:
                for tag in (getattr(raw, "tags", None) or {}).values():
                    candidate = getattr(tag, "data", None)
                    if isinstance(candidate, bytes):
                        data = candidate
                        break
            if data:
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    self.cover.setPixmap(pixmap.scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            logging.debug("No cover for %s", path)

    def set_rating(self, rating):
        self.current_rating = rating
        for index, button in enumerate(self.star_buttons, 1):
            button.setIcon(star_icon(index <= rating))

    def update_preview(self, *args):
        library = self.library.library_path
        genre = self.genre_combo.currentText()
        self.preview.setText(f"Destino: {library / genre}" if library and genre else "Elige el destino y un género para guardar")

    def edit_genres(self):
        text, ok = QInputDialog.getMultiLineText(self, "Tus géneros", "Un género por línea:", "\n".join(self.library.genres))
        if ok:
            try:
                selected = self.genre_combo.currentText()
                self.library.set_genres(text.splitlines())
                self.genre_combo.clear()
                self.genre_combo.addItems(self.library.genres)
                self.genre_combo.setCurrentIndex(max(0, self.genre_combo.findText(selected)))
                self.sync_genre_filter()
                self.render_prepared()
            except Exception as error:
                self.show_error(str(error))

    def classify(self):
        if self.busy or not self.current:
            return
        source = self.current
        genre, rating, color = self.genre_combo.currentText(), self.current_rating, self.color_combo.currentText()
        record = self.current_record
        self.player.stop()
        self.player.setSource(QUrl())
        action = self.library.update if record else self.library.prepare
        args = (record["id"] if record else source, genre, rating, color)
        self.run_job(action, args, lambda result: self.saved(result, source, bool(record)), "Guardando preparación…")

    def saved(self, result, source, updating):
        self.drafts.pop(str(source), None)
        self.rb_states.pop(result["id"], None)
        self.current = self.current_record = None
        self.sync_genre_filter()
        self.render_prepared()
        if updating:
            self.open_track(Path(result["path"]), result)
            self.status.setText("Estrellas, color y género actualizados.")
        else:
            self.pending = [path for path in self.pending if path != source]
            self.filter_pending()
            self.status.setText(f"Preparada: {result.get('name', '')} · {result['genre']} · {result['rating']} estrellas · {result['color']}")
            if self.autoplay.isChecked() and self.current:
                self.player.play()

    def bridge_directory(self):
        configured = self.library.config.get("rekordbox_bridge_dir")
        return Path(configured) if configured else default_bridge_dir()

    def send_to_rekordbox(self):
        if self.busy:
            return
        if not self.library.tracks:
            self.show_error("Primero prepara al menos una canción por género.")
            return
        # Always publish the complete library; UI filters must not remove tracks from the bridge.
        records = [dict(record) for record in self.library.tracks]
        self.run_job(publish_library, (records, self.bridge_directory()), self.bridge_published,
                     "Actualizando la biblioteca de conexión con Rekordbox…")

    def bridge_published(self, result):
        self.last_export = result
        self.status.setText(f"Biblioteca publicada: {result['count']} canciones. Falta comprobar su importación y análisis.")
        self.show_connection_dialog(result)

    def show_connection_dialog(self, result):
        dialog = QDialog(self)
        self.connection_dialog = dialog
        dialog.setWindowTitle("Conectar CapelHouse con Rekordbox")
        dialog.resize(680, 520)
        layout = QVBoxLayout(dialog)
        heading = QLabel("Tu música, conectada a Rekordbox")
        heading.setObjectName("song")
        layout.addWidget(heading)
        path = Path(result["xml"])
        self.connection_label = QLabel()
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)
        path_field = QLineEdit(str(path))
        path_field.setReadOnly(True)
        layout.addWidget(path_field)
        copy = QPushButton("Copiar ruta de conexión")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(str(path)))
        layout.addWidget(copy)
        instructions = QLabel(
            "1. Con Rekordbox cerrado, pulsa Configurar conexión. Se activan el panel XML y el análisis automático.\n\n"
            "2. Abre Rekordbox. En su panel lateral, abre rekordbox xml > Playlists > CapelHouse "
            "y usa Importar playlist en los géneros que quieras añadir. "
            "Si el panel muestra una versión anterior, pulsa su botón Actualizar.\n\n"
            "3. Pulsa Comprobar estado. CapelHouse solo muestra Lista cuando encuentra la canción "
            "en Colección, la clasificación coincide y hay datos nativos de análisis. "
            "Si falta el análisis, selecciona la canción en Rekordbox y usa Analizar pista.\n\n"
            "La ruta de conexión se mantiene en los siguientes envíos. Las canciones continúan en sus carpetas por género.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        buttons = QHBoxLayout()
        configure = QPushButton("Configurar conexión")
        configure.clicked.connect(lambda: self.configure_bridge(path))
        buttons.addWidget(configure)
        open_rb = QPushButton("Abrir Rekordbox")
        open_rb.clicked.connect(self.open_rekordbox)
        buttons.addWidget(open_rb)
        check = QPushButton("Comprobar estado")
        check.clicked.connect(self.refresh_rekordbox_status)
        buttons.addWidget(check)
        layout.addLayout(buttons)
        repair = QPushButton("Aplicar clasificación a canciones ya importadas")
        repair.clicked.connect(self.repair_native_classification)
        layout.addWidget(repair)
        repair_help = QLabel("Si las canciones ya estaban en Colección, cierra Rekordbox y usa este botón. "
                             "Se respalda la biblioteca y se actualizan solo género, estrellas y color; se conserva el análisis.")
        repair_help.setWordWrap(True)
        layout.addWidget(repair_help)
        self.connection_results = QLabel("La publicación del XML no confirma la importación.")
        self.connection_results.setWordWrap(True)
        layout.addWidget(self.connection_results)
        close = QPushButton("Volver a mi biblioteca")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        self.update_connection_label(path)
        missing = result.get("missing", [])
        if missing:
            self.connection_results.setText(f"Se omitieron {len(missing)} archivos no localizados. Consulta missing_files.txt junto al XML.")
        self.rb_timer.start()
        dialog.finished.connect(lambda: self.rb_timer.stop())
        dialog.exec()
        self.connection_dialog = None

    def update_connection_label(self, xml_path=None):
        path = xml_path or self.bridge_directory() / "CapelHouse.xml"
        try:
            connection = inspect_connection(xml_path=path)
        except Exception as error:
            connection = {"configured": False, "running": False, "error": str(error)}
        self.rb_connection = connection
        if hasattr(self, "connection_label"):
            configured = connection.get("configured")
            running = connection.get("running")
            text = ("Conexión configurada." if configured else "Rekordbox aún no apunta a esta biblioteca.")
            if connection.get("error"):
                text += f" {connection['error']}"
            if running and not configured:
                text += " Cierra Rekordbox para configurar sin sobrescribir sus ajustes abiertos."
            self.connection_label.setText(text)
        return connection

    def configure_bridge(self, path):
        if self.busy:
            return
        try:
            result = configure_connection(path)
            self.update_connection_label(path)
            self.connection_results.setText(f"Conexión configurada. Respaldo de ajustes: {result.get('backup', '')}")
        except Exception as error:
            self.connection_results.setText(str(error))

    def open_rekordbox(self):
        connection = self.update_connection_label()
        executable = connection.get("executable")
        if not executable:
            self.show_error("No se encontró Rekordbox. Ábrelo desde su acceso directo.")
            return
        try:
            subprocess.Popen([str(executable)], shell=False)
        except OSError as error:
            self.show_error(str(error))

    def repair_native_classification(self):
        if self.busy:
            return
        self.run_job(apply_classification, ([dict(record) for record in self.library.tracks],),
                     self.native_classification_applied, "Respaldando y aplicando la clasificación en Rekordbox…")

    def native_classification_applied(self, result):
        text = f"Clasificación aplicada a {result['updated']} canciones."
        if result.get("backup"):
            text += f" Respaldo: {result['backup']}"
        if result.get("missing"):
            text += f" {len(result['missing'])} canciones todavía deben importarse desde el panel XML."
        if self.connection_dialog is not None:
            self.connection_results.setText(text)
        self.status.setText(text)
        self.refresh_rekordbox_status()

    def refresh_rekordbox_status(self):
        if self.busy or not self.library.tracks:
            return
        records = [dict(record) for record in self.library.tracks]
        self.run_job(inspect_tracks, (records,), self.rekordbox_status_received,
                     "Comprobando importación, clasificación y análisis en Rekordbox…")

    def rekordbox_status_received(self, statuses):
        self.rb_states = {row["id"]: row for row in statuses}
        self.render_prepared()
        counts = {}
        for row in statuses:
            state = RB_STATES.get(row.get("state"), "Sin verificar")
            counts[state] = counts.get(state, 0) + 1
        text = " · ".join(f"{count} {name.lower()}" for name, count in counts.items())
        self.status.setText(text or "No hay canciones que verificar.")
        if self.connection_dialog is not None:
            self.connection_results.setText(text)

    def skip_current(self):
        if self.current and not self.current_record:
            try:
                self.library.skip(self.current)
                self.refresh_pending()
            except Exception as error:
                self.show_error(str(error))

    def restore_skipped(self):
        try:
            self.library.restore_skipped()
            self.refresh_pending()
        except Exception as error:
            self.show_error(str(error))

    def toggle_playback(self):
        if not self.current or not self.current.is_file():
            self.status.setText("Selecciona un archivo de audio disponible.")
            return
        if self.player.source().isEmpty():
            self.player.setSource(QUrl.fromLocalFile(str(self.current)))
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek(self, delta):
        self.player.setPosition(max(0, min(self.player.duration(), self.player.position() + delta)))

    def duration_changed(self, duration):
        self.progress.setRange(0, duration)
        self.position_changed(self.player.position())

    def position_changed(self, position):
        if not self.progress.isSliderDown():
            self.progress.setValue(position)
        self.time_label.setText(f"{clock(position)} / {clock(self.player.duration())}")

    def playback_changed(self, state):
        self.play_button.setText("Pausar" if state == QMediaPlayer.PlayingState else "Reproducir")

    def playback_error(self, error, message):
        if error != QMediaPlayer.NoError:
            self.status.setText(f"No se pudo reproducir: {message}")

    def export(self):
        records = self.visible_records() if self.tabs.currentIndex() == 1 and self.export_filtered.isChecked() else list(self.library.tracks)
        if not records:
            self.show_error("Prepara al menos una canción o amplía los filtros para exportar.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Dónde guardar la exportación para Rekordbox")
        if folder:
            self.run_job(export_library, (records, Path(folder)), self.export_done, "Generando XML, playlist y respaldo…")

    def export_done(self, result):
        self.last_export = result
        self.status.setText(f"Exportadas {result['count']} canciones. XML: {result['xml']}")
        missing = len(result.get("missing", []))
        text = (f"{result['count']} canciones exportadas.\n\n{result['xml']}\n\n"
                "En Rekordbox, elige este XML en Preferencias > Avanzado > Base de datos > rekordbox xml "
                "(la ubicación depende de la versión). Activa el panel rekordbox xml y usa Importar colección o playlist.\n\n"
                "El XML lleva género, estrellas y color. El M3U8 solo contiene la lista de archivos. "
                "Conserva las canciones en su ubicación después de importar.")
        if missing:
            text += f"\n\nSe omitieron {missing} archivos no localizados. Revisa el respaldo de exportación."
        box = QMessageBox(QMessageBox.Information, "Preparación exportada", text, parent=self)
        open_button = box.addButton("Abrir carpeta", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() == open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(result["xml"]).parent)))

    def eventFilter(self, obj, event):
        if isinstance(event, QKeyEvent) and event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            if self.busy or QApplication.activeModalWidget() is not None:
                return super().eventFilter(obj, event)
            focus = QApplication.focusWidget()
            if isinstance(focus, (QLineEdit, QComboBox)) or (focus is not None and focus.inherits("QTextEdit")):
                return super().eventFilter(obj, event)
            if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
                return super().eventFilter(obj, event)
            key = event.key()
            if key == Qt.Key_Space:
                self.toggle_playback()
            elif Qt.Key_0 <= key <= Qt.Key_5:
                self.set_rating(key - Qt.Key_0)
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self.classify()
            elif key in (Qt.Key_Left, Qt.Key_Right):
                self.seek(5000 if key == Qt.Key_Right else -5000)
            else:
                return super().eventFilter(obj, event)
            return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self.busy:
            self.status.setText("Espera a que termine la operación para cerrar CapelHouse.")
            event.ignore()
            return
        self.rb_timer.stop()
        self.player.stop()
        self.player.setSource(QUrl())
        if self.theme_changed:
            try:
                self.library.save()
            except OSError as error:
                self.status.setText(f"No se pudo guardar el tema: {error}")
        QApplication.instance().removeEventFilter(self)
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="CapelHouse")
    parser.add_argument("--config", type=Path, help="Ruta de configuración alternativa")
    parser.add_argument("--self-test", type=Path, help="Verifica la aplicación con audios sintéticos en esta carpeta")
    parser.add_argument("--diagnose-rekordbox", type=Path, help="Guarda un diagnóstico de conexión y análisis en solo lectura")
    options = parser.parse_args()
    if options.diagnose_rekordbox:
        from rekordbox_diagnostic import create_report
        return create_report(options.config or config_location(), options.diagnose_rekordbox)
    if options.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("CapelHouse")
    try:
        if options.self_test:
            from smoke_check import start_check
            return start_check(app, options.self_test)
        window = App(options.config)
    except Exception as error:
        QMessageBox.critical(None, "CapelHouse no pudo iniciar", str(error))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
