"""Windows desktop bridge for explicitly requested Iris window interactions.

An external window is never moved until the user initiates a grip and drags.
Only ordinary, visible, enabled, titled top-level windows of other processes
are candidates. Unsupported platforms intentionally have no such capability.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class WindowEdge:
    hwnd: int
    title: str
    x: int
    y: int
    width: int
    height: int

    @property
    def top(self) -> int:
        return self.y


def nearest_edge(windows: list[WindowEdge], point: tuple[int, int],
                 max_distance: int = 96) -> WindowEdge | None:
    """Pure selector, to make hit testing auditable and testable without Windows."""
    px, py = point
    candidates = [
        w for w in windows
        if w.width >= 120 and w.height >= 90
        and w.x - 20 <= px <= w.x + w.width + 20
        and abs(w.top - py) <= max_distance
    ]
    return min(candidates, key=lambda w: (
        abs(w.top - py) * 2 + max(w.x - px, 0, px - (w.x + w.width)),
        w.width * w.height,
    ), default=None)


class DesktopWindowBridge:
    """Win32 operations with no input injection, elevation or focus stealing."""

    def __init__(self):
        self.supported = sys.platform == "win32"
        self._api = None
        if self.supported:
            try:
                import ctypes
                from ctypes import wintypes
                self._ctypes, self._wt = ctypes, wintypes
                self._api = ctypes.windll.user32
                self._api.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
                self._api.EnumWindows.restype = wintypes.BOOL
                self._api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                self._api.GetWindowRect.restype = wintypes.BOOL
                self._api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                self._api.GetWindowThreadProcessId.restype = wintypes.DWORD
                self._api.GetWindowTextLengthW.argtypes = [wintypes.HWND]
                self._api.GetWindowTextLengthW.restype = ctypes.c_int
                self._api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                self._api.GetWindowTextW.restype = ctypes.c_int
                self._api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
                self._api.SetWindowPos.restype = wintypes.BOOL
                for function in ("IsWindow", "IsWindowVisible", "IsWindowEnabled", "IsIconic", "IsZoomed"):
                    call = getattr(self._api, function)
                    call.argtypes = [wintypes.HWND]
                    call.restype = wintypes.BOOL
                self._api.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
                self._api.GetWindow.restype = wintypes.HWND
                self._api.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                self._api.GetWindowLongW.restype = wintypes.LONG
            except (AttributeError, OSError):
                self.supported = False
                self._api = None

    def _validate(self, hwnd: int) -> bool:
        if not self.supported or not self._api or not hwnd:
            return False
        api = self._api
        if not api.IsWindow(hwnd) or not api.IsWindowVisible(hwnd) or not api.IsWindowEnabled(hwnd):
            return False
        if api.IsIconic(hwnd):
            return False
        pid = self._wt.DWORD()
        api.GetWindowThreadProcessId(hwnd, self._ctypes.byref(pid))
        if pid.value in (0, os.getpid()):
            return False
        length = api.GetWindowTextLengthW(hwnd)
        if not 0 < length < 1024:
            return False
        # Owned/pop-up and tool windows are not general-purpose draggable app windows.
        if api.GetWindow(hwnd, 4):  # GW_OWNER
            return False
        style_ex = api.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        if style_ex & 0x00000080:  # WS_EX_TOOLWINDOW
            return False
        return True

    def _edge(self, hwnd: int) -> WindowEdge | None:
        if not self._validate(hwnd):
            return None
        rect = self._wt.RECT()
        if not self._api.GetWindowRect(hwnd, self._ctypes.byref(rect)):
            return None
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width < 120 or height < 90:
            return None
        buf = self._ctypes.create_unicode_buffer(self._api.GetWindowTextLengthW(hwnd) + 1)
        self._api.GetWindowTextW(hwnd, buf, len(buf))
        if not buf.value:
            return None
        return WindowEdge(int(hwnd), buf.value, rect.left, rect.top, width, height)

    def windows(self) -> list[WindowEdge]:
        if not self.supported or not self._api:
            return []
        out: list[WindowEdge] = []
        callback_type = self._ctypes.WINFUNCTYPE(self._wt.BOOL, self._wt.HWND, self._wt.LPARAM)
        def visit(hwnd, _):
            info = self._edge(hwnd)
            if info is not None:
                out.append(info)
            return True
        callback = callback_type(visit)
        self._api.EnumWindows(callback, 0)
        return out

    def find_edge(self, point: tuple[int, int], max_distance: int = 96) -> WindowEdge | None:
        return nearest_edge(self.windows(), point, max_distance)

    def current_edge(self, hwnd: int) -> WindowEdge | None:
        return self._edge(hwnd)

    def move(self, target: WindowEdge, dx: int, dy: int) -> bool:
        """Move one already selected window. No activation or resizing."""
        if not self._validate(target.hwnd):
            return False
        before = self._edge(target.hwnd)
        if before is None or not (dx or dy):
            return bool(before)
        # Do not move windows the OS has maximized or disabled.
        if self._api.IsZoomed(target.hwnd):
            return False
        flags = 0x0004 | 0x0010 | 0x0001  # NOZORDER, NOACTIVATE, NOSIZE
        return bool(self._api.SetWindowPos(target.hwnd, 0,
                                          int(before.x + dx), int(before.y + dy),
                                          0, 0, flags))
