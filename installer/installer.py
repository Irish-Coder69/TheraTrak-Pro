from __future__ import annotations

import os
import shutil
import subprocess
import sys
import winreg
import json
import ctypes
from uuid import UUID
from pathlib import Path
from tkinter import Tk, messagebox


APP_NAME = "TheraTrak Pro"
APP_EXE = "TheraTrak Pro.exe"
UNINSTALL_EXE = "TheraTrak Pro Uninstaller.exe"
ICON_FILE = "Theratrak-Pro.ico"
VERSION_FILE = "version.json"


def bundled_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def desktop_dir() -> Path:
    # Resolve real desktop location (works with OneDrive and folder redirection).
    folder_id = UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
    guid_bytes = folder_id.bytes_le

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    guid = GUID(
        int.from_bytes(guid_bytes[0:4], "little"),
        int.from_bytes(guid_bytes[4:6], "little"),
        int.from_bytes(guid_bytes[6:8], "little"),
        (ctypes.c_ubyte * 8).from_buffer_copy(guid_bytes[8:16]),
    )

    path_ptr = ctypes.c_wchar_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(path_ptr),
    )
    if hr == 0 and path_ptr.value:
        desktop = Path(path_ptr.value)
        ctypes.windll.ole32.CoTaskMemFree(path_ptr)
        return desktop
    return Path.home() / "Desktop"


def get_display_version(version_path: Path) -> str:
    if not version_path.exists():
        return "1.0.0"
    try:
        with version_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        major = int(data.get("major", 1))
        minor = int(data.get("minor", 0))
        patch = int(data.get("patch", 0))
        build = int(data.get("build", 1))
        return f"{major}.{minor}.{patch}.{build}"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "1.0.0"


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


def write_uninstall_registry(target: Path, version: str) -> None:
    uninstall_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TheraTrak Pro"
    uninstall_exe = target / UNINSTALL_EXE
    app_exe = target / APP_EXE
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path)
    try:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "TheraTrak")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(app_exe))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    finally:
        winreg.CloseKey(key)


def main() -> int:
    root = Tk()
    root.withdraw()

    source = bundled_dir()
    target = install_dir()
    target.mkdir(parents=True, exist_ok=True)

    for name in (APP_EXE, UNINSTALL_EXE, ICON_FILE, VERSION_FILE):
        src = source / name
        if src.exists():
            shutil.copy2(src, target / name)

    exe_path = target / APP_EXE
    icon_path = target / ICON_FILE

    desktop = desktop_dir()
    start_menu_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    start_menu_dir.mkdir(parents=True, exist_ok=True)

    create_shortcut(desktop / f"{APP_NAME}.lnk", exe_path, icon_path, target)
    create_shortcut(start_menu_dir / f"{APP_NAME}.lnk", exe_path, icon_path, target)
    create_shortcut(start_menu_dir / "Uninstall TheraTrak Pro.lnk", target / UNINSTALL_EXE, icon_path, target)
    write_uninstall_registry(target, get_display_version(target / VERSION_FILE))

    messagebox.showinfo(
        APP_NAME,
        "TheraTrak Pro was installed successfully.\n\nDesktop and Start Menu shortcuts were created.\nAn uninstaller was also registered in Installed Apps.",
    )
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())