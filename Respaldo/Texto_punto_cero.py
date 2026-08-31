"""Organizador musical sencillo para sets de DJ.

Flujo: elegir una carpeta de entrada, escuchar una canción y clasificarla
como Inicio, Medio o Ponchadas. Los archivos se COPIAN para conservar los
originales descargados o copiados desde la USB.
"""

from pathlib import Path
import os
import json
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

try:
    import pygame
except ImportError:
    pygame = None

try:
    import librosa
except ImportError:
    librosa = None

try:
    from mutagen import File as abrir_metadata, MutagenError
except ImportError:
    abrir_metadata = None
    MutagenError = Exception


EXTENSIONES_AUDIO = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
CARPETAS_SET = ("Inicio", "Medio", "Ponchadas")
GENEROS_PREDETERMINADOS = ("House", "Techno", "Hip Hop", "Reggaeton", "Pop")
ARCHIVO_CONFIGURACION = Path(__file__).with_name("configuracion_dj.json")


class OrganizadorDJ(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Organizador DJ")
        self.geometry("900x720")
        self.minsize(720, 600)

        configuracion_guardada = self._leer_configuracion()
        self.carpeta_entrada = tk.StringVar(value=configuracion_guardada.get("entrada", ""))
        self.carpeta_biblioteca = tk.StringVar(
            value=configuracion_guardada.get("biblioteca", str(Path.home() / "Musica DJ"))
        )
        self.estado = tk.StringVar(value="Elige una carpeta de entrada para comenzar.")
        self.generos = configuracion_guardada.get("generos", [])
        self.categorias = configuracion_guardada.get("categorias", list(CARPETAS_SET))
        self.genero_actual = tk.StringVar()
        self.bpm_actual = tk.StringVar(value="BPM: sin analizar")
        self.canciones = []
        self.cancion_actual = None
        self.bpm_detectado = None
        self.reproduciendo = False
        self.pausado = False
        self.duracion_actual = 0
        self.posicion_base = 0
        self.actualizando_barra = False

        if not configuracion_guardada.get("generos") and not self._configurar_biblioteca():
            self.destroy()
            return

        if pygame:
            pygame.mixer.init()

        self._crear_interfaz()
        self.bind_all("<KeyPress>", self._manejar_atajo)
        self.cambiar_volumen(self.volumen.get())
        if Path(self.carpeta_entrada.get()).is_dir():
            self.cargar_canciones()
        self.after(500, self._actualizar_reproductor)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _configurar_biblioteca(self):
        configuracion = tk.Toplevel(self)
        configuracion.title("Configuración de biblioteca DJ")
        configuracion.geometry("560x460")
        configuracion.resizable(False, False)
        configuracion.transient(self)
        configuracion.deiconify()
        configuracion.grab_set()
        configuracion.lift()
        configuracion.focus_force()

        ttk.Label(
            configuracion,
            text="Elige dónde guardar tu música y define tus géneros.",
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=20, pady=(18, 12))
        ttk.Label(
            configuracion,
            text="Puedes elegir una USB o un disco externo. Se crearán carpetas para cada género y nivel.",
            wraplength=500,
        ).pack(padx=20, pady=(0, 14))

        destino = ttk.Frame(configuracion)
        destino.pack(fill="x", padx=20)
        ttk.Label(destino, text="Carpeta principal:").pack(anchor="w")
        entrada_destino = ttk.Entry(destino, textvariable=self.carpeta_biblioteca)
        entrada_destino.pack(side="left", fill="x", expand=True, pady=(5, 14))

        def elegir_destino():
            carpeta = filedialog.askdirectory(
                parent=configuracion,
                title="Elige dónde guardar la biblioteca DJ",
            )
            if carpeta:
                self.carpeta_biblioteca.set(carpeta)

        ttk.Button(destino, text="Examinar", command=elegir_destino).pack(side="left", padx=(8, 0), pady=(5, 14))

        ttk.Label(configuracion, text="Géneros:").pack(anchor="w", padx=20)
        generos_lista = tk.Listbox(configuracion, height=8, exportselection=False)
        generos_lista.pack(fill="both", expand=True, padx=20, pady=(5, 8))
        generos_iniciales = self.generos or self._descubrir_generos(Path(self.carpeta_biblioteca.get())) or list(GENEROS_PREDETERMINADOS)
        for genero in generos_iniciales:
            generos_lista.insert(tk.END, genero)

        gestion_generos = ttk.Frame(configuracion)
        gestion_generos.pack(fill="x", padx=20)
        nuevo_genero = ttk.Entry(gestion_generos)
        nuevo_genero.pack(side="left", fill="x", expand=True)

        def agregar_genero(_evento=None):
            genero = nuevo_genero.get().strip()
            if genero and genero not in generos_lista.get(0, tk.END):
                generos_lista.insert(tk.END, genero)
                nuevo_genero.delete(0, tk.END)

        def quitar_genero():
            seleccion = generos_lista.curselection()
            if seleccion:
                generos_lista.delete(seleccion[0])

        nuevo_genero.bind("<Return>", agregar_genero)
        ttk.Button(gestion_generos, text="Agregar", command=agregar_genero).pack(side="left", padx=(8, 0))
        ttk.Button(gestion_generos, text="Quitar seleccionado", command=quitar_genero).pack(side="left", padx=(8, 0))

        resultado = {"aceptado": False}

        def crear_estructura():
            ruta = Path(self.carpeta_biblioteca.get().strip())
            generos = [genero.strip() for genero in generos_lista.get(0, tk.END) if genero.strip()]
            caracteres_invalidos = '<>:"/\\|?*'
            if not str(ruta):
                messagebox.showwarning("Falta la carpeta", "Elige una carpeta principal.", parent=configuracion)
                return
            if not generos:
                messagebox.showwarning("Faltan géneros", "Agrega al menos un género.", parent=configuracion)
                return
            if any(any(caracter in genero for caracter in caracteres_invalidos) for genero in generos):
                messagebox.showwarning("Nombre no válido", "Los géneros no pueden contener \\ / : * ? \" < > o |.", parent=configuracion)
                return
            try:
                for genero in generos:
                    for categoria in self.categorias:
                        (ruta / genero / categoria).mkdir(parents=True, exist_ok=True)
            except OSError as error:
                messagebox.showerror("No se pudo crear la estructura", str(error), parent=configuracion)
                return
            self.generos = generos
            self.genero_actual.set(generos[0])
            self._guardar_configuracion(ruta, generos)
            resultado["aceptado"] = True
            configuracion.destroy()

        def cancelar():
            configuracion.destroy()

        configuracion.protocol("WM_DELETE_WINDOW", cancelar)
        botones = ttk.Frame(configuracion)
        botones.pack(fill="x", padx=20, pady=16)
        ttk.Button(botones, text="Crear biblioteca", command=crear_estructura).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=cancelar).pack(side="right", padx=(0, 8))
        entrada_destino.focus_set()
        self.wait_window(configuracion)
        return resultado["aceptado"]

    @staticmethod
    def _leer_configuracion():
        try:
            with ARCHIVO_CONFIGURACION.open("r", encoding="utf-8") as archivo:
                configuracion = json.load(archivo)
            if Path(configuracion.get("biblioteca", "")).is_dir():
                return configuracion
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return {}

    @staticmethod
    def _descubrir_generos(ruta):
        if not ruta.is_dir():
            return []
        if all((ruta / nivel).is_dir() for nivel in CARPETAS_SET):
            return [ruta.name]
        return sorted(
            (carpeta.name for carpeta in ruta.iterdir() if carpeta.is_dir()),
            key=str.casefold,
        )

    def _guardar_configuracion(self, ruta, generos):
        try:
            with ARCHIVO_CONFIGURACION.open("w", encoding="utf-8") as archivo:
                json.dump(
                    {
                        "biblioteca": str(ruta),
                        "entrada": self.carpeta_entrada.get(),
                        "generos": generos,
                        "categorias": self.categorias,
                    },
                    archivo,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def _crear_interfaz(self):
        barra_menu = tk.Menu(self)
        menu_archivo = tk.Menu(barra_menu, tearoff=False)
        menu_archivo.add_command(label="Agregar Genero", command=self.agregar_genero)
        menu_archivo.add_command(label="Administrar categorias", command=self.administrar_categorias)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self._cerrar)
        barra_menu.add_cascade(label="Archivo", menu=menu_archivo)
        self.config(menu=barra_menu)

        configuracion = ttk.LabelFrame(self, text="Carpetas")
        configuracion.pack(fill="x", padx=14, pady=(14, 8))

        ttk.Label(configuracion, text="Entrada:").grid(row=0, column=0, padx=8, pady=7, sticky="w")
        ttk.Entry(configuracion, textvariable=self.carpeta_entrada).grid(row=0, column=1, padx=4, pady=7, sticky="ew")
        ttk.Button(configuracion, text="Elegir carpeta", command=self.elegir_entrada).grid(row=0, column=2, padx=8, pady=7)

        ttk.Label(configuracion, text="Biblioteca:").grid(row=1, column=0, padx=8, pady=7, sticky="w")
        ttk.Entry(configuracion, textvariable=self.carpeta_biblioteca).grid(row=1, column=1, padx=4, pady=7, sticky="ew")
        ttk.Button(configuracion, text="Elegir carpeta", command=self.elegir_biblioteca).grid(row=1, column=2, padx=8, pady=7)
        configuracion.columnconfigure(1, weight=1)

        principal = ttk.PanedWindow(self, orient="horizontal")
        principal.pack(fill="both", expand=True, padx=14, pady=8)

        panel_lista = ttk.LabelFrame(principal, text="Canciones por revisar")
        panel_lista.columnconfigure(0, weight=1)
        panel_lista.rowconfigure(0, weight=1)
        self.lista = tk.Listbox(panel_lista, activestyle="dotbox", font=("Segoe UI", 11), selectmode="single")
        self.lista.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scrollbar = ttk.Scrollbar(panel_lista, orient="vertical", command=self.lista.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.lista.configure(yscrollcommand=scrollbar.set)
        self.lista.bind("<<ListboxSelect>>", self.seleccionar_cancion)
        self.lista.bind("<Left>", self._manejar_atajo)
        self.lista.bind("<Right>", self._manejar_atajo)
        ttk.Button(panel_lista, text="Actualizar lista", command=self.cargar_canciones).grid(row=1, column=0, columnspan=2, pady=(0, 8))
        principal.add(panel_lista, weight=3)

        panel_acciones = ttk.LabelFrame(principal, text="Escuchar y clasificar")
        panel_acciones.columnconfigure(0, weight=1)
        ttk.Label(panel_acciones, text="Selecciona una canción y escúchala antes de enviarla a su carpeta.", wraplength=280).grid(row=0, column=0, padx=20, pady=(28, 18))
        self.nombre_cancion = ttk.Label(panel_acciones, text="Ninguna canción seleccionada", wraplength=280, justify="center")
        self.nombre_cancion.grid(row=1, column=0, padx=20, pady=8)
        self.tiempo_actual = ttk.Label(panel_acciones, text="00:00 / 00:00")
        self.tiempo_actual.grid(row=2, column=0, pady=(0, 4))
        self.barra_posicion = ttk.Scale(panel_acciones, from_=0, to=1)
        self.barra_posicion.bind("<Button-1>", self._mover_barra_con_mouse)
        self.barra_posicion.bind("<B1-Motion>", self._mover_barra_con_mouse)
        self.barra_posicion.bind("<ButtonRelease-1>", self._buscar_posicion)
        self.barra_posicion.grid(row=3, column=0, sticky="ew", padx=25)
        controles = ttk.Frame(panel_acciones)
        controles.grid(row=4, column=0, pady=12)
        self.boton_play = ttk.Button(controles, text="▶ Reproducir", command=self.reproducir)
        self.boton_play.grid(row=0, column=0, padx=4)
        self.boton_pausa = ttk.Button(controles, text="⏸ Pausa", command=self.pausar)
        self.boton_pausa.grid(row=0, column=1, padx=4)
        ttk.Button(controles, text="■ Detener", command=self.detener).grid(row=0, column=2, padx=4)

        saltos = ttk.Frame(panel_acciones)
        saltos.grid(row=5, column=0, pady=(0, 10))
        self._crear_control_salto(saltos, "Rewind 5 s", -5).grid(row=0, column=0, padx=3)
        self._crear_control_salto(saltos, "Adelantar 5 s", 5).grid(row=0, column=1, padx=3)
        ttk.Button(saltos, text="Anterior", command=self.pista_anterior).grid(row=0, column=2, padx=3)
        ttk.Button(saltos, text="Siguiente", command=self.siguiente_pista).grid(row=0, column=3, padx=3)

        ttk.Label(panel_acciones, text="Volumen").grid(row=6, column=0, pady=(0, 2))
        self.volumen = ttk.Scale(panel_acciones, from_=0, to=1, value=0.8, command=self.cambiar_volumen)
        self.volumen.grid(row=7, column=0, sticky="ew", padx=55)

        ttk.Separator(panel_acciones).grid(row=8, column=0, sticky="ew", padx=20, pady=20)
        ttk.Label(panel_acciones, text="Enviar a:").grid(row=9, column=0, pady=(0, 8))
        ttk.Label(panel_acciones, text="Género:").grid(row=10, column=0, pady=(0, 4))
        self.selector_genero = ttk.Combobox(panel_acciones, textvariable=self.genero_actual, values=self.generos, state="readonly")
        self.selector_genero.grid(
            row=11, column=0, sticky="ew", padx=55, pady=(0, 8)
        )
        ttk.Label(panel_acciones, textvariable=self.bpm_actual).grid(row=12, column=0, pady=(0, 8))
        self.panel_categorias = ttk.Frame(panel_acciones)
        self.panel_categorias.grid(row=13, column=0, sticky="ew", padx=55, pady=5)
        self._actualizar_botones_categorias()
        principal.add(panel_acciones, weight=2)
        ttk.Label(self, textvariable=self.estado, relief="sunken", anchor="w").pack(fill="x", padx=14, pady=(0, 14))

    def _actualizar_botones_categorias(self):
        for widget in self.panel_categorias.winfo_children():
            widget.destroy()
        for categoria in self.categorias:
            ttk.Button(
                self.panel_categorias,
                text=categoria,
                command=lambda c=categoria: self.clasificar(c),
            ).pack(fill="x", pady=3)

    def _crear_control_salto(self, padre, texto, segundos):
        boton = ttk.Button(padre, text=texto)
        temporizador = {"id": None}

        def clic_simple(_evento=None):
            temporizador["id"] = self.after(250, lambda: self.saltar(segundos))

        def doble_clic(_evento=None):
            if temporizador["id"] is not None:
                self.after_cancel(temporizador["id"])
                temporizador["id"] = None
            self.saltar(segundos * 2)

        boton.bind("<Button-1>", clic_simple)
        boton.bind("<Double-Button-1>", doble_clic)
        return boton

    @staticmethod
    def _formatear_tiempo(segundos):
        segundos = max(0, int(segundos))
        return f"{segundos // 60:02d}:{segundos % 60:02d}"

    def _manejar_atajo(self, evento):
        if isinstance(evento.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Spinbox)):
            return
        tecla = evento.keysym.lower()
        acciones = {
            "w": lambda: self.pista_anterior(),
            "s": lambda: self.siguiente_pista(),
            "left": lambda: self.saltar(-5),
            "right": lambda: self.saltar(5),
            "space": self._alternar_reproduccion,
        }
        accion = acciones.get(tecla)
        if accion:
            accion()
            return "break"

    def _alternar_reproduccion(self):
        if self.reproduciendo:
            self.pausar()
        else:
            self.reproducir()

    def _obtener_duracion(self, ruta):
        try:
            if abrir_metadata:
                archivo = abrir_metadata(str(ruta))
                if archivo and archivo.info and archivo.info.length:
                    return archivo.info.length
        except (OSError, MutagenError):
            pass
        return 0

    def _actualizar_reproductor(self):
        if self.reproduciendo and not self.pausado and pygame:
            posicion = self.posicion_base + max(0, pygame.mixer.music.get_pos()) / 1000
            if self.duracion_actual:
                posicion = min(posicion, self.duracion_actual)
                self.actualizando_barra = True
                self.barra_posicion.set(posicion)
                self.actualizando_barra = False
            self.tiempo_actual.configure(text=f"{self._formatear_tiempo(posicion)} / {self._formatear_tiempo(self.duracion_actual)}")
        self.after(500, self._actualizar_reproductor)

    def mover_posicion(self, valor):
        if self.actualizando_barra or not self.cancion_actual or not pygame or not self.duracion_actual:
            return
        posicion = min(float(valor), self.duracion_actual)
        try:
            pygame.mixer.music.play(start=posicion)
            self.posicion_base = posicion
            self.reproduciendo = True
            self.pausado = False
        except (pygame.error, TypeError):
            pass

    def _buscar_posicion(self, _evento=None):
        self.mover_posicion(self.barra_posicion.get())

    def _mover_barra_con_mouse(self, evento):
        if not self.duracion_actual:
            return "break"
        ancho = max(1, self.barra_posicion.winfo_width())
        posicion = max(0, min(1, evento.x / ancho)) * self.duracion_actual
        self.barra_posicion.set(posicion)
        return "break"

    def saltar(self, segundos):
        if not self.cancion_actual or not pygame or not self.duracion_actual:
            return
        posicion = self.posicion_base + max(0, pygame.mixer.music.get_pos()) / 1000
        nueva_posicion = max(0, min(self.duracion_actual, posicion + segundos))
        try:
            pygame.mixer.music.play(start=nueva_posicion)
            self.posicion_base = nueva_posicion
            self.reproduciendo = True
            self.pausado = False
        except (pygame.error, TypeError):
            pass

    def pausar(self):
        if not pygame or not self.reproduciendo:
            return
        if self.pausado:
            pygame.mixer.music.unpause()
            self.pausado = False
            self.boton_pausa.configure(text="⏸ Pausa")
        else:
            pygame.mixer.music.pause()
            self.pausado = True
            self.boton_pausa.configure(text="▶ Continuar")

    def cambiar_volumen(self, valor):
        if pygame:
            pygame.mixer.music.set_volume(float(valor))

    def seleccionar_indice(self, indice):
        if not self.canciones:
            return
        indice = max(0, min(len(self.canciones) - 1, indice))
        self.lista.selection_clear(0, tk.END)
        self.lista.selection_set(indice)
        self.lista.see(indice)
        self.seleccionar_cancion()

    def pista_anterior(self):
        seleccion = self.lista.curselection()
        self.seleccionar_indice((seleccion[0] if seleccion else 0) - 1)

    def siguiente_pista(self):
        seleccion = self.lista.curselection()
        self.seleccionar_indice((seleccion[0] if seleccion else -1) + 1)

    def agregar_genero(self):
        dialogo = tk.Toplevel(self)
        dialogo.title("Agregar Genero")
        dialogo.geometry("390x150")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()

        ttk.Label(dialogo, text="Nombre del nuevo genero:").pack(anchor="w", padx=20, pady=(20, 6))
        entrada = ttk.Entry(dialogo)
        entrada.pack(fill="x", padx=20)

        def guardar():
            genero = entrada.get().strip()
            caracteres_invalidos = '<>:"/\\|?*'
            if not genero:
                messagebox.showwarning("Falta el genero", "Escribe un nombre.", parent=dialogo)
                return
            if any(caracter in genero for caracter in caracteres_invalidos):
                messagebox.showwarning("Nombre no valido", "El nombre contiene caracteres no permitidos.", parent=dialogo)
                return
            if genero.casefold() in {existente.casefold() for existente in self.generos}:
                messagebox.showwarning("Genero existente", "Ese genero ya esta registrado.", parent=dialogo)
                return
            ruta = Path(self.carpeta_biblioteca.get()) / genero
            try:
                for categoria in self.categorias:
                    (ruta / categoria).mkdir(parents=True, exist_ok=True)
                self.generos.append(genero)
                self.selector_genero.configure(values=self.generos)
                self.genero_actual.set(genero)
                self._guardar_configuracion(Path(self.carpeta_biblioteca.get()), self.generos)
                self.estado.set(f"Genero agregado: {genero}")
                dialogo.destroy()
            except OSError as error:
                messagebox.showerror("No se pudo crear el genero", str(error), parent=dialogo)

        botones = ttk.Frame(dialogo)
        botones.pack(fill="x", padx=20, pady=18)
        ttk.Button(botones, text="Agregar", command=guardar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=dialogo.destroy).pack(side="right", padx=(0, 8))
        entrada.focus_set()
        dialogo.bind("<Return>", lambda _evento: guardar())

    def administrar_categorias(self):
        dialogo = tk.Toplevel(self)
        dialogo.title("Administrar categorias")
        dialogo.geometry("600x400")
        dialogo.minsize(500, 340)
        dialogo.resizable(True, True)
        dialogo.transient(self)
        dialogo.grab_set()

        ttk.Label(dialogo, text="Categorias para organizar tus canciones:").pack(
            anchor="w", padx=20, pady=(18, 6)
        )
        categorias_lista = tk.Listbox(dialogo, height=9, exportselection=False)
        categorias_lista.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        for categoria in self.categorias:
            categorias_lista.insert(tk.END, categoria)
        cambios_nombres = {}

        gestion = ttk.Frame(dialogo)
        gestion.pack(fill="x", padx=20)
        nueva_categoria = ttk.Entry(gestion)
        nueva_categoria.pack(fill="x", expand=True)

        def agregar(_evento=None):
            categoria = nueva_categoria.get().strip()
            existentes = categorias_lista.get(0, tk.END)
            if categoria and categoria.casefold() not in {item.casefold() for item in existentes}:
                categorias_lista.insert(tk.END, categoria)
                nueva_categoria.delete(0, tk.END)

        def quitar():
            seleccion = categorias_lista.curselection()
            if not seleccion:
                return
            categoria = categorias_lista.get(seleccion[0])
            if not messagebox.askyesno(
                "Quitar categoria",
                f"¿Quitar '{categoria}' de las opciones? Sus archivos no se borraran.",
                parent=dialogo,
            ):
                return
            categorias_lista.delete(seleccion[0])
            cambios_nombres.pop(categoria, None)

        def renombrar():
            seleccion = categorias_lista.curselection()
            nombre = nueva_categoria.get().strip()
            existentes = categorias_lista.get(0, tk.END)
            if not seleccion or not nombre:
                return
            if any(
                indice != seleccion[0] and categoria.casefold() == nombre.casefold()
                for indice, categoria in enumerate(existentes)
            ):
                messagebox.showwarning("Categoria existente", "Ese nombre ya esta registrado.", parent=dialogo)
                return
            categoria_anterior = existentes[seleccion[0]]
            origen = next(
                (clave for clave, valor in cambios_nombres.items() if valor == categoria_anterior),
                categoria_anterior,
            )
            cambios_nombres.pop(origen, None)
            cambios_nombres[origen] = nombre
            categorias_lista.delete(seleccion[0])
            categorias_lista.insert(seleccion[0], nombre)
            categorias_lista.selection_set(seleccion[0])
            nueva_categoria.delete(0, tk.END)

        nueva_categoria.bind("<Return>", agregar)
        acciones = ttk.Frame(gestion)
        acciones.pack(fill="x", pady=(8, 0))
        ttk.Button(acciones, text="Agregar", command=agregar).pack(side="left")
        ttk.Button(acciones, text="Renombrar seleccionada", command=renombrar).pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Quitar seleccionada", command=quitar).pack(side="left", padx=(8, 0))

        def guardar():
            categorias = [categoria.strip() for categoria in categorias_lista.get(0, tk.END) if categoria.strip()]
            caracteres_invalidos = '<>:"/\\|?*'
            if not categorias:
                messagebox.showwarning("Faltan categorias", "Agrega al menos una categoria.", parent=dialogo)
                return
            if any(any(caracter in categoria for caracter in caracteres_invalidos) for categoria in categorias):
                messagebox.showwarning(
                    "Nombre no valido",
                    "Las categorias no pueden contener \\ / : * ? \" < > o |.",
                    parent=dialogo,
                )
                return
            ruta = Path(self.carpeta_biblioteca.get())
            try:
                for categoria_anterior, categoria_nueva in cambios_nombres.items():
                    if categoria_anterior == categoria_nueva:
                        continue
                    for genero in self.generos:
                        origen = ruta / genero / categoria_anterior
                        destino = ruta / genero / categoria_nueva
                        if origen.is_dir() and destino.exists():
                            raise OSError(
                                f"Ya existe la carpeta '{categoria_nueva}' para el genero '{genero}'."
                            )
                        if origen.is_dir():
                            origen.rename(destino)
                for genero in self.generos:
                    for categoria in categorias:
                        (ruta / genero / categoria).mkdir(parents=True, exist_ok=True)
            except OSError as error:
                messagebox.showerror("No se pudieron crear las categorias", str(error), parent=dialogo)
                return
            self.categorias = categorias
            self._guardar_configuracion(ruta, self.generos)
            self._actualizar_botones_categorias()
            self.estado.set("Categorias actualizadas.")
            dialogo.destroy()

        botones = ttk.Frame(dialogo)
        botones.pack(fill="x", padx=20, pady=16)
        ttk.Button(botones, text="Guardar", command=guardar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=dialogo.destroy).pack(side="right", padx=(0, 8))
        nueva_categoria.focus_set()

    def elegir_entrada(self):
        carpeta = filedialog.askdirectory(title="Selecciona USB, Descargas o carpeta de entrada")
        if carpeta:
            self.carpeta_entrada.set(carpeta)
            self._guardar_configuracion(Path(self.carpeta_biblioteca.get()), self.generos)
            self.cargar_canciones()

    def elegir_biblioteca(self):
        carpeta = filedialog.askdirectory(title="Selecciona dónde guardar tu biblioteca DJ")
        if carpeta:
            self.carpeta_biblioteca.set(carpeta)
            self._guardar_configuracion(Path(carpeta), self.generos)

    def cargar_canciones(self):
        entrada = Path(self.carpeta_entrada.get())
        if not entrada.is_dir():
            self.estado.set("La carpeta de entrada no es válida.")
            return
        self.canciones = sorted((p for p in entrada.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES_AUDIO), key=lambda p: p.name.lower())
        self.lista.delete(0, tk.END)
        for cancion in self.canciones:
            self.lista.insert(tk.END, cancion.name)
        self.estado.set(f"{len(self.canciones)} canción(es) encontradas.")

    def seleccionar_cancion(self, _evento=None):
        seleccion = self.lista.curselection()
        if seleccion:
            cancion_seleccionada = self.canciones[seleccion[0]]
            if cancion_seleccionada != self.cancion_actual:
                self.detener()
            self.cancion_actual = cancion_seleccionada
            self.bpm_detectado = None
            self.duracion_actual = self._obtener_duracion(self.cancion_actual)
            self.posicion_base = 0
            self.barra_posicion.configure(to=max(1, self.duracion_actual))
            self.barra_posicion.set(0)
            self.tiempo_actual.configure(text=f"00:00 / {self._formatear_tiempo(self.duracion_actual)}")
            self.nombre_cancion.configure(text=self.cancion_actual.name)
            self.bpm_actual.set("BPM: pendiente de clasificación")
            self.estado.set(f"Lista para escuchar: {self.cancion_actual.name}")

    def analizar_bpm(self):
        if not self.cancion_actual:
            return
        try:
            bpm = self._leer_bpm_metadata(self.cancion_actual)
            origen = "metadata"
            if bpm is None:
                if not librosa:
                    raise RuntimeError("no hay BPM en metadata y falta instalar librosa")
                audio, frecuencia = librosa.load(str(self.cancion_actual), sr=None, mono=True, duration=90)
                tempo, _ = librosa.beat.beat_track(y=audio, sr=frecuencia)
                bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
                origen = "análisis de audio"
            if bpm <= 0:
                raise ValueError("No se detectó un BPM válido")
            self.bpm_detectado = round(bpm)
            self.bpm_actual.set(f"BPM: {self.bpm_detectado} ({origen}) | Rango: {self._rango_bpm(self.bpm_detectado)}")
            self.estado.set(f"Lista para escuchar: {self.cancion_actual.name}")
        except (OSError, ValueError, RuntimeError, MutagenError) as error:
            self.bpm_detectado = None
            self.bpm_actual.set("BPM: no se pudo analizar")
            self.estado.set(f"No se pudo analizar el BPM: {error}")

    @staticmethod
    def _leer_bpm_metadata(ruta):
        if not abrir_metadata:
            return None
        archivo = abrir_metadata(str(ruta), easy=True)
        if not archivo or not archivo.tags:
            return None
        for clave in ("bpm", "tbpm", "tempo"):
            valores = archivo.tags.get(clave)
            if valores:
                try:
                    return float(str(valores[0]).replace(",", "."))
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _rango_bpm(bpm):
        inicio = (bpm // 4) * 4
        return f"{inicio}-{inicio + 3} BPM"

    def reproducir(self):
        if not self.cancion_actual:
            messagebox.showinfo("Selecciona una canción", "Elige una canción de la lista primero.")
            return
        if not pygame:
            messagebox.showerror("Falta una dependencia", "Instala pygame con: pip install pygame")
            return
        try:
            pygame.mixer.music.load(str(self.cancion_actual))
            pygame.mixer.music.play()
            self.reproduciendo = True
            self.pausado = False
            self.posicion_base = 0
            self.boton_play.configure(text="▶ Reproduciendo")
            self.estado.set(f"Reproduciendo: {self.cancion_actual.name}")
        except pygame.error as error:
            messagebox.showerror("No se pudo reproducir", f"Formato no compatible o archivo dañado.\n\n{error}")

    def detener(self):
        if pygame:
            pygame.mixer.music.stop()
        self.reproduciendo = False
        self.pausado = False
        self.posicion_base = 0
        self.boton_play.configure(text="▶ Reproducir")
        self.boton_pausa.configure(text="⏸ Pausa")

    def clasificar(self, carpeta):
        if not self.cancion_actual:
            messagebox.showinfo("Selecciona una canción", "Elige una canción de la lista primero.")
            return
        if self.bpm_detectado is None:
            self.analizar_bpm()
        if self.bpm_detectado is None:
            messagebox.showwarning("BPM no disponible", "No se pudo analizar el BPM de esta canción.")
            return
        rango_bpm = self._rango_bpm(self.bpm_detectado)
        biblioteca = Path(self.carpeta_biblioteca.get())
        genero = self.genero_actual.get()
        raiz_genero = biblioteca if biblioteca.name.casefold() == genero.casefold() else biblioteca / genero
        destino = raiz_genero / carpeta / rango_bpm
        destino.mkdir(parents=True, exist_ok=True)
        ruta_destino = destino / self.cancion_actual.name
        if ruta_destino.exists():
            respuesta = messagebox.askyesno("Archivo existente", f"Ya existe '{ruta_destino.name}'. ¿Quieres reemplazarlo?")
            if not respuesta:
                return
        try:
            shutil.copy2(self.cancion_actual, ruta_destino)
            self.detener()
            self.estado.set(f"Copiada a {carpeta}: {self.cancion_actual.name}")
            indice = self.canciones.index(self.cancion_actual)
            self.lista.delete(indice)
            self.canciones.pop(indice)
            self.cancion_actual = None
            self.nombre_cancion.configure(text="Ninguna canción seleccionada")
        except OSError as error:
            messagebox.showerror("No se pudo copiar", str(error))

    def _cerrar(self):
        self.detener()
        if pygame:
            pygame.quit()
        self.destroy()


if __name__ == "__main__":
    OrganizadorDJ().mainloop()
