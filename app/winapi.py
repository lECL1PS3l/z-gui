from __future__ import annotations

import ctypes
import os

ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

_user32.FindWindowW.restype = ctypes.c_void_p
_user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
_user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]


def single_instance(name: str):
    handle = _kernel32.CreateMutexW(None, False, name)
    if not handle:
        return None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def find_window(title: str = "Z-GUI"):
    return _user32.FindWindowW(None, title)


def show_window(handle) -> bool:
    if not handle:
        return False
    _user32.ShowWindow(handle, 9)
    _user32.SetForegroundWindow(handle)
    return True


def close_window(handle) -> bool:
    if not handle:
        return False
    _user32.PostMessageW(handle, 0x0010, None, None)
    return True


def dark_title(handle) -> None:
    if not handle:
        return
    try:
        dwm = ctypes.WinDLL("dwmapi")
        value = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(
            ctypes.c_void_p(handle), 20, ctypes.byref(value), ctypes.sizeof(value)
        )
    except OSError:
        pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def spawn_detached(command: list[str], cwd: str | None = None) -> None:
    import subprocess

    flags = 0x00000008 if os.name == "nt" else 0
    subprocess.Popen(
        command,
        cwd=cwd,
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
