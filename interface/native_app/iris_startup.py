"""Optional per-user Iris startup. Never silently enable Windows autorun.

Downloading a file cannot run software: the user must explicitly execute the
installer. The installer launches once after consent; logon startup is optional.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


class StartupError(RuntimeError):
    pass


def startup_supported() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def startup_command(executable: str | Path) -> str:
    path = Path(executable).resolve()
    if path.name.lower() != "genesis.exe":
        raise StartupError("O início automático exige Genesis.exe instalado.")
    return '"' + str(path) + '" --mascot-only'


def is_startup_enabled() -> bool:
    if not startup_supported():
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        )
        with key:
            actual, _ = winreg.QueryValueEx(key, "GenesisIrisMascot")
        return str(actual) == startup_command(sys.executable)
    except (OSError, StartupError):
        return False


def set_startup_enabled(enabled: bool) -> None:
    """Writes/deletes only the current user's named Run key, on explicit action."""
    if not startup_supported():
        raise StartupError("Iniciar com Windows está disponível no Genesis.exe instalado.")
    try:
        import winreg
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, "GenesisIrisMascot", 0, winreg.REG_SZ,
                    startup_command(sys.executable),
                )
            else:
                try:
                    winreg.DeleteValue(key, "GenesisIrisMascot")
                except FileNotFoundError:
                    pass
    except OSError as exc:
        raise StartupError("Windows não permitiu alterar a inicialização automática.") from exc
