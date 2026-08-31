"""Single local JSON configuration authority for the new desktop runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from architecture.contracts import RoutePreset

DEFAULT_CATEGORIES = ("Inicio", "Medio", "Ponchadas")
DEFAULT_GENRES = ("House", "Techno", "Progressive House")


def default_config_path() -> Path:
    override = os.environ.get("CAPELHOUSE_CONFIG")
    if override:
        return Path(override).expanduser()
    app_data = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if app_data:
        return Path(app_data) / "CapelHouse" / "config.json"
    return Path.home() / ".capelhouse" / "config.json"


def default_routes() -> list[RoutePreset]:
    presets = (
        ("1", "House · Inicio", "{genre}/Inicio/{bpmBucket}", "Inicio", "House"),
        ("2", "House · Medio", "{genre}/Medio/{bpmBucket}", "Medio", "House"),
        ("3", "House · Ponchadas", "{genre}/Ponchadas/{bpmBucket}", "Ponchadas", "House"),
        ("4", "Techno · Inicio", "{genre}/Inicio/{bpmBucket}", "Inicio", "Techno"),
        ("5", "Techno · Medio", "{genre}/Medio/{bpmBucket}", "Medio", "Techno"),
        ("6", "Techno · Ponchadas", "{genre}/Ponchadas/{bpmBucket}", "Ponchadas", "Techno"),
        ("7", "Progressive · Inicio", "{genre}/Inicio/{bpmBucket}", "Inicio", "Progressive House"),
        ("8", "Progressive · Medio", "{genre}/Medio/{bpmBucket}", "Medio", "Progressive House"),
        ("9", "Needs Review", "Needs Review/{bpmBucket}", None, None),
    )
    return [
        RoutePreset(route_id, label, destination, category, genre)
        for route_id, label, destination, category, genre in presets
    ]


def _route_to_dict(route: RoutePreset) -> dict[str, object]:
    return route.to_dict()


def _default_document() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "root": "",
        "categories": list(DEFAULT_CATEGORIES),
        "genres": list(DEFAULT_GENRES),
        "routes": [_route_to_dict(route) for route in default_routes()],
        "sort": {"field": "name", "direction": "asc"},
    }


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def read(self) -> dict[str, Any]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(document, dict):
                merged = _default_document()
                merged.update(document)
                return merged
        except (OSError, json.JSONDecodeError):
            pass
        return _default_document()

    def write(self, document: dict[str, Any]) -> dict[str, Any]:
        merged = _default_document()
        merged.update(document)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged

    def set_root(self, root: str) -> dict[str, Any]:
        document = self.read()
        document["root"] = str(Path(root).expanduser())
        return self.write(document)

    def routes(self) -> list[RoutePreset]:
        routes: list[RoutePreset] = []
        for item in self.read().get("routes", []):
            if not isinstance(item, dict):
                continue
            try:
                routes.append(RoutePreset(
                    route_id=str(item["routeId"]),
                    label=str(item["label"]),
                    relative_destination=str(item["relativeDestination"]),
                    category=str(item["category"]) if item.get("category") else None,
                    genre=str(item["genre"]) if item.get("genre") else None,
                ))
            except (KeyError, TypeError):
                continue
        return routes or default_routes()

    def set_routes(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        document = self.read()
        document["routes"] = routes
        return self.write(document)
