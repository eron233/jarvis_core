"""Íris livre na área de trabalho: janela leve, multi-monitor e laboratório visual.

Só manipula suas próprias janelas. Não arrasta abas de terceiros, não espiona
o desktop, não ativa áudio, não altera permissões e não inicia ações do runtime.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPropertyAnimation,
    QSettings, Qt, QTimer, Signal,
)
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from interface.native_app.iris_desktop import (
    clamp_to_screens, nearest_edge_position, next_monitor_position,
)
from interface.native_app.iris_lab import IrisLabWindow, IrisPortalDoor
from interface.native_app.iris_presence import ASSET_PATH, FALLBACK_ASSET_PATH


class IrisMascotWindow(QWidget):
    """Avatar flutuante arrastável, com portal e configuração por usuário."""

    hiddenByUser = Signal()

    def __init__(self, *, settings=None, parent=None):
        # Não vincular a janela ao ciclo de minimizar do aplicativo principal.
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName("IrisMascotWindow")
        self.setWindowTitle("Íris, mascote flutuante")
        self.setAccessibleName("Íris, mascote flutuante interativo")
        self.setFixedSize(180, 252)
        self.settings = settings if settings is not None else QSettings("Genesis", "Iris")
        self.lab = None
        self._closing = False
        self._drag_at = None
        self._strolling = bool(self.settings.value("iris_mascot/stroll", False, type=bool))
        self._reduced_motion = os.environ.get("IRIS_REDUCED_MOTION", "").lower() in (
            "1", "true", "yes",
        )

        self._animation = QPropertyAnimation(self, b"pos", self)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.finished.connect(self.save_position)
        self._stroll_timer = QTimer(self)
        self._stroll_timer.setInterval(28000)
        self._stroll_timer.timeout.connect(self.go_to_next_monitor)
        self._build_widgets()

        x = self.settings.value("iris_mascot/x", None)
        y = self.settings.value("iris_mascot/y", None)
        if x is None or y is None:
            cursor = QCursor.pos()
            initial = (cursor.x() + 20, cursor.y() + 25)
        else:
            try:
                initial = (int(x), int(y))
            except (ValueError, TypeError):
                initial = (QCursor.pos().x(), QCursor.pos().y())
        self.move_to(initial, animated=False)
        if self._strolling:
            self._stroll_timer.start()

    def _build_widgets(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSpacing(0)
        self.card = QFrame()
        self.card.setObjectName("MascotCard")
        self.card.setStyleSheet("""
            #MascotCard {
                background: rgba(10, 23, 37, 238); border: 1px solid #477f98;
                border-radius: 22px;
            }
            QLabel { color: #e9f9ff; background: transparent; }
            QPushButton {
                background: #14384e; color: #e8fbff; border: 1px solid #33627c;
                border-radius: 10px; padding: 6px;
            }
            QPushButton:hover { background: #275673; }
        """)
        root.addWidget(self.card)
        col = QVBoxLayout(self.card)
        col.setContentsMargins(10, 9, 10, 11)
        col.setSpacing(4)

        self.caption = QLabel("Í R I S   ·   G Ê N E S I S")
        self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setStyleSheet("font-size: 9px; color: #bddded; letter-spacing: 1px;")
        col.addWidget(self.caption)

        self.stack = QStackedWidget()
        self.stack.setFixedHeight(158)
        self.avatar = QLabel()
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setAccessibleName("Arraste a Íris para movê-la pelo desktop")
        self._load_image()
        self.stack.addWidget(self.avatar)

        self.door = IrisPortalDoor()
        self.door.entered.connect(self._enter_lab)
        self.stack.addWidget(self.door)
        col.addWidget(self.stack)

        self.hint = QLabel("Arraste • clique direito para ações")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("font-size: 9px; color: #8db4c7;")
        col.addWidget(self.hint)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.lab_button = QPushButton("◈ Laboratório")
        self.lab_button.setToolTip("Abrir uma porta para o laboratório visual")
        self.lab_button.clicked.connect(self.open_lab)
        self.close_button = QPushButton("×")
        self.close_button.setToolTip("Esconder mascote; recuperar pelo botão no Gênesis")
        self.close_button.setFixedWidth(25)
        self.close_button.clicked.connect(self.hide_by_user)
        row.addWidget(self.lab_button, 1)
        row.addWidget(self.close_button)
        col.addLayout(row)

        for obj in (self.card, self.avatar, self.caption, self.hint):
            obj.installEventFilter(self)

    def _load_image(self):
        selected = os.environ.get("IRIS_AVATAR_PATH", "").strip()
        path = Path(selected).expanduser() if selected else ASSET_PATH
        original = QPixmap(str(path)) if path.is_file() else QPixmap()
        if original.isNull():
            original = QPixmap(str(ASSET_PATH))
        if original.isNull():
            original = QPixmap(str(FALLBACK_ASSET_PATH))
        if original.isNull():
            self.avatar.setText("Í")
            return
        self.avatar.setPixmap(original.scaled(148, 155, Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation))

    def _screen_rects(self):
        return [
            (s.availableGeometry().x(), s.availableGeometry().y(),
             s.availableGeometry().width(), s.availableGeometry().height())
            for s in QApplication.screens()
        ]

    def move_to(self, position, *, animated=True):
        target = clamp_to_screens(
            (int(position[0]), int(position[1])),
            (self.width(), self.height()),
            self._screen_rects(),
        )
        self._animation.stop()
        if not animated or self._reduced_motion:
            self.move(*target)
            return
        start = self.pos()
        if start == QPoint(*target):
            return
        distance = abs(start.x() - target[0]) + abs(start.y() - target[1])
        self._animation.setDuration(max(380, min(1500, distance // 2)))
        self._animation.setStartValue(start)
        self._animation.setEndValue(QPoint(*target))
        self._animation.start()

    def save_position(self):
        """Persiste apenas coordenadas; nunca dados ou imagens da tela."""
        x, y = clamp_to_screens((self.x(), self.y()),
                                (self.width(), self.height()), self._screen_rects())
        self.settings.setValue("iris_mascot/x", x)
        self.settings.setValue("iris_mascot/y", y)

    def go_to_next_monitor(self):
        target = next_monitor_position((self.x(), self.y()),
                                        (self.width(), self.height()), self._screen_rects())
        self.move_to(target)

    def dock_at_edge(self):
        target = nearest_edge_position((self.x(), self.y()),
                                       (self.width(), self.height()), self._screen_rects())
        self.move_to(target)

    def set_stroll(self, enabled: bool):
        self._strolling = bool(enabled)
        self.settings.setValue("iris_mascot/stroll", self._strolling)
        if enabled:
            self._stroll_timer.start()
        else:
            self._stroll_timer.stop()

    def hide_by_user(self):
        self._stroll_timer.stop()
        self.hide()
        self.hiddenByUser.emit()

    def open_lab(self, instant=False):
        if self.lab is not None and self.lab.isVisible():
            self.lab.activateWindow()
            return
        self._stroll_timer.stop()
        self.stack.setCurrentWidget(self.door)
        self.hint.setText("Abrindo passagem para o laboratório...")
        self.door.enter(instant=instant)

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
        self.door.reset()
        self.stack.setCurrentWidget(self.avatar)
        self.hint.setText("Arraste • clique direito para ações")
        self.show()
        self.raise_()
        if self._strolling:
            self._stroll_timer.start()

    def _open_menu(self, global_point):
        menu = QMenu(self)
        menu.addAction("Passear para outra tela", self.go_to_next_monitor)
        menu.addAction("Encostar na borda", self.dock_at_edge)
        walk = menu.addAction("Passeio automático")
        walk.setCheckable(True)
        walk.setChecked(self._strolling)
        walk.toggled.connect(self.set_stroll)
        menu.addSeparator()
        menu.addAction("Entrar no laboratório", self.open_lab)
        menu.addAction("Esconder Íris", self.hide_by_user)
        menu.exec(global_point)

    def eventFilter(self, obj, event):
        if obj in (self.card, self.avatar, self.caption, self.hint):
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.open_lab()
                return True
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.RightButton:
                    self._open_menu(event.globalPosition().toPoint())
                    return True
                if event.button() == Qt.LeftButton:
                    self._animation.stop()
                    self._drag_at = event.globalPosition().toPoint() - self.pos()
                    return True
            if event.type() == QEvent.MouseMove and self._drag_at is not None:
                if event.buttons() & Qt.LeftButton:
                    self.move(event.globalPosition().toPoint() - self._drag_at)
                    return True
            if event.type() == QEvent.MouseButtonRelease and self._drag_at is not None:
                self._drag_at = None
                self.move_to((self.x(), self.y()), animated=False)
                self.save_position()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._closing = True
        self._stroll_timer.stop()
        self._animation.stop()
        if self.lab is not None:
            self.lab.close()
        super().closeEvent(event)
