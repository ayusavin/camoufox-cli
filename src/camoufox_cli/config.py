"""Config: read/write ~/.camoufox-cli/config.json"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".camoufox-cli"
CONFIG_PATH = CONFIG_DIR / "config.json"
EXTENSIONS_DIR = CONFIG_DIR / "extensions"
CAPSOLVER_XPI_PATH = EXTENSIONS_DIR / "capsolver.xpi"


def read_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text())
    except Exception:
        pass
    return {}


def write_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def has_capsolver_xpi() -> bool:
    return CAPSOLVER_XPI_PATH.exists()
