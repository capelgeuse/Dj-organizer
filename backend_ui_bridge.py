"""Backend pequeño para la nueva interfaz; conserva el flujo de Texto_punto_cero."""
import base64
import json
import os
import shutil
import sys
from pathlib import Path

from Texto_punto_cero import EXTENSIONES_AUDIO

try:
    import pygame
except ImportError:
    pygame = None
try:
    from mutagen import File as open_metadata
except ImportError:
    open_metadata = None

CONFIG = Path(os.environ.get("CAPELHOUSE_CONFIG", Path(__file__).with_name("configuracion_dj.json")))
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def config_read():
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def config_write(value):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def metadata(path):
    result = {"bpm": None, "genre": "Sin analizar", "duration": "--:--", "cover": None}
    try:
        file = open_metadata(str(path)) if open_metadata else None
        if file:
            seconds = getattr(getattr(file, "info", None), "length", 0)
            if seconds:
                seconds = round(seconds)
                result["duration"] = f"{seconds // 60}:{seconds % 60:02d}"
            pictures = list(getattr(file, "pictures", []) or [])
            if pictures:
                result["cover"] = f"data:{pictures[0].mime};base64,{base64.b64encode(pictures[0].data).decode()}"
            tags = getattr(file, "tags", None) or {}
            for key in ("bpm", "tbpm", "tempo"):
                values = tags.get(key)
                if values:
                    try:
                        result["bpm"] = round(float(str(values[0]).replace(",", ".")))
                        break
                    except ValueError:
                        pass
            if tags.get("genre"):
                result["genre"] = str(tags["genre"][0])
    except (OSError, TypeError, ValueError):
        pass
    if result["cover"] is None:
        for stem in ("cover", "folder", "front", path.stem):
            for extension in IMAGE_EXTENSIONS:
                image = path.parent / f"{stem}{extension}"
                if image.is_file():
                    mime = "image/jpeg" if extension in {".jpg", ".jpeg"} else f"image/{extension[1:]}"
                    result["cover"] = f"data:{mime};base64,{base64.b64encode(image.read_bytes()).decode()}"
                    return result
    return result


def summary():
    cfg = config_read()
    root = Path(cfg.get("entrada", ""))
    categories = cfg.get("categorias", [])
    tracks = []
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in EXTENSIONES_AUDIO:
                relative = path.relative_to(root)
                if not any(part in categories for part in relative.parts[:-1]):
                    tracks.append({"name": path.name, "path": str(path), **metadata(path)})
    tracks.sort(key=lambda item: item["name"].casefold())
    return {"input": cfg.get("entrada", ""), "library": cfg.get("biblioteca", ""), "categories": categories, "tracks": tracks}


def dispatch(request):
    command = request.get("command")
    if command == "ping":
        return {"ok": True}
    if command == "summary":
        return {"ok": True, "data": summary()}
    if command == "set_workspace":
        root = Path(str(request.get("path", "")).strip())
        if not root.is_dir():
            return {"ok": False, "error": "La carpeta no existe."}
        cfg = config_read(); cfg["entrada"] = str(root); cfg["biblioteca"] = str(root); config_write(cfg)
        return {"ok": True}
    if command == "set_categories":
        values, invalid = [], '<>:"/\\|?*'
        for item in request.get("categories", []):
            value = str(item).strip()
            if value and value not in values and value not in {".", ".."} and not any(char in value for char in invalid):
                values.append(value)
        if len(values) != len([str(x).strip() for x in request.get("categories", []) if str(x).strip()]):
            return {"ok": False, "error": "Nombre de categoría no válido o repetido."}
        cfg = config_read(); cfg["categorias"] = values; config_write(cfg)
        root = Path(cfg.get("biblioteca", ""))
        for value in values:
            (root / value).mkdir(parents=True, exist_ok=True)
        return {"ok": True, "categories": values}
    if command == "classify":
        cfg, source = config_read(), Path(request.get("path", "")); category = str(request.get("category", "")).strip()
        if category not in cfg.get("categorias", []): return {"ok": False, "error": "Categoría no configurada."}
        bpm = metadata(source)["bpm"]; folder = f"{(bpm // 4) * 4}-{(bpm // 4) * 4 + 3} BPM" if bpm else "BPM no detectado"
        destination = Path(cfg.get("biblioteca", "")) / category / folder / source.name
        try: destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, destination)
        except OSError as error: return {"ok": False, "error": str(error)}
        return {"ok": True, "destination": str(destination)}
    if command in {"play", "pause", "resume", "stop", "seek"}:
        if pygame is None: return {"ok": False, "error": "pygame no está instalado."}
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init()
            if command == "play": pygame.mixer.music.load(str(request["path"])); pygame.mixer.music.play()
            elif command == "pause": pygame.mixer.music.pause()
            elif command == "resume": pygame.mixer.music.unpause()
            elif command == "stop": pygame.mixer.music.stop()
            else:
                pygame.mixer.music.load(str(request["path"])); pygame.mixer.music.play(start=max(0, float(request.get("position", 0))))
            return {"ok": True}
        except Exception as error: return {"ok": False, "error": str(error)}
    return {"ok": False, "error": "Comando no soportado."}


for line in sys.stdin:
    try: result = dispatch(json.loads(line))
    except Exception as error: result = {"ok": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False), flush=True)
