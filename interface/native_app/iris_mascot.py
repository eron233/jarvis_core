"""Íris, personagem articulada flutuante e operadora de bordas no Windows.

Sem moldura, caixa de chat, retrato estático ou áudio. Quando o usuário pede,
pode prender os dedos à borda de uma janela normal e movê-la por arrasto real.
Respeita bloqueios/permissões do SO. Tabs de outros aplicativos não têm API
universal e não são manipuladas por força nem por injeção de teclas.
"""
from __future__ import annotations

import os
from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QWidget, QVBoxLayout

from interface.native_app.iris_desktop import (
    clamp_to_screens, nearest_edge_position, next_monitor_position,
)
from interface.native_app.iris_lab import IrisLabWindow
from interface.native_app.iris_puppet import IrisPuppet
from interface.native_app.iris_window_bridge import DesktopWindowBridge, WindowEdge


class IrisMascotWindow(QWidget):
    """Full-body movable Qt overlay. Grip requires user selection and drag."""

    hiddenByUser = Signal()
    interactionResult = Signal(str)

    def __init__(self, *, settings=None, parent=None, bridge=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Íris, mascote articulado")
        self.setAccessibleName("Íris, androide articulada, andando, sentando e agarrando bordas")
        self.setToolTip("Arraste a Íris. Clique direito para agarrar uma janela, sentar ou visitar o estúdio.")
        self.settings = settings if settings is not None else QSettings("Genesis", "Iris")
        self.bridge = bridge if bridge is not None else DesktopWindowBridge()
        self._reduced_motion = os.environ.get("IRIS_REDUCED_MOTION", "").lower() in ("1", "true", "yes")
        self._closing = False
        self._drag_at = None
        self._last_pointer = None
        self._gripped_window: WindowEdge | None = None
        self._strolling = bool(self.settings.value("iris_mascot/stroll", False, type=bool))
        self.lab = None

        self.puppet = IrisPuppet()
        self.avatar = self.puppet  # compatibilidade de chamadas existentes
        self.setFixedSize(self.puppet.size())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.puppet)
        self.puppet.installEventFilter(self)

        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.finished.connect(self._motion_finished)
        self._stroll_timer = QTimer(self)
        self._stroll_timer.setInterval(28000)
        self._stroll_timer.timeout.connect(self.go_to_next_monitor)
        self._stroll_timer.setSingleShot(False)

        saved_x = self.settings.value("iris_mascot/x", None)
        saved_y = self.settings.value("iris_mascot/y", None)
        try:
            initial = (int(saved_x), int(saved_y))
        except (TypeError, ValueError):
            cursor = QCursor.pos()
            initial = (cursor.x() + 20, cursor.y() + 25)
        self.move_to(initial, animated=False)
        if self._strolling:
            self._stroll_timer.start()

    def _screen_rects(self):
        return [(r.x(), r.y(), r.width(), r.height())
                for s in QApplication.screens() for r in [s.availableGeometry()]]

    def move_to(self, position, *, animated=True):
        coords = clamp_to_screens(
            (int(position[0]), int(position[1])),
            (self.width(), self.height()), self._screen_rects()
        )
        self._animation.stop()
        if not animated or self._reduced_motion:
            self.move(*coords)
            return
        start = self.pos()
        target = QPoint(*coords)
        if start == target:
            return
        distance = (start - target).manhattanLength()
        self.puppet.set_pose("walk")
        self._animation.setDuration(max(350, min(1500, distance // 2)))
        self._animation.setStartValue(start)
        self._animation.setEndValue(target)
        self._animation.start()

    def _motion_finished(self):
        if not self._closing:
            if self._gripped_window is None:
                self.puppet.set_pose("idle")
            self.save_position()

    def save_position(self):
        x, y = clamp_to_screens(
            (self.x(), self.y()), (self.width(), self.height()), self._screen_rects()
        )
        self.settings.setValue("iris_mascot/x", x)
        self.settings.setValue("iris_mascot/y", y)

    def go_to_next_monitor(self):
        if self._gripped_window is not None or self.lab is not None and self.lab.isVisible():
            return
        target = next_monitor_position((self.x(), self.y()),
                    (self.width(), self.height()), self._screen_rects())
        self.move_to(target)

    def dock_at_edge(self):
        self.move_to(nearest_edge_position(
            (self.x(), self.y()), (self.width(), self.height()), self._screen_rects()))

    def set_stroll(self, enabled):
        self._strolling = bool(enabled)
        self.settings.setValue("iris_mascot/stroll", self._strolling)
        if enabled and self._gripped_window is None and not (self.lab and self.lab.isVisible()):
            self._stroll_timer.start()
        else:
            self._stroll_timer.stop()

    def hide_by_user(self):
        self.release_window()
        self._stroll_timer.stop()
        self.hide()
        self.hiddenByUser.emit()

    def _hand_global_position(self):
        hx, hy = IrisPuppet.HAND_ANCHOR
        return self.x() + hx, self.y() + hy

    def select_window_edge(self) -> bool:
        """Explicit context-menu action: close the five fingers around a real edge."""
        target = self.bridge.find_edge(self._hand_global_position())
        if target is None:
            self.interactionResult.emit(
                "Nenhuma borda de janela compatível perto da mão da Íris.")
            return False
        self._gripped_window = target
        self._stroll_timer.stop()
        self._animation.stop()
        self.puppet.set_pose("reach")
        self.puppet.close_hand()
        self.interactionResult.emit("Íris agarrou a borda de: " + target.title)
        return True

    def sit_on_nearest_window(self) -> bool:
        target = self.bridge.find_edge(self._hand_global_position(), 160)
        if target is None:
            self.interactionResult.emit("Nenhuma borda compatível para sentar.")
            return False
        self.release_window()
        self.move_to((max(target.x, min(self.x(), target.x + target.width - self.width())),
                      target.y - 220), animated=False)
        self.puppet.set_pose("sit")
        self.interactionResult.emit("Íris sentou na borda de: " + target.title)
        return True

    def move_gripped_window(self, dx: int, dy: int) -> bool:
        """Window dragging only while a grip was explicitly acquired."""
        if self._gripped_window is None:
            return False
        target = self.bridge.current_edge(self._gripped_window.hwnd)
        if target is None or not self.bridge.move(target, dx, dy):
            self.release_window()
            self.interactionResult.emit("O sistema não permitiu puxar essa janela.")
            return False
        self.puppet.set_pose("pull")
        return True

    def release_window(self):
        self._gripped_window = None
        self.puppet.open_hand()
        if self.puppet.pose != "portal":
            self.puppet.set_pose("idle")
        if self._strolling and self.isVisible():
            self._stroll_timer.start()

    def open_lab(self, instant=False):
        if self.lab is not None and self.lab.isVisible():
            self.lab.activateWindow()
            return
        self.release_window()
        self._stroll_timer.stop()
        self.puppet.set_pose("portal")
        if instant or self._reduced_motion:
            self._enter_lab()
        else:
            QTimer.singleShot(650, self._enter_lab)

    def _enter_lab(self):
        if self._closing:
            return
        if self.lab is None:
            self.lab = IrisLabWindow()
            self.lab.leftLab.connect(self._return_from_lab)
        self.lab.show()
        self.lab.raise_()
        self.hide()

    def _return_from_lab(self):
        if self._closing:
            return
        self.puppet.set_pose("idle")
        self.show()
        self.raise_()
        if self._strolling:
            self._stroll_timer.start()

    def _open_menu(self, location):
        menu = QMenu(self)
        menu.addAction("Agarrar borda de janela próxima", self.select_window_edge)
        menu.addAction("Soltar borda", self.release_window)
        menu.addAction("Sentar em janela próxima", self.sit_on_nearest_window)
        menu.addSeparator()
        menu.addAction("Andar para outra tela", self.go_to_next_monitor)
        menu.addAction("Encostar na borda do monitor", self.dock_at_edge)
        stroll = menu.addAction("Passeio automático")
        stroll.setCheckable(True)
        stroll.setChecked(self._strolling)
        stroll.toggled.connect(self.set_stroll)
        menu.addSeparator()
        menu.addAction("Entrar no laboratório", lambda: self.open_lab())
        menu.addAction("Esconder Íris", self.hide_by_user)
        menu.exec(location)

    def eventFilter(self, source, event):
        if source is self.puppet:
            kind = event.type()
            if kind == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.open_lab()
                return True
            if kind == QEvent.MouseButtonPress:
                if event.button() == Qt.RightButton:
                    self._open_menu(event.globalPosition().toPoint())
                    return True
                if event.button() == Qt.LeftButton:
                    self._animation.stop()
                    cursor = event.globalPosition().toPoint()
                    self._drag_at = cursor - self.pos()
                    self._last_pointer = cursor
                    self.puppet.set_pose("grip" if self._gripped_window else "walk")
                    return True
            if kind == QEvent.MouseMove and self._drag_at is not None:
                if event.buttons() & Qt.LeftButton:
                    cursor = event.globalPosition().toPoint()
                    dx = cursor.x() - self._last_pointer.x()
                    dy = cursor.y() - self._last_pointer.y()
                    if self._gripped_window is not None:
                        self.move_gripped_window(dx, dy)
                    self.move(cursor - self._drag_at)
                    self._last_pointer = cursor
                    return True
            if kind == QEvent.MouseButtonRelease and self._drag_at is not None:
                self._drag_at = None
                self._last_pointer = None
                self.move_to((self.x(), self.y()), animated=False)
                self.save_position()
                self.release_window()
                return True
        return super().eventFilter(source, event)

    def closeEvent(self, event):
        self._closing = True
        self._stroll_timer.stop()
        self._animation.stop()
        self.puppet.motion_timer.stop()
        self.puppet.hand_animation.stop()
        if self.lab is not None:
            self.lab.close()
        super().closeEvent(event)
