"""Laboratorio visual local da Iris: porta animada e abas arrastaveis.

Nao promete executar testes do backend: cards da cena podem ser movidos,
e a interface exibe somente as capacidades visuais realmente disponiveis.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Property, QPropertyAnimation, QEasingCurve, Signal, QRectF, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
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


class IrisStudioView(QGraphicsView):
    """Cena adaptável, preservando proporção em monitores de tamanhos variados."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() is not None:
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)


class IrisLabWindow(QDialog):
    """Estúdio digital inspirado no escritório visto na primeira fotografia de Íris."""

    leftLab = Signal()
    ROOM_IMAGE = Path(__file__).resolve().parent / "assets" / "iris_studio_room.svg"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Íris | Seu estúdio e laboratório")
        self.setMinimumSize(740, 510)
        self.resize(1080, 740)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._lights_dimmed = False
        self.setStyleSheet("""
            QDialog { background: #141018; color: #eaf8ff; }
            QLabel { color: #e5d3bf; }
            QPushButton {
                background: #302a30; color: #fff3e8; border: 1px solid #876b5d;
                border-radius: 11px; padding: 11px 13px;
            }
            QPushButton:hover { background: #48394a; border-color: #d5a678; }
        """)
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 19, 20, 16)
        main.setSpacing(9)

        heading = QHBoxLayout()
        title = QLabel("ESTÚDIO DA ÍRIS")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #fff1df; letter-spacing: 2px;")
        heading.addWidget(title, 1)
        badge = QLabel("RECONSTRUÇÃO DIGITAL · HOME OFFICE")
        badge.setStyleSheet(
            "font-size: 10px; color: #e3ae7c; background: #30201e;"
            "padding: 8px 12px; border: 1px solid #674638; border-radius: 8px;"
        )
        heading.addWidget(badge)
        main.addLayout(heading)

        subtitle = QLabel(
            "O escritório quente da fotografia original: quadro urbano, madeira,"
            " planta, cadeira escura e monitores de código."
        )
        subtitle.setWordWrap(True)
        main.addWidget(subtitle)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 1200, 650)
        self.scene.setBackgroundBrush(QBrush(QColor("#241c21")))
        self.room_background = None
        source = QPixmap(str(self.ROOM_IMAGE))
        if not source.isNull():
            # Fundo real renderizado em Qt, não uma imagem fake dentro do chat.
            self.room_background = self.scene.addPixmap(
                source.scaled(1200, 650, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            )
            self.room_background.setZValue(-20)
            self.room_background.setAcceptedMouseButtons(Qt.NoButton)

        self.lighting_overlay = self.scene.addRect(
            self.scene.sceneRect(), QPen(Qt.NoPen), QBrush(QColor(12, 18, 30, 0))
        )
        self.lighting_overlay.setZValue(-10)
        self.lighting_overlay.setAcceptedMouseButtons(Qt.NoButton)

        # Objetos móveis pertencem exclusivamente ao laboratório de Íris.
        self.cards = []
        self.card_origins = []
        for index, (name, description) in enumerate((
            ("PERCEPÇÃO", "Um mundo de observações. O acesso a sensores exige autorização."),
            ("MOVIMENTO", "Passeios reais entre monitores e encaixe nas bordas."),
            ("EXPERIMENTOS", "Animações, portais e elementos visuais manipuláveis."),
        )):
            x, y = (28 + index * 389, 481)
            card = self.scene.addRect(
                0, 0, 355, 135,
                QPen(QColor("#c18b66"), 2),
                QBrush(QColor(20, 31, 43, 235)),
            )
            card.setPos(x, y)
            card.setFlag(QGraphicsItem.ItemIsMovable, True)
            card.setFlag(QGraphicsItem.ItemIsSelectable, True)
            card.setCursor(Qt.OpenHandCursor)
            card.setZValue(5)
            stripe = self.scene.addRect(0, 0, 355, 5, QPen(Qt.NoPen), QBrush(QColor("#71cfe6")))
            stripe.setParentItem(card)
            stripe.setAcceptedMouseButtons(Qt.NoButton)

            header = self.scene.addText(name, QFont("Segoe UI", 16, QFont.Bold))
            header.setDefaultTextColor(QColor("#f8e9d9"))
            header.setParentItem(card)
            header.setPos(21, 17)
            header.setAcceptedMouseButtons(Qt.NoButton)

            caption = self.scene.addText(description, QFont("Segoe UI", 10))
            caption.setTextWidth(320)
            caption.setDefaultTextColor(QColor("#b6d7e0"))
            caption.setParentItem(card)
            caption.setPos(21, 62)
            caption.setAcceptedMouseButtons(Qt.NoButton)

            self.cards.append(card)
            self.card_origins.append((x, y))

        self.view = IrisStudioView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setStyleSheet(
            "border: 1px solid #947256; background: #241c21; border-radius: 14px;"
        )
        main.addWidget(self.view, 1)

        footer = QHBoxLayout()
        label = QLabel("Pegue os cartões e reorganize a bancada. A sala é visual, sem executar testes reais.")
        label.setWordWrap(True)
        footer.addWidget(label, 1)

        self.lighting_button = QPushButton("Luzes: quente")
        self.lighting_button.clicked.connect(self.toggle_lights)
        footer.addWidget(self.lighting_button)

        self.reset_button = QPushButton("Arrumar bancada")
        self.reset_button.clicked.connect(self.reset_cards)
        footer.addWidget(self.reset_button)

        self.exit_button = QPushButton("Voltar ao desktop")
        self.exit_button.clicked.connect(self.close)
        footer.addWidget(self.exit_button)
        main.addLayout(footer)

        # Espera o Qt calcular a viewport real antes do enquadramento.
        QTimer.singleShot(0, self._fit_scene)

    def _fit_scene(self):
        if self.view.scene() is not None:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def toggle_lights(self):
        """Apenas altera a iluminação digital da nossa sala, nunca a iluminação real."""
        self._lights_dimmed = not self._lights_dimmed
        opacity = 142 if self._lights_dimmed else 0
        self.lighting_overlay.setBrush(QBrush(QColor(9, 21, 42, opacity)))
        self.lighting_button.setText("Luzes: noturna" if self._lights_dimmed else "Luzes: quente")

    def reset_cards(self):
        for card, (x, y) in zip(self.cards, self.card_origins):
            card.setPos(x, y)

    def closeEvent(self, event):
        self.leftLab.emit()
        super().closeEvent(event)
