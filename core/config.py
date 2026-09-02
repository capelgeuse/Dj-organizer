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
        ("1", "House · Inicio", "Route 1", None, None),
        ("2", "House · Medio", "Route 2", None, None),
        ("3", "House · Ponchadas", "Route 3", None, None),
        ("4", "Techno · Inicio", "Route 4", None, None),
        ("5", "Techno · Medio", "Route 5", None, None),
        ("6", "Techno · Ponchadas", "Route 6", None, None),
        ("7", "Progressive · Inicio", "Route 7", None, None),
        ("8", "Progressive · Medio", "Route 8", None, None),
        ("9", "Needs Review", "Needs Review", None, None),
    )
    return [
        RoutePreset(route_id, label, destination, category, genre)
        for route_id, label, destination, category, genre in presets
    ]


def _route_to_dict(route: RoutePreset) -> dict[str, object]:
    return route.to_dict()


def _default_document() -> dict[str, Any]:
    return {
        "schemaVersion": 2,
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
                if int(document.get("schemaVersion", 1)) < 2:
                    routes = merged.get("routes", [])
                    for route in routes if isinstance(routes, list) else []:
                        if not isinstance(route, dict):
                            continue
                        destination = str(route.get("relativeDestination", "")).replace("\\", "/")
                        destination = destination.removesuffix("/{bpmBucket}")
                        if "{" in destination or "}" in destination:
                            destination = str(route.get("label", f"Route {route.get('routeId', '')}")).strip()
                        route["relativeDestination"] = destination
                        route["category"] = None
                        route["genre"] = None
                    merged["schemaVersion"] = 2
                    self.write(merged)
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

    def set_route_path(self, route_id: str, path: str, label: str | None = None) -> dict[str, Any]:
        document = self.read()
        root = Path(str(document.get("root", "")).strip()).expanduser().resolve()
        selected = Path(path).expanduser().resolve()
        if not root.is_dir() or root not in selected.parents or selected == root:
            raise ValueError("DESTINATION_OUTSIDE_ROOT")
        relative = selected.relative_to(root).as_posix().rstrip("/")
        routes = list(document.get("routes", []))
        for route in routes:
            if isinstance(route, dict) and str(route.get("routeId")) == route_id:
                route["relativeDestination"] = relative
                route["category"] = None
                route["genre"] = None
                if label is not None and label.strip():
                    route["label"] = label.strip()
                break
        else:
            raise ValueError("INVALID_ROUTE")
        return self.write({**document, "routes": routes})
