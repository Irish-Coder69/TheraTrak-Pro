"""Application paths that work in source and packaged builds."""

from pathlib import Path
import sys


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_ROOT = get_app_root()
ICON_FILE = APP_ROOT / "Theratrak-Pro.ico"
VERSION_FILE = APP_ROOT / "version.json"
DB_FILE = APP_ROOT / "theratrak.db"