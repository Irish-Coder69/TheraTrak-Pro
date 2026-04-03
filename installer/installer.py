from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import Tk, messagebox


APP_NAME = "TheraTrak Pro"
APP_EXE = "TheraTrak Pro.exe"
ICON_FILE = "Theratrak-Pro.ico"
VERSION_FILE = "version.json"


def bundled_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def create_shortcut(shortcut_path: Path, target_path: Path, icon_path: Path, working_dir: Path) -> None:
    ps = f"""
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut('{shortcut_path}')
$shortcut.TargetPath = '{target_path}'
$shortcut.WorkingDirectory = '{working_dir}'
$shortcut.IconLocation = '{icon_path}'
$shortcut.Save()
""".strip()
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    root = Tk()
    root.withdraw()

    source = bundled_dir()
    target = install_dir()
    target.mkdir(parents=True, exist_ok=True)

    for name in (APP_EXE, ICON_FILE, VERSION_FILE):
        src = source / name
        if src.exists():
            shutil.copy2(src, target / name)

    exe_path = target / APP_EXE
    icon_path = target / ICON_FILE

    desktop_dir = Path.home() / "Desktop"
    start_menu_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    start_menu_dir.mkdir(parents=True, exist_ok=True)

    create_shortcut(desktop_dir / f"{APP_NAME}.lnk", exe_path, icon_path, target)
    create_shortcut(start_menu_dir / f"{APP_NAME}.lnk", exe_path, icon_path, target)

    messagebox.showinfo(
        APP_NAME,
        "TheraTrak Pro was installed successfully.\n\nDesktop and Start Menu shortcuts were created.",
    )
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())