# CapelHouse 2.1 (Windows)

## Instalación y apertura

El repositorio contiene el código fuente; no incluye el ejecutable. Puedes ejecutar la aplicación con Python o generar una distribución portable siguiendo la sección **Empaquetado opcional**. Para distribuirla, copia la carpeta generada completa, no solo el ejecutable.

Con Python 3.11 o posterior instalado en Windows, ejecuta `Instalar_CapelHouse.bat` y después `Abrir_CapelHouse.bat`. El instalador utiliza `.venv` en la raíz del proyecto; si no existe, reutiliza `Capelhouse\.venv` si está presente o crea el entorno en la raíz. Instala las dependencias de `requirements.txt`, incluido pyrekordbox con su controlador SQLCipher para consultar el estado de Rekordbox, sin cambiar la política de ejecución de PowerShell. El lanzador busca esos entornos en el mismo orden y, si no existen, intenta `py -3` y `python`; en ese caso las dependencias deben estar instaladas en ese Python.

## Uso

Selecciona la carpeta de entrada y la biblioteca de destino; define los géneros, escucha cada pista y selecciona género, estrellas y color. Las estrellas y el color son independientes. Al guardar, se copia el archivo a una carpeta por género sin mover ni modificar el original; no se organiza por BPM ni por categorías de estrellas o color. Conserva estables las rutas de la biblioteca de salida para que los programas DJ encuentren los archivos.

Atajos: Espacio reproduce o pausa; `1` a `5` asignan estrellas; `0` las borra; Enter guarda; flechas izquierda y derecha retroceden o avanzan cinco segundos. Los atajos no se activan mientras se edita texto o hay un diálogo abierto.

Para abrir una biblioteca anterior, usa **Biblioteca → Abrir biblioteca guardada** y selecciona su `configuracion_dj.json` o `library.json`. Si ya existe un `library.json` en esa misma carpeta, se abre ese archivo con prioridad; verifica que sea la biblioteca deseada. La selección cambia la biblioteca activa, no la copia a la ubicación predeterminada: los cambios se guardan en la biblioteca seleccionada (o en `library.json` junto al archivo anterior). Al guardar una configuración anterior se crea un respaldo `.bak`.

Al ejecutar desde el código se utiliza la biblioteca de `%LOCALAPPDATA%\CapelHouse` si ya existe; en caso contrario se busca una configuración anterior en `Capelhouse\configuracion_dj.json`. Los cambios se guardan en `library.json`, sin sobrescribir el archivo anterior. En la versión empaquetada se usa `%LOCALAPPDATA%\CapelHouse` (o la carpeta de usuario si `LOCALAPPDATA` no está definido). El repositorio incluye `configuracion_dj.example.json` como ejemplo vacío e ignora la configuración personal.

La selección de otra biblioteca no cambia la ruta predeterminada para el próximo inicio. Para volver a abrirla, usa el menú de nuevo o inicia el ejecutable con `--config`, indicando su ruta entre comillas:

```bat
Capelhouse\dist\CapelHouse\CapelHouse.exe --config "C:\ruta\a\library.json"
```

## Rekordbox

**Enviar a Rekordbox** publica la biblioteca preparada completa en una ruta estable, `CapelHouse.xml`; los filtros de la vista no limitan el envío. Publicar el XML no importa ni analiza pistas por sí solo.

1. Cierra Rekordbox y pulsa **Configurar conexión** en el diálogo de CapelHouse. Esto configura la ruta del XML, activa el panel XML y el análisis automático, y respalda los ajustes de Rekordbox. Si prefieres configurarlo a mano, copia la ruta del diálogo: en Rekordbox usa **Preferencias → Avanzado → Base de datos → rekordbox xml → Biblioteca importada** y activa **rekordbox xml** en **Preferencias → Vista → Diseño → Navegador multimedia**.
2. Pulsa **Abrir Rekordbox** o usa su acceso directo. En Rekordbox, abre **rekordbox xml → Playlists → CapelHouse** y usa **Importar playlist** para los géneros que quieras añadir a la colección. En envíos posteriores, actualiza el panel XML si sigue mostrando la versión anterior; la ruta no cambia. Si alguna pista nueva no se analiza automáticamente, selecciónala en la colección y usa **Analizar pista** en Rekordbox.
3. Pulsa **Comprobar estado** en el diálogo o **Comprobar estado en Rekordbox** en **Preparadas**. La comprobación de la base de datos es de solo lectura. **Lista** requiere que la pista figure en la colección, que coincida su clasificación (género, estrellas y color) y que existan datos nativos de análisis. **Pendiente de análisis** o **Analizando** no significan que haya terminado; **Revisar clasificación** indica una diferencia. **Sin verificar** no confirma ni descarta la importación. El XML publicado por sí solo no da el estado **Lista**.

Mantén accesibles y estables las rutas del audio. Prueba primero con pistas nuevas: no se garantiza que reimportar actualice estrellas o color de pistas existentes. La exportación manual XML/CSV/M3U8 sigue disponible; importar el M3U8 o arrastrar el audio no transfiere estrellas ni colores.

### Canciones ya importadas, sin estrellas o color

Si **Comprobar estado** indica **Revisar clasificación**, cierra Rekordbox y pulsa **Aplicar clasificación a canciones ya importadas**. Se crea un respaldo cifrado de su base de datos antes de cambiar género, estrellas y color de las rutas coincidentes. Se conserva el análisis, los cues y las playlists. El proceso omite rutas que no estén importadas o tengan duplicados ambiguos y se bloquea si Rekordbox está abierto. Después vuelve a abrir Rekordbox y comprueba el estado. Esta reparación no incorpora archivos nuevos ni sustituye su análisis.

En Windows se detectó Rekordbox 7.2.8 en ejecución, pero no se pudo activar su ventana durante la prueba automatizada. El flujo nativo de importación y análisis no quedó validado de extremo a extremo. Consulta el [manual de Rekordbox 7.2.8](https://cdn.rekordbox.com/files/20251202174516/rekordbox7.2.8_manual_EN.pdf).

## Empaquetado opcional

Para regenerar el paquete desde la raíz del proyecto, instala PyInstaller por separado y ejecuta (ajusta la ruta si utilizas `Capelhouse\.venv`):

```bat
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe -m PyInstaller --distpath Capelhouse\dist --workpath Capelhouse\build Capelhouse\CapelHouse.spec
```

Instala primero las dependencias de `requirements.txt` en el entorno de compilación. PyInstaller no es necesario para ejecutar desde el código. El paquete incluye el lector de estado y el controlador SQLCipher; NumPy y Construct son dependencias de pyrekordbox. No se empaqueta la configuración personal.

## Autoverificación

Desde la raíz del proyecto, ejecuta la versión empaquetada con una carpeta nueva dedicada a la prueba:

```bat
Capelhouse\dist\CapelHouse\CapelHouse.exe --self-test Capelhouse\qa\verificacion
```

La prueba usa audio sintético y comprueba reproducción, guardado por género y exportación XML; también captura la interfaz. Los resultados quedan en `Capelhouse\qa\verificacion\resultado.json` y `CapelHouse.png`, junto con los datos generados. Usa una carpeta de prueba independiente, no una biblioteca personal. La prueba no sustituye la validación en Rekordbox.
