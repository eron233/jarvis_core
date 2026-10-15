"""Laboratorio visual local da Iris: porta animada e abas arrastaveis.

Nao promete executar testes do backend: cards da cena podem ser movidos,
e a interface exibe somente as capacidades visuais realmente disponiveis.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve, Signal, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsItem, QGraphicsScene, QGraphicsView, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
)


class IrisPortalDoor(QWidget):
    """Uma porta desenhada e animada, sem sobreposicao a outros aplicativos."""
    entered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(122, 100)
        self._openness = 0.0
        self.animation = QPropertyAnimation(self, b"openness", self)
        self.animation.setDuration(600)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.finished.connect(self._finished)

    def _get_openness(self):
        return self._openness

    def _set_openness(self, value):
        self._openness = float(value)
        self.update()

    openness = Property(float, _get_openness, _set_openness)

    def enter(self, instant=False):
        """Abre a porta; avisa o chamador apenas no termino da animacao."""
        self.animation.stop()
        self._openness = 0.0
        if instant:
            self._set_openness(1.0)
            self.entered.emit()
        else:
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.start()

    def reset(self):
        self.animation.stop()
        self._set_openness(0.0)

    def _finished(self):
        if self._openness >= .99:
            self.entered.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        box = self.rect().adjusted(10, 6, -10, -6)
        painter.setPen(QPen(QColor("#6bb8dd"), 2))
        painter.setBrush(QColor("#062639"))
        painter.drawRoundedRect(box, 20, 20)
        opening = box.adjusted(12, 9, -12, -8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#78ddf4"))
        painter.drawRoundedRect(opening, 15, 15)
        half = opening.width() / 2
        travel = int(half * self._openness)
        painter.setBrush(QColor("#122332"))
        painter.drawRect(QRectF(opening.left() - travel, opening.top(), half, opening.height()))
        painter.drawRect(QRectF(opening.left() + half + travel, opening.top(), half, opening.height()))
        painter.end()


class IrisLabWindow(QDialog):
    """Sala visual independente, com abas de experiencia que podem ser movidas."""
    leftLab = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Íris | Laboratório visual")
        self.setMinimumSize(740, 520)
        self.resize(920, 610)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setStyleSheet("""
            QDialog { background: #07101a; color: #e6f6ff; }
            QLabel { color: #bdd6e8; }
            QPushButton { background: #12374d; color: #f5fcff; border: 1px solid #396980;
                           border-radius: 11px; padding: 11px 16px; }
            QPushButton:hover { background: #1c506b; }
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(24, 22, 24, 22)
        title = QLabel("LABORATÓRIO DA ÍRIS")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #ecfcff; letter-spacing: 2px;")
        main.addWidget(title)
        sub = QLabel("Espaço visual experimental. Arraste as abas para reorganizar a bancada.")
        sub.setWordWrap(True)
        main.addWidget(sub)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 820, 350)
        self.scene.setBackgroundBrush(QBrush(QColor("#0c1e2c")))
        self.cards = []
        for index, (name, description) in enumerate((
            ("PERCEPÇÃO", "Sensores e visão: somente com permissão"),
            ("MOVIMENTO", "Travessia entre monitores"),
            ("EXPERIMENTOS", "Interações e animações visuais"),
        )):
            rect = self.scene.addRect(0, 0, 228, 122, QPen(QColor("#44768c"), 1.5),
                                      QBrush(QColor("#153449")))
            rect.setPos(28 + index * 255, 93)
            rect.setFlag(QGraphicsItem.ItemIsMovable, True)
            rect.setFlag(QGraphicsItem.ItemIsSelectable, True)
            rect.setZValue(1)
            header = self.scene.addText(name, QFont("Segoe UI", 13, QFont.Bold))
            header.setDefaultTextColor(QColor("#e4faff"))
            header.setParentItem(rect)
            header.setPos(17, 16)
            caption = self.scene.addText(description, QFont("Segoe UI", 9))
            caption.setTextWidth(198)
            caption.setDefaultTextColor(QColor("#a8cddd"))
            caption.setParentItem(rect)
            caption.setPos(17, 53)
            self.cards.append(rect)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setStyleSheet("border: 1px solid #204155; background: #0c1e2c; border-radius: 15px;")
        main.addWidget(self.view, 1)

        footer = QHBoxLayout()
        detail = QLabel("Ambiente local e ilustrativo. Nenhum teste externo foi executado.")
        detail.setWordWrap(True)
        footer.addWidget(detail, 1)
        self.exit_button = QPushButton("Voltar ao desktop")
        self.exit_button.clicked.connect(self.close)
        footer.addWidget(self.exit_button)
        main.addLayout(footer)

    def closeEvent(self, event):
        self.leftLab.emit()
        super().closeEvent(event)
