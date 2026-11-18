"""Read-only native-library diagnostic, including from a frozen Windows build."""
import json
from pathlib import Path

from library import Library
from rekordbox_bridge import default_bridge_dir, inspect_connection, inspect_tracks


def create_report(config_path, output_path):
    library = Library(Path(config_path))
    bridge = Path(library.config.get("rekordbox_bridge_dir") or default_bridge_dir())
    report = {
        "connection": inspect_connection(xml_path=bridge / "CapelHouse.xml"),
        "tracks": inspect_tracks(library.tracks),
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0
