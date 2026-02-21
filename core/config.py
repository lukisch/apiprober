"""
ApiProber.core.config -- Konfigurationsmanagement
===================================================
Laedt, validiert und speichert Probe-Konfigurationen.
Pattern: llmauto/core/config.py (DEFAULT + load/save + deepcopy)
"""
import json
from pathlib import Path
from copy import deepcopy

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG = {
    "delay_ms": 500,
    "max_requests": 500,
    "max_depth": 3,
    "timeout_seconds": 15,
    "user_agent": "ApiProber/0.1 (github.com/lukisch; passive-discovery)",
    "respect_robots_txt": True,
    "skip_destructive": True,
    "strategies": ["openapi", "wordlist", "pattern", "response_driven"],
    "auth": {
        "type": "none",
        "value": ""
    },
    "wordlists": [
        "common_rest.txt",
        "swagger_paths.txt",
        "auth_endpoints.txt",
        "admin_paths.txt"
    ],
    "pattern_versions": [1, 2, 3],
    "pattern_resources": [
        "users", "posts", "comments", "items", "products",
        "orders", "categories", "tags", "articles", "pages",
        "search", "settings", "config", "health", "status",
        "albums", "photos", "videos", "contacts", "customers",
        "tickets", "reviews", "collections", "templates"
    ],
    "methods_safe": ["GET", "HEAD", "OPTIONS"],
    "methods_all": ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
    "export_dir": "exports",
    "db_path": "data/api_prober.db"
}


def load_config(config_path=None):
    """Laedt Konfiguration aus JSON-Datei, merged mit Defaults."""
    if config_path is None:
        config_path = BASE_DIR / "config.json"
    else:
        config_path = Path(config_path)

    config = deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        _deep_merge(config, user_config)
    return config


def save_config(config, config_path=None):
    """Speichert Konfiguration als JSON."""
    if config_path is None:
        config_path = BASE_DIR / "config.json"
    else:
        config_path = Path(config_path)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_db_path(config=None):
    """Gibt absoluten Pfad zur DB zurueck."""
    if config is None:
        config = load_config()
    db_rel = config.get("db_path", DEFAULT_CONFIG["db_path"])
    return BASE_DIR / db_rel


def get_export_dir(config=None):
    """Gibt absoluten Pfad zum Export-Verzeichnis zurueck."""
    if config is None:
        config = load_config()
    export_rel = config.get("export_dir", DEFAULT_CONFIG["export_dir"])
    return BASE_DIR / export_rel


def _deep_merge(base, override):
    """Rekursiver Merge: override ueberschreibt base in-place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
