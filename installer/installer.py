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
APP_BUNDLE_DIR = "app"
UNINSTALL_CMD = "Uninstall TheraTrak Pro.cmd"
ICON_FILE = "Theratrak-Pro.ico"
VERSION_FILE = "version.json"
LEGACY_START_MENU_FOLDERS = ("Thorough Track Pro", "TheraTrak-Pro")
LEGACY_ROOT_SHORTCUTS = ("TheraTrak Pro.lnk", "Uninstall TheraTrak Pro.lnk")


def bundled_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def start_menu_program_dirs() -> list[Path]:
    candidates = [
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ["ProgramData"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    seen = set()
    unique = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


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


def create_shortcut(
    shortcut_path: Path,
    target_path: Path,
    icon_path: Path,
    working_dir: Path,
    arguments: str = "",
) -> None:
    def _ps_quote(p: Path) -> str:
        return str(p).replace("'", "''")

    if shortcut_path.exists():
        shortcut_path.unlink()

    ps = f"""
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut('{_ps_quote(shortcut_path)}')
$shortcut.TargetPath = '{_ps_quote(target_path)}'
$shortcut.WorkingDirectory = '{_ps_quote(working_dir)}'
$shortcut.IconLocation = '{_ps_quote(icon_path)},0'
$shortcut.Arguments = '{arguments.replace("'", "''")}'
$shortcut.Description = '{APP_NAME}'
$shortcut.Save()
""".strip()
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def write_uninstall_cmd(target: Path) -> Path:
    uninstall_cmd = target / UNINSTALL_CMD
    script = (
        "@echo off\n"
        "setlocal\n"
        "set \"LOG=%TEMP%\\theratrak-uninstall.log\"\n"
        "echo [%date% %time%] Uninstall started>\"%LOG%\"\n"
        "cd /d \"%~dp0\"\n"
        "echo [%date% %time%] Working dir: %cd%>>\"%LOG%\"\n"
        "taskkill /IM \"TheraTrak Pro.exe\" /F >>\"%LOG%\" 2>&1\n"
        "for %%P in (\"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\" \"%ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs\" \"%USERPROFILE%\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\") do (\n"
        "  echo [%date% %time%] Cleaning Programs root: %%~P>>\"%LOG%\"\n"
        "  del /f /q \"%%~P\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\Uninstall TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\TheraTrak Pro\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\Thorough Track Pro\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\TheraTrak-Pro\" >>\"%LOG%\" 2>&1\n"
        ")\n"
        "del /f /q \"%USERPROFILE%\\Desktop\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "if defined OneDrive del /f /q \"%OneDrive%\\Desktop\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "rmdir /s /q \"%LOCALAPPDATA%\\Temp\\TheraTrakUpdates\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%LOCALAPPDATA%\\Temp\\run_theratrak_update.bat\" >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\TheraTrak Pro\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\TheraTrak Pro\" /f >>\"%LOG%\" 2>&1\n"
        "echo [%date% %time%] Refreshing Start menu host>>\"%LOG%\"\n"
        "taskkill /IM StartMenuExperienceHost.exe /F >>\"%LOG%\" 2>&1\n"
        "taskkill /IM explorer.exe /F >>\"%LOG%\" 2>&1\n"
        "start \"\" explorer.exe\n"
        "set \"TARGET=%~dp0\"\n"
        "set \"CLEANUP=%TEMP%\\theratrak_uninstall_cleanup.cmd\"\n"
        ">\"%CLEANUP%\" echo @echo off\n"
        ">>\"%CLEANUP%\" echo set TARGET=%%~1\n"
        ">>\"%CLEANUP%\" echo for /L %%%%i in ^(1,1,20^) do ^(\n"
        ">>\"%CLEANUP%\" echo   rmdir /s /q \"%%TARGET%%\" ^>^>\"%%TEMP%%\\theratrak-uninstall.log\" 2^>^&1\n"
        ">>\"%CLEANUP%\" echo   if not exist \"%%TARGET%%\" goto done\n"
        ">>\"%CLEANUP%\" echo   ping 127.0.0.1 -n 2 ^>nul\n"
        ">>\"%CLEANUP%\" echo ^)\n"
        ">>\"%CLEANUP%\" echo :done\n"
        ">>\"%CLEANUP%\" echo del /f /q \"%%~f0\"\n"
        "start \"\" /min cmd /c \"\"%CLEANUP%\" \"%TARGET%\"\"\n"
        "exit /b 0\n"
    )
    uninstall_cmd.write_text(script, encoding="utf-8", newline="\r\n")
    return uninstall_cmd


def write_uninstall_registry(target: Path, uninstall_cmd: Path, version: str) -> None:
    uninstall_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TheraTrak Pro"
    app_exe = target / APP_EXE
    comspec = Path(os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe"))
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path)
    try:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "TheraTrak")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(app_exe))
        winreg.SetValueEx(
            key,
            "UninstallString",
            0,
            winreg.REG_SZ,
            f'"{comspec}" /c ""{uninstall_cmd}""',
        )
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

    app_bundle = source / APP_BUNDLE_DIR
    if app_bundle.exists() and app_bundle.is_dir():
        for item in app_bundle.iterdir():
            destination = target / item.name
            if item.is_dir():
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)

    for name in (UNINSTALL_EXE, ICON_FILE, VERSION_FILE):
        src = source / name
        if src.exists():
            shutil.copy2(src, target / name)

    exe_path = target / APP_EXE
    uninstaller_path = target / UNINSTALL_EXE
    icon_path = target / ICON_FILE
    uninstall_cmd_path = target / UNINSTALL_CMD

    missing = [
        p.name for p in (exe_path, uninstaller_path, icon_path)
        if not p.exists()
    ]
    if missing:
        messagebox.showerror(APP_NAME, f"Install failed. Missing files: {', '.join(missing)}")
        root.destroy()
        return 1

    uninstall_cmd_path = write_uninstall_cmd(target)

    desktop = desktop_dir()
    programs_dirs = start_menu_program_dirs()
    for programs_dir in programs_dirs:
        for legacy_name in (APP_NAME, *LEGACY_START_MENU_FOLDERS):
            legacy_dir = programs_dir / legacy_name
            if legacy_dir.exists() and legacy_dir.is_dir():
                shutil.rmtree(legacy_dir, ignore_errors=True)
        for shortcut_name in LEGACY_ROOT_SHORTCUTS:
            try:
                (programs_dir / shortcut_name).unlink(missing_ok=True)
            except OSError:
                pass

    start_menu_dir = programs_dirs[0] / APP_NAME
    start_menu_dir.mkdir(parents=True, exist_ok=True)

    create_shortcut(desktop / f"{APP_NAME}.lnk", exe_path, exe_path, target)
    create_shortcut(start_menu_dir / f"{APP_NAME}.lnk", exe_path, exe_path, target)
    create_shortcut(
        start_menu_dir / "Uninstall TheraTrak Pro.lnk",
        Path(os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")),
        uninstaller_path,
        target,
        arguments=f'/c ""{uninstall_cmd_path}""',
    )
    write_uninstall_registry(target, uninstall_cmd_path, get_display_version(target / VERSION_FILE))

    messagebox.showinfo(
        APP_NAME,
        "TheraTrak Pro was installed successfully.\n\nDesktop and Start Menu shortcuts were created.\nAn uninstaller was also registered in Installed Apps.",
    )
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())