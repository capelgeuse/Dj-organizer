"""Interfaz Qt clara para organizar canciones con el flujo de Texto_punto_cero."""
import json, shutil, sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QImage, QKeyEvent, QPixmap, QIcon, QFontDatabase
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSlider, QSplitter, QVBoxLayout, QWidget,
    QLineEdit, QTextEdit)
import pygame
from mutagen import File as open_metadata

AUDIO = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
CONFIG = Path(__file__).with_name("configuracion_dj.json")
LOGO = Path(__file__).with_name("logo.png")
BRAND_FONT = Path(__file__).with_name("Mr_Dafoe") / "MrDafoe-Regular.ttf"
BYLINE_FONT = Path(__file__).with_name("Barlow_Condensed,Mr_Dafoe") / "Barlow_Condensed" / "BarlowCondensed-BlackItalic.ttf"

class App(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("CapelHouse · Organizador DJ"); self.resize(1440, 900); self.setMinimumSize(1000, 650); self.statusBar().setSizeGripEnabled(True)
        self.cfg = self.read_config(); self.input_path=Path(self.cfg.get("entrada", "")); self.library_path=Path(self.cfg.get("biblioteca", "")); self.categories=self.cfg.get("categorias", ["Inicio", "Medio", "Ponchadas"]); self.genres=self.cfg.get("generos", []); self.reviewed=self.cfg.get("revisadas", []); self.omitted=self.cfg.get("omitidas", []); self.tracks=[]; self.current=None; self.playing=False; self.paused=False; self.position=0; self.duration=0; self.ignore_slider=False
        self.audio_ready=False
        self.dark_mode=False; self.brand_family="Mr Dafoe"; font_id=QFontDatabase.addApplicationFont(str(BRAND_FONT)) if BRAND_FONT.is_file() else -1; families=QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []; self.brand_family=families[0] if families else self.brand_family; self.build_ui(); self.size_combo.setMinimumWidth(135); self.genre_combo.setMinimumWidth(150); self.genre_combo.setPlaceholderText("Sin géneros — pulsa Editar"); self.reviewed_list.setIconSize(QSize(48,48)); self.reviewed_list.setSpacing(5); self.reviewed_list.setUniformItemSizes(True); self.volume=QSlider(Qt.Horizontal); self.volume.setMinimumWidth(180); self.volume.setRange(0,100); self.volume.setValue(80); self.volume.valueChanged.connect(self.set_volume); self.volume_label=QLabel("Volumen 80%"); self.category_box.insertWidget(0,self.volume_label); self.category_box.insertWidget(1,self.volume); self.apply_theme(); self.load_tracks(); QTimer.singleShot(0,self.balance_split); QApplication.instance().installEventFilter(self); self.timer=QTimer(self); self.timer.timeout.connect(self.update_progress); self.timer.start(400)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"main_split"): self.balance_split()
    def balance_split(self):
        if hasattr(self,"main_split") and self.main_split.count()==3:
            width=max(1,self.main_split.width()); self.main_split.setSizes([int(width*.36),int(width*.20),int(width*.44)])
    def set_volume(self,value):
        self.volume_label.setText(f"Volumen {value}%")
        if self.audio_ready:
            pygame.mixer.music.set_volume(value/100)
    def show_message(self,icon,title,text):
        box=QMessageBox(self); box.setIcon(icon); box.setWindowTitle(title); box.setText(text)
        if self.dark_mode:
            box.setStyleSheet("QMessageBox{background:#181b1f;color:#f4f3ee} QMessageBox QLabel{color:#f4f3ee;min-width:280px} QMessageBox QPushButton{background:#1e2227;color:#f4f3ee;border:1px solid #2a2f35;border-radius:7px;padding:7px 16px} QMessageBox QPushButton:hover{background:#2c2920;border-color:#e6b84a}")
        else:
            box.setStyleSheet("QMessageBox{background:#ffffff;color:#17191c} QMessageBox QLabel{color:#17191c;min-width:280px} QMessageBox QPushButton{background:#ffffff;color:#17191c;border:1px solid #cbc8c0;border-radius:7px;padding:7px 16px} QMessageBox QPushButton:hover{background:#f7edcf;border-color:#d8a933}")
        box.exec()
    def relocate_controls(self):
        if getattr(self,"controls_relocated",False): return
        self.controls_relocated=True
        self.play.setObjectName("playButton"); self.progress.setObjectName("timeline"); self.list.setObjectName("pendingList"); self.reviewed_list.setObjectName("reviewedList")
        if self.category_box.count()>=2:
            self.category_box.takeAt(0); self.category_box.takeAt(0)
        heading=QLabel("CLASIFICACIÓN"); heading.setObjectName("sectionHeading"); self.category_box.insertWidget(0,heading)
        player_layout=self.volume.parentWidget().layout() if self.volume.parentWidget() else None
        if player_layout:
            player_layout.insertWidget(5,self.volume_label); player_layout.insertWidget(6,self.volume)
    def read_config(self):
        try: return json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return {}
    def save_config(self):
        self.cfg.update(entrada=str(self.input_path), biblioteca=str(self.library_path), categorias=self.categories, generos=self.genres, revisadas=self.reviewed, omitidas=self.omitted); CONFIG.write_text(json.dumps(self.cfg,ensure_ascii=False,indent=2),encoding="utf-8")
    def build_ui(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); outer.setContentsMargins(28,24,28,18); outer.setSpacing(14)
        title=QLabel("CAPELHOUSE\nOrganiza tu música con orden"); title.setObjectName("title"); outer.addWidget(title); sub=QLabel("Elige una canción, escúchala y clasifícala. Los originales se conservan."); sub.setObjectName("muted"); outer.addWidget(sub)
        locations=QGroupBox("Ubicaciones"); loc=QHBoxLayout(locations); self.input_label=QLabel(); self.library_label=QLabel(); b=QPushButton("Entrada"); b.clicked.connect(self.choose_input); d=QPushButton("Destino"); d.clicked.connect(self.choose_library); loc.addWidget(b); loc.addWidget(self.input_label,1); loc.addWidget(d); loc.addWidget(self.library_label,1); loc.addWidget(QLabel("Tamaño:")); self.size_combo=QComboBox(); self.size_combo.addItems(["1440 × 900", "1920 × 1080", "1366 × 768"]); self.size_combo.currentIndexChanged.connect(self.change_size); loc.addWidget(self.size_combo); outer.addWidget(locations)
        theme=QPushButton("Modo noche"); theme.clicked.connect(self.toggle_theme); loc.addWidget(theme)
        split=QSplitter(Qt.Horizontal); self.main_split=split; outer.addWidget(split,1); split.setChildrenCollapsible(False); split.setStretchFactor(0,3); split.setStretchFactor(1,2); split.setStretchFactor(2,5)
        library=QGroupBox("Canciones por revisar"); lv=QVBoxLayout(library); self.list=QListWidget(); self.list.currentRowChanged.connect(self.select); self.list.setToolTip("Selecciona una canción y pulsa Supr para quitarla de esta lista"); lv.addWidget(self.list); actions=QHBoxLayout(); remove=QPushButton("Quitar seleccionada"); remove.setToolTip("La canción no se borrará del disco"); remove.clicked.connect(self.omit_current); update=QPushButton("Actualizar lista"); update.clicked.connect(self.load_tracks); actions.addWidget(remove); actions.addWidget(update); lv.addLayout(actions); split.addWidget(library)
        reviewed_box=QGroupBox("Canciones revisadas"); rv=QVBoxLayout(reviewed_box); self.reviewed_list=QListWidget(); self.reviewed_list.setWordWrap(True); rv.addWidget(self.reviewed_list); split.addWidget(reviewed_box)
        inspector=QGroupBox("Reproductor y clasificación"); iv=QVBoxLayout(inspector); scroll=QScrollArea(); scroll.setWidgetResizable(True); panel=QWidget(); pv=QVBoxLayout(panel); self.cover=QLabel("♪"); self.cover.setObjectName("cover"); self.cover.setAlignment(Qt.AlignCenter); pv.addWidget(self.cover); self.name=QLabel("Selecciona una canción"); self.name.setObjectName("song"); self.name.setWordWrap(True); pv.addWidget(self.name); self.info=QLabel("BPM -- · Duración --:--"); pv.addWidget(self.info); self.play=QPushButton("▶  Reproducir"); self.play.clicked.connect(self.toggle); pv.addWidget(self.play); jump=QHBoxLayout(); forw=QPushButton("+5 s"); forw.clicked.connect(lambda:self.seek(5)); back=QPushButton("−5 s"); back.clicked.connect(lambda:self.seek(-5)); jump.addWidget(back); jump.addWidget(forw); pv.addLayout(jump); self.progress=QSlider(Qt.Horizontal); self.progress.setRange(0,1); self.progress.sliderReleased.connect(self.seek_slider); pv.addWidget(self.progress); genre=QHBoxLayout(); genre.addWidget(QLabel("Género")); self.genre_combo=QComboBox(); self.genre_combo.addItems(self.genres); genre.addWidget(self.genre_combo,1); edit_genre=QPushButton("Editar"); edit_genre.clicked.connect(self.manage_genres); genre.addWidget(edit_genre); pv.addLayout(genre); edit_cat=QPushButton("Administrar categorías"); edit_cat.clicked.connect(self.manage_categories); pv.addWidget(edit_cat); self.category_box=QVBoxLayout(); pv.addLayout(self.category_box); pv.addStretch(); scroll.setWidget(panel); iv.addWidget(scroll); split.addWidget(inspector); split.setSizes([700,420]); self.refresh_labels(); self.render_categories(); self.setStyleSheet(self.styles())
        layout=self.centralWidget().layout(); layout.itemAt(0).widget().hide(); layout.itemAt(1).widget().hide(); header=QHBoxLayout(); self.logo=QLabel(); self.logo.setFixedSize(120,120); self.logo.setAlignment(Qt.AlignCenter); header.addWidget(self.logo); head_text=QVBoxLayout(); self.brand=QLabel("Capelhouse"); self.brand.setObjectName("brand"); self.brand.setStyleSheet("font-family:'"+self.brand_family+"';font-size:40px;font-weight:400;color:#172027"); head_text.addWidget(self.brand); tagline=QLabel("By Capelgeuse"); tagline.setObjectName("byline"); head_text.addWidget(tagline); header.addLayout(head_text,1); layout.insertLayout(0,header); self.logo.setPixmap(QPixmap(str(LOGO)).scaled(112,112,Qt.KeepAspectRatio,Qt.SmoothTransformation)) if LOGO.is_file() else self.logo.setText("♪")
    def styles(self): return "QMainWindow{background:#f3f5f7} QLabel{color:#111820} QLabel#brand{font-family:'Mr Dafoe';font-size:38px;font-weight:400;color:#172027} QLabel#title{font-size:27px;font-weight:700;color:#172027} QLabel#muted{color:#66737d} QGroupBox{background:#fff;border:1px solid #dce2e7;border-radius:10px;margin-top:10px;padding:14px;font-weight:600} QGroupBox QLabel{color:#111820} QGroupBox QLabel#song{color:#111820;background:transparent;font-size:17px;font-weight:600} QScrollArea{background:#fff;border:0} QScrollArea QWidget{background:#fff} QSplitter::handle{background:#dce2e7;width:2px} QComboBox{min-height:28px;padding:3px 8px;border:1px solid #cbd3da;border-radius:6px;background:#fff;color:#111820} QComboBox QAbstractItemView{background:#fff;color:#111820;selection-background-color:#e76552;selection-color:#fff} QSlider::groove:horizontal{height:6px;background:#d5dce1;border-radius:3px} QSlider::handle:horizontal{width:14px;height:14px;margin:-4px 0;border-radius:7px;background:#e76552} QScrollBar:vertical{width:10px;background:transparent;margin:2px} QScrollBar::handle:vertical{background:#c3cbd1;min-height:30px;border-radius:5px} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0} QPushButton{background:#fff;border:1px solid #cbd3da;border-radius:7px;padding:9px 13px} QPushButton:hover{background:#fff0ec;border-color:#e76552} QListWidget{background:#fbfcfd;border:0;padding:7px} QListWidget::item{background:#ffffff;border:1px solid #e1e6ea;border-radius:8px;margin:3px 2px;padding:10px 8px} QListWidget::item:hover{background:#fff7f4;border-color:#efb1a5} QListWidget::item:selected{background:#e76552;color:white;border-color:#e76552} QLabel#cover{background:#29313a;color:white;min-height:110px;max-height:135px;font-size:46px;border-radius:8px}"
    def configure_logo(self):
        barlow_id=QFontDatabase.addApplicationFont(str(BYLINE_FONT)) if BYLINE_FONT.is_file() else -1; barlow_families=QFontDatabase.applicationFontFamilies(barlow_id) if barlow_id>=0 else []; byline_family=barlow_families[0] if barlow_families else "Barlow Condensed"
        if hasattr(self,"brand") and self.brand.parentWidget() and self.brand.parentWidget().layout(): self.brand.parentWidget().layout().setSpacing(-4); self.brand.parentWidget().layout().setContentsMargins(0,0,0,0); byline=self.brand.parentWidget().layout().itemAt(1).widget(); byline.setText("By Capelgeuse"); byline.setObjectName("byline"); byline.setStyleSheet("font-family:'"+byline_family+"';font-size:20px;font-weight:900;color:"+ ("#f4f1eb" if self.dark_mode else "#172027")); byline.setAlignment(Qt.AlignLeft|Qt.AlignTop); self.brand.parentWidget().layout().itemAt(2).widget().hide()
        if not LOGO.is_file() or not hasattr(self,"logo"): return
        image=QImage(str(LOGO))
        if image.isNull(): return
        side=min(image.width(),image.height()); full=QPixmap.fromImage(image).scaled(112,112,Qt.KeepAspectRatio,Qt.SmoothTransformation); self.logo.setFixedSize(120,120); self.logo.setPixmap(full); face=image.copy(int(image.width()*.35),int(image.height()*.16),int(side*.30),int(side*.30)); face_icon=QPixmap.fromImage(face).scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation); self.setWindowIcon(QIcon(face_icon))
    def apply_theme(self):
        self.relocate_controls()
        self.configure_logo()
        if self.dark_mode:
            self.setStyleSheet(self.styles()+"QMainWindow{background:#111315} QLabel{color:#f4f3ee} QLabel#title{color:#f4f3ee;font-family:'Segoe UI';font-size:24px;font-weight:600} QLabel#muted{color:#979ea6;font-family:'Segoe UI'} QLabel#sectionHeading{color:#e6b84a;font-size:12px;font-weight:700;letter-spacing:1px} QGroupBox{background:#181b1f;color:#f4f3ee;border-color:#2a2f35} QGroupBox QLabel{color:#f4f3ee} QGroupBox QLabel#song{color:#f4f3ee;background:transparent} QScrollArea{background:#181b1f} QScrollArea QWidget{background:#181b1f} QSplitter::handle{background:#2a2f35;width:2px} QComboBox{background:#1e2227;color:#f4f3ee;border-color:#2a2f35} QComboBox QAbstractItemView{background:#1e2227;color:#f4f3ee;selection-background-color:#e6b84a;selection-color:#111315} QPushButton{background:#1e2227;color:#f4f3ee;border-color:#2a2f35} QPushButton:hover{background:#2c2920;border-color:#e6b84a;color:#f0c75e} QListWidget{background:#1e2227;color:#f4f3ee} QListWidget::item{background:#1e2227;color:#f4f3ee;border:0;border-left:3px solid transparent;margin:2px 0;padding:10px 8px} QListWidget::item:hover{background:#252a2f} QListWidget::item:selected{background:#2b3029;color:#f4f3ee;border-left:3px solid #e6b84a} #reviewedList::item{border:1px solid #2a2f35;border-radius:8px;margin:4px 2px;padding:8px} #reviewedList::item:selected{border-color:#e6b84a} QComboBox,QSlider{color:#f4f3ee} QPushButton#playButton{background:#e6b84a;color:#111315;border:0;border-radius:28px;font-size:16px;font-weight:700;min-height:52px} QPushButton#playButton:hover{background:#f0c75e} QPushButton#categoryButton{background:#1e2227;color:#f4f3ee;border:1px solid #2a2f35;border-radius:8px;min-height:38px;font-weight:600} QPushButton#categoryButton:hover{background:#2c2920;color:#f0c75e;border-color:#e6b84a}")
            self.cover.setStyleSheet("background:#20252a;color:white;border-radius:8px;min-height:220px;max-height:280px;font-size:64px"); self.name.setStyleSheet("color:#f4f1eb;font-size:20px;font-weight:600"); self.info.setStyleSheet("color:#979ea6"); self.brand.setStyleSheet("font-family:'"+self.brand_family+"';font-size:40px;font-weight:400;color:#f4f1eb")
        else:
            self.setStyleSheet(self.styles()+"QMainWindow{background:#f2f1ec} QLabel{color:#17191c} QLabel#title{color:#17191c;font-family:'Segoe UI';font-size:24px;font-weight:600} QLabel#muted{color:#73787e;font-family:'Segoe UI'} QLabel#sectionHeading{color:#b78b18;font-size:12px;font-weight:700;letter-spacing:1px} QGroupBox{background:#ffffff;color:#17191c;border-color:#d8d5cd} QGroupBox QLabel{color:#17191c} QGroupBox QLabel#song{color:#17191c;background:transparent} QScrollArea{background:#ffffff} QScrollArea QWidget{background:#ffffff} QSplitter::handle{background:#d8d5cd;width:2px} QComboBox{background:#ffffff;color:#17191c;border-color:#cbc8c0} QComboBox QAbstractItemView{background:#ffffff;color:#17191c;selection-background-color:#d8a933;selection-color:#17191c} QPushButton{background:#ffffff;color:#17191c;border-color:#cbc8c0} QPushButton:hover{background:#f7edcf;color:#6f5310;border-color:#d8a933} QListWidget{background:#faf9f5;color:#17191c} QListWidget::item{background:#ffffff;color:#17191c;border:0;border-left:3px solid transparent;margin:2px 0;padding:10px 8px} QListWidget::item:hover{background:#f7f4ea} QListWidget::item:selected{background:#f7edcf;color:#17191c;border-left:3px solid #d8a933} #reviewedList::item{border:1px solid #dedbd3;border-radius:8px;margin:4px 2px;padding:8px} #reviewedList::item:selected{border-color:#d8a933} QPushButton#playButton{background:#d8a933;color:#17191c;border:0;border-radius:28px;font-size:16px;font-weight:700;min-height:52px} QPushButton#playButton:hover{background:#e4ba49} QPushButton#categoryButton{background:#ffffff;color:#17191c;border:1px solid #cbc8c0;border-radius:8px;min-height:38px;font-weight:600} QPushButton#categoryButton:hover{background:#f7edcf;color:#6f5310;border-color:#d8a933}")
            self.cover.setStyleSheet("background:#3b4145;color:#ffffff;border-radius:8px;min-height:220px;max-height:280px;font-size:64px"); self.name.setStyleSheet("color:#17191c;font-size:20px;font-weight:600"); self.info.setStyleSheet("color:#73787e"); self.brand.setStyleSheet("font-family:'"+self.brand_family+"';font-size:40px;font-weight:400;color:#172027")
    def toggle_theme(self):
        self.dark_mode=not self.dark_mode; self.apply_theme()
        for button in self.findChildren(QPushButton):
            if button.text() in {"Modo noche","Modo día"}: button.setText("Modo día" if self.dark_mode else "Modo noche")
    def refresh_labels(self):
        if not hasattr(self,"status"):
            self.status=QLabel("Atajos: ↑ ↓ seleccionar · ← → mover 5 s · Espacio reproducir/pausar · 1, 2, 3… clasificar"); self.status.setObjectName("muted"); self.centralWidget().layout().addWidget(self.status)
        self.input_label.setText(str(self.input_path) if self.input_path else "Sin seleccionar"); self.library_label.setText(str(self.library_path) if self.library_path else "Sin seleccionar")
    def choose_input(self):
        path=QFileDialog.getExistingDirectory(self,"Selecciona carpeta de entrada");
        if path: self.input_path=Path(path); self.save_config(); self.refresh_labels(); self.load_tracks()
    def choose_library(self):
        path=QFileDialog.getExistingDirectory(self,"Selecciona carpeta de destino");
        if path: self.library_path=Path(path); self.save_config(); self.refresh_labels()
    def change_size(self,index):
        sizes=[(1440,900),(1920,1080),(1366,768)]
        if 0<=index<len(sizes):
            self.showNormal(); screen=QApplication.primaryScreen().availableGeometry(); target_w,target_h=sizes[index]; width=min(target_w,screen.width()); height=min(target_h,screen.height()); self.resize(width,height); self.move(screen.left()+max(0,(screen.width()-width)//2),screen.top()+max(0,(screen.height()-height)//2)); self.balance_split()
    def load_tracks(self):
        candidates=[p for p in self.input_path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO] if self.input_path.is_dir() else []
        reviewed_paths={str(item.get("source", "")) for item in self.reviewed}; omitted_paths=set(self.omitted); self.tracks=sorted([p for p in candidates if str(p) not in reviewed_paths and str(p) not in omitted_paths and not any(part in self.categories for part in p.relative_to(self.input_path).parts[:-1])],key=lambda p:p.name.casefold()); self.list.clear(); [self.list.addItem(p.name) for p in self.tracks]; self.render_reviewed(); self.select_first()
    def select_first(self):
        if self.tracks and self.list.currentRow()<0:self.list.setCurrentRow(0)
    def omit_current(self):
        if not self.current or self.current not in self.tracks:return
        source=str(self.current)
        if source not in self.omitted:self.omitted.append(source)
        self.stop(); self.current=None; self.save_config(); self.load_tracks(); self.status_message("Canción quitada de la lista; el archivo se conservó")
    def select(self,index):
        if index<0 or index>=len(self.tracks):return
        self.stop(); self.current=self.tracks[index]; data=self.meta(self.current); self.duration=data["duration_seconds"]; self.position=0; self.name.setText(self.current.name); self.info.setText(f"BPM {data['bpm'] or '--'} · Duración {data['duration']}"); self.cover.setText(self.current.name[:1]); self.cover.setPixmap(QPixmap());
        if data["cover"]: self.cover.setPixmap(QPixmap.fromImage(data["cover"]).scaled(260,260,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.progress.setRange(0,max(1,self.duration)); self.progress.setValue(0)
    def meta(self,path):
        out={"bpm":None,"duration":"--:--","duration_seconds":0,"cover":None}
        try:
            raw=open_metadata(str(path)); easy=open_metadata(str(path),easy=True)
            seconds=round(getattr(getattr(raw,"info",None),"length",0) or 0); out["duration_seconds"]=seconds; out["duration"]=f"{seconds//60}:{seconds%60:02d}" if seconds else "--:--"
            tags=getattr(easy,"tags",None) or {}
            for key in ("bpm","tbpm","tempo"):
                if tags.get(key):
                    out["bpm"]=round(float(str(tags[key][0]).replace(',','.'))); break
            pictures=list(getattr(raw,"pictures",[]) or [])
            image_data=None
            if pictures: image_data=pictures[0].data
            else:
                for value in (getattr(raw,"tags",None) or {}).values():
                    data=getattr(value,"data",None)
                    if isinstance(data,(bytes,bytearray)) and data:
                        image_data=data; break
            if image_data:
                image=QImage();
                if image.loadFromData(image_data): out["cover"]=image
        except Exception: pass
        if out["cover"] is None:
            for stem in ("cover","folder","front",path.stem):
                for extension in (".jpg",".jpeg",".png",".webp"):
                    nearby=path.parent/f"{stem}{extension}"
                    if nearby.is_file():
                        image=QImage(str(nearby))
                        if not image.isNull(): out["cover"]=image; return out
        return out
    def toggle(self):
        if not self.current:return
        if not self.audio_ready:
            try: pygame.mixer.init(); pygame.mixer.music.set_volume(self.volume.value()/100); self.audio_ready=True
            except pygame.error: self.show_message(QMessageBox.Warning,"Audio no disponible","No se pudo inicializar el dispositivo de audio."); return
        try:
            if self.playing and not self.paused: pygame.mixer.music.pause(); self.paused=True; self.play.setText("▶  Continuar")
            elif self.paused: pygame.mixer.music.unpause(); self.paused=False; self.play.setText("Ⅱ  Pausar")
            else: pygame.mixer.music.load(str(self.current)); pygame.mixer.music.play(); self.playing=True; self.paused=False; self.play.setText("Ⅱ  Pausar")
        except pygame.error as error: self.show_message(QMessageBox.Critical,"No se pudo reproducir",str(error))
    def stop(self):
        if self.audio_ready: pygame.mixer.music.stop()
        self.playing=False; self.paused=False; self.position=0
        if hasattr(self,"play"): self.play.setText("▶  Reproducir")
    def seek(self,seconds):
        if not self.current:return
        if not self.audio_ready:
            try: pygame.mixer.init(); pygame.mixer.music.set_volume(self.volume.value()/100); self.audio_ready=True
            except pygame.error: return
        self.position=max(0,min(self.duration,self.position+seconds));
        try: pygame.mixer.music.load(str(self.current)); pygame.mixer.music.play(start=self.position); self.playing=True; self.paused=False
        except pygame.error: pass
    def seek_slider(self): self.seek(self.progress.value()-self.position)
    def update_progress(self):
        if self.playing and not self.paused and self.audio_ready: self.position=min(self.duration,self.position+0.4); self.ignore_slider=True; self.progress.setValue(int(self.position)); self.ignore_slider=False
    def render_categories(self):
        preserved=1 if hasattr(self,"volume") else 0
        while self.category_box.count()>preserved: self.category_box.takeAt(preserved).widget().deleteLater()
        for i,cat in enumerate(self.categories):
            b=QPushButton(f"{i+1}.  {cat}"); b.setObjectName("categoryButton"); b.clicked.connect(lambda _,c=cat:self.classify(c)); self.category_box.addWidget(b)
    def render_reviewed(self):
        if not hasattr(self,"reviewed_list"): return
        self.reviewed_list.clear()
        for item in reversed(self.reviewed):
            row=QListWidgetItem(f"{item.get('name','Canción')}\n→ {item.get('destination','')}")
            source=Path(item.get("source", ""))
            if source.is_file():
                cover=self.meta(source).get("cover")
                if cover: row.setIcon(QIcon(QPixmap.fromImage(cover).scaled(48,48,Qt.KeepAspectRatio,Qt.SmoothTransformation)))
            self.reviewed_list.addItem(row)
    def manage_categories(self):
        text,ok=QInputDialog.getText(self,"Categorías","Nombres separados por comas:",text=", ".join(self.categories));
        if ok:
            values=[]
            for value in text.split(','):
                value=value.strip()
                if value and value not in values:values.append(value)
            if values:self.categories=values; self.save_config(); self.render_categories()
    def manage_genres(self):
        text,ok=QInputDialog.getText(self,"Géneros","Nombres separados por comas:",text=", ".join(self.genres));
        if ok:
            values=[]
            for value in text.split(','):
                value=value.strip()
                if value and value not in values:values.append(value)
            if values:self.genres=values; self.genre_combo.clear(); self.genre_combo.addItems(values); self.save_config()
    def classify(self,category):
        if not self.current:return
        genre=self.genre_combo.currentText().strip()
        if not genre or not self.library_path.is_dir(): self.show_message(QMessageBox.Warning,"Falta configuración","Selecciona biblioteca y género antes de clasificar."); return
        bpm=self.meta(self.current)["bpm"]
        try:
            import librosa
        except ImportError:
            librosa=None
        if bpm is None and librosa:
            try:
                audio,sr=librosa.load(str(self.current),sr=None,mono=True,duration=90)
                tempo=librosa.beat.beat_track(y=audio,sr=sr)[0]
                bpm=round(float(tempo[0] if hasattr(tempo,"__len__") else tempo))
            except Exception: pass
        folder=f"{(bpm//4)*4}-{(bpm//4)*4+3} BPM" if bpm else "No BPM"
        dest=self.library_path/genre/category/folder/self.current.name
        try:
            # pygame mantiene abierto el archivo que está cargado; hay que
            # liberarlo antes de moverlo, especialmente en Windows.
            self.stop()
            if self.audio_ready:
                try:
                    pygame.mixer.music.unload()
                except pygame.error:
                    pass
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.resolve() != self.current.resolve(): shutil.move(str(self.current),str(dest))
            self.reviewed.append({"source":str(self.current),"name":self.current.name,"genre":genre,"category":category,"bpm":bpm,"destination":str(dest.relative_to(self.library_path))}); self.stop(); self.current=None; self.save_config(); self.load_tracks(); self.status_message(f"Movida a {category}")
        except OSError as error: self.show_message(QMessageBox.Critical,"No se pudo mover",str(error))
    def status_message(self,text): self.status.setText(text) if hasattr(self,"status") else None
    def eventFilter(self,obj,event):
        if isinstance(event,QKeyEvent) and event.type()==QKeyEvent.KeyPress and not event.isAutoRepeat():
            # Los diálogos de edición deben recibir normalmente la barra
            # espaciadora y las demás teclas, sin activar atajos del reproductor.
            if QApplication.activeModalWidget() is not None:
                return super().eventFilter(obj,event)
            if isinstance(obj,(QLineEdit,QTextEdit,QComboBox)):
                return super().eventFilter(obj,event)
            key=event.key()
            if key==Qt.Key_Up:self.list.setCurrentRow(max(0,self.list.currentRow()-1));return True
            if key==Qt.Key_Down:self.list.setCurrentRow(min(len(self.tracks)-1,self.list.currentRow()+1));return True
            if key==Qt.Key_Left:self.seek(-5);return True
            if key==Qt.Key_Right:self.seek(5);return True
            if key==Qt.Key_Space:self.toggle();return True
            if key in (Qt.Key_Delete, Qt.Key_Backspace):self.omit_current();return True
            if Qt.Key_1<=key<=Qt.Key_9 and key-Qt.Key_1<len(self.categories):self.classify(self.categories[key-Qt.Key_1]);return True
        return super().eventFilter(obj,event)
    def closeEvent(self,event): self.stop(); pygame.mixer.quit() if self.audio_ready else None; event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv); app.setWindowIcon(QIcon(QPixmap.fromImage(QImage(str(LOGO)).copy(448,205,384,384)).scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation))) if LOGO.is_file() else None; window=App(); window.show(); sys.exit(app.exec())
