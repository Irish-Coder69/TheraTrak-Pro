from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path
from tkinter import Tk, messagebox


APP_NAME = "TheraTrak Pro"
APP_EXE = "TheraTrak Pro.exe"
ICON_FILE = "Theratrak-Pro.ico"


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def desktop_shortcut_candidates() -> list[Path]:
    candidates = [Path.home() / "Desktop"]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        candidates.append(Path(one_drive) / "Desktop")
    seen = set()
    unique = []
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p / f"{APP_NAME}.lnk")
    return unique


def start_menu_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME


def remove_registry_entry() -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TheraTrak Pro"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            winreg.DeleteKey(hive, key_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            pass
        except OSError:
            pass


def remove_shortcuts() -> None:
    for shortcut in desktop_shortcut_candidates():
        try:
            shortcut.unlink(missing_ok=True)
        except OSError:
            pass

    try:
        shutil.rmtree(start_menu_dir(), ignore_errors=True)
    except OSError:
        pass


def stop_running_app() -> None:
    # Best effort: app may be running and lock files in the install directory.
    subprocess.run(
        ["taskkill", "/IM", APP_EXE, "/F"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def schedule_self_delete_folder(target: Path) -> None:
    script_path = Path(tempfile.gettempdir()) / "theratrak_uninstall_cleanup.cmd"
    script = (
        "@echo off\n"
        "cd /d %TEMP%\n"
        "set TARGET=%~1\n"
        "for /L %%i in (1,1,15) do (\n"
        "  rmdir /s /q \"%TARGET%\" >nul 2>&1\n"
        "  if not exist \"%TARGET%\" goto done\n"
        "  ping 127.0.0.1 -n 2 > nul\n"
        ")\n"
        ":done\n"
        "del /f /q \"%~f0\"\n"
    )
    script_path.write_text(script, encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path), str(target)],
        cwd=tempfile.gettempdir(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def main() -> int:
    root = Tk()
    root.withdraw()
    try:
        icon_path = install_dir() / ICON_FILE
        if icon_path.exists():
            root.iconbitmap(default=str(icon_path))
    except Exception:
        pass

    if not messagebox.askyesno(APP_NAME, "Uninstall TheraTrak Pro from this computer?"):
        root.destroy()
        return 0

    target = install_dir()
    stop_running_app()
    remove_shortcuts()
    remove_registry_entry()

    try:
        # In frozen mode this executable is running from the install directory,
        # so defer deleting the folder until after process exit.
        if getattr(sys, "frozen", False):
            schedule_self_delete_folder(target)
        else:
            shutil.rmtree(target, ignore_errors=True)
    except OSError:
        pass

    messagebox.showinfo(APP_NAME, "TheraTrak Pro was uninstalled.")
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
