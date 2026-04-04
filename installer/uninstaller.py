from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import winreg
import ctypes
from uuid import UUID
from pathlib import Path
from tkinter import Tk, messagebox


APP_NAME = "TheraTrak Pro"
APP_EXE = "TheraTrak Pro.exe"


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def desktop_dir() -> Path:
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


def desktop_shortcut() -> Path:
    return desktop_dir() / f"{APP_NAME}.lnk"


def start_menu_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME


def remove_registry_entry() -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TheraTrak Pro"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def remove_shortcuts() -> None:
    try:
        desktop_shortcut().unlink(missing_ok=True)
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
        "ping 127.0.0.1 -n 4 > nul\n"
        f"rmdir /s /q \"{target}\"\n"
        "del /f /q \"%~f0\"\n"
    )
    script_path.write_text(script, encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def main() -> int:
    root = Tk()
    root.withdraw()

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
