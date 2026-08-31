"""Puente JSON-lines de la UI hacia la lógica original de Texto.py."""
import json
import os
import sys

from Texto import AudioPlayer, OrganizadorService


service = OrganizadorService(os.environ.get("CAPELHOUSE_CONFIG"))
player = AudioPlayer()


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            command = request.get("command")
            if command == "ping":
                result = {"ok": True, "ready": True}
            elif command == "library_summary":
                result = {"ok": True, "data": service.summary()}
            elif command == "set_library":
                result = service.set_workspace(request.get("libraryPath", ""))
            elif command == "set_categories":
                result = service.set_categories(request.get("categories", []))
            elif command == "classify_track":
                result = service.classify(request.get("trackPath", ""), request.get("category", ""))
            elif command in {"play", "pause", "resume", "stop", "seek", "seek_relative"}:
                result = player.command(request)
            else:
                result = {"ok": False, "error": "Comando no soportado"}
        except (json.JSONDecodeError, AttributeError, TypeError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
