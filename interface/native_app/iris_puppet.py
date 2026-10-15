"""Íris: mascote chibi 2D, desenhada em Qt e animada por juntas.

Identidade visual constante: cabelos prateados, olhos azuis, roupa branca
tecnológica. Presets de idade são estilos gráficos da MESMA personagem fictícia,
sem simular qualquer alteração real de idade.
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve, QPointF, QRectF
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

BASE_W, BASE_H = 236, 318
STYLES = {
    "nova": {"head": 1.10, "eye": 1.13, "lash": 0.7, "hair": "#f2f3ff", "suit": "#f1eaf7"},
    "padrao": {"head": 1.0, "eye": 1.0, "lash": 1.0, "hair": "#e4eaf5", "suit": "#eef1f8"},
    "madura": {"head": .94, "eye": .90, "lash": 1.18, "hair": "#e6e5f3", "suit": "#dde5f1"},
}
SIZE_PRESETS = {"mini": .56, "normal": 1.0, "grande": 1.45}
MIN_SCALE, MAX_SCALE = .40, 2.15


def valid_scale(scale: float) -> float:
    value = float(scale)
    if not math.isfinite(value):
        raise ValueError("Escala inválida")
    return max(MIN_SCALE, min(MAX_SCALE, value))


class IrisPuppet(QWidget):
    """Corpo inteiro, cabelo em movimento, olhos vivos e cinco dedos articulados."""

    POSES = frozenset({"idle", "walk", "sit", "reach", "grip", "pull", "portal", "jump", "sleep"})
    HAND_ANCHOR = (201, 146)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAccessibleName("Íris estilizada de corpo inteiro, piscando, caminhando e agarrando")
        self.pose = "idle"
        self.visual_age = "padrao"
        self.scale_factor = 1.0
        self.grip = 0.0
        self.step = 0.0
        self._tick = 0
        self._reduced_motion = os.environ.get("IRIS_REDUCED_MOTION", "").lower() in ("1", "true", "yes", "on")
        self.motion_timer = QTimer(self)
        self.motion_timer.setInterval(65)
        self.motion_timer.timeout.connect(self._advance)
        self.hand_animation = QVariantAnimation(self)
        self.hand_animation.setDuration(460)
        self.hand_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.hand_animation.valueChanged.connect(self._set_grip)
        self.set_scale(1.0)
        if not self._reduced_motion:
            self.motion_timer.start()

    def set_scale(self, scale):
        self.scale_factor = valid_scale(scale)
        self.setFixedSize(round(BASE_W * self.scale_factor), round(BASE_H * self.scale_factor))
        self.update()

    def set_visual_age(self, style):
        if style not in STYLES:
            raise ValueError("Estilo visual desconhecido: " + str(style))
        self.visual_age = style
        self.update()

    def set_pose(self, pose):
        if pose not in self.POSES:
            raise ValueError("Pose não suportada: " + str(pose))
        self.pose = pose
        self.update()

    def _set_grip(self, value):
        self.grip = float(value)
        self.update()

    def close_hand(self, *, instant=False):
        self._animate_hand(1., instant)

    def open_hand(self, *, instant=False):
        self._animate_hand(0., instant)

    def _animate_hand(self, end, instant=False):
        self.hand_animation.stop()
        if instant or self._reduced_motion:
            self._set_grip(end)
            return
        self.hand_animation.setStartValue(self.grip)
        self.hand_animation.setEndValue(end)
        self.hand_animation.start()

    def _advance(self):
        if not self.isVisible():
            return
        self._tick += 1
        self.step += .32 if self.pose in ("walk", "pull", "jump") else .06
        self.update()

    @staticmethod
    def _line(p, pts, color, width=6, rim="#56637f"):
        for shade, thick in ((rim, width + 3), (color, width)):
            p.setPen(QPen(QColor(shade), thick, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for a, b in zip(pts, pts[1:]):
                p.drawLine(QPointF(*a), QPointF(*b))

    @staticmethod
    def _fill_path(p, vertices, fill, stroke="#536079", width=2):
        path = QPainterPath()
        path.moveTo(*vertices[0])
        for x, y in vertices[1:]:
            path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(QPen(QColor(stroke), width))
        p.setBrush(QColor(fill))
        p.drawPath(path)

    def _hand(self, p, center):
        """Each finger bends independently around the selected window edge."""
        cx, cy = center
        p.setPen(QPen(QColor("#4d617d"), 2))
        p.setBrush(QColor("#f3f5fc"))
        p.drawRoundedRect(QRectF(cx - 9, cy - 9, 20, 21), 6, 6)
        for f in range(5):
            angle = math.radians(-82 + f * 31)
            ox, oy = cx + 7 * math.cos(angle), cy - 3 + 7 * math.sin(angle)
            reach = 16 if f else 13
            tip = (ox + reach * math.cos(angle), oy + reach * math.sin(angle))
            fold = (cx + 2 + (f-2)*2, cy + 11 + abs(f-2)*1.5)
            mid = ((ox + tip[0]) / 2*(1-self.grip) + fold[0]*self.grip,
                   (oy + tip[1]) / 2*(1-self.grip) + fold[1]*self.grip)
            end = (tip[0]*(1-self.grip) + cx*self.grip,
                   tip[1]*(1-self.grip) + (cy+11)*self.grip)
            self._line(p, [(ox,oy), mid, end], "#e9f2fa", 3.5, "#6b86a2")

    def _head(self, p, style, hair_shift, blinking, gaze):
        """Illustrated face, NOT a cropped photograph; animated expression is real."""
        p.save()
        p.translate(119, 99)
        head = style["head"]
        p.scale(head, head)
        p.translate(-119, -99)

        # Back hair / silhouette with lively separated locks.
        p.setPen(QPen(QColor("#98a9c3"), 2.4))
        p.setBrush(QColor(style["hair"]))
        p.drawEllipse(QRectF(66, 32, 109, 122))
        for x, direction in ((71,-1),(163,1),(79,-1),(158,1)):
            wave = hair_shift * (1 if direction > 0 else -1)
            hair = QPainterPath()
            hair.moveTo(x, 71)
            hair.cubicTo(x + 15*direction + wave, 105, x + 14*direction + wave, 143,
                         x + 8*direction + wave, 166)
            p.setPen(QPen(QColor("#cbd9ef"), 9, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(hair)

        # Ears, round jaw, nose and blush. More mature mode is subtle, not sexualized.
        p.setPen(QPen(QColor("#ad91ae"), 2))
        p.setBrush(QColor("#f5d9d7"))
        p.drawEllipse(QRectF(73, 86, 12, 24))
        p.drawEllipse(QRectF(156, 86, 12, 24))
        face = QPainterPath()
        face.moveTo(82, 79)
        face.cubicTo(82, 48, 160, 48, 160, 81)
        face.cubicTo(161, 116, 153, 139, 120, 146)
        face.cubicTo(91, 140, 79, 118, 82, 79)
        face.closeSubpath()
        p.setBrush(QColor("#f7dcdb"))
        p.drawPath(face)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(252, 133, 157, 45))
        p.drawEllipse(QRectF(82, 112, 26, 13))
        p.drawEllipse(QRectF(140, 112, 26, 13))

        blink = blinking or self.pose == "sleep"
        for eye_x in (102, 139):
            p.setPen(QPen(QColor("#584969"), 2.3))
            if blink:
                p.drawArc(QRectF(eye_x - 11, 99, 23, 8), 0, -180*16)
            else:
                eye_size = style["eye"]
                p.setBrush(QColor("#e5f9ff"))
                p.drawEllipse(QRectF(eye_x-11*eye_size, 94, 22*eye_size, 22*eye_size))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#1a7cb6"))
                p.drawEllipse(QRectF(eye_x-6 + gaze, 97, 13, 16))
                p.setBrush(QColor("#9bf4ff"))
                p.drawEllipse(QRectF(eye_x-2 + gaze, 98, 5, 6))
                p.setPen(QPen(QColor("#624e71"), 2))
                p.drawArc(QRectF(eye_x-12, 92, 24, 11), 15*16, 153*16)
                if style["lash"] > 1:
                    p.drawLine(QPointF(eye_x + 10, 97), QPointF(eye_x + 14, 92))
        p.setPen(QPen(QColor("#ce9aab"), 1.3))
        p.drawLine(QPointF(120, 111), QPointF(118, 115))
        mouth = QPainterPath()
        mouth.moveTo(112, 125)
        mouth.quadTo(120, 130 if self.pose != "pull" else 122, 129, 124)
        p.setPen(QPen(QColor("#b47892"), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(mouth)

        # Platinum fringe / asymmetrical bangs.
        p.setBrush(QColor(style["hair"]))
        p.setPen(QPen(QColor("#afbbd2"), 1.6))
        fringe = QPainterPath()
        fringe.moveTo(69, 95)
        fringe.cubicTo(59, 54, 76, 31, 119, 29)
        fringe.cubicTo(162, 24, 180, 56, 172, 91)
        fringe.cubicTo(156, 66, 152, 57, 142, 54)
        fringe.cubicTo(129, 74, 116, 74, 103, 91)
        fringe.cubicTo(96, 72, 89, 67, 69, 95)
        p.drawPath(fringe)
        p.setPen(QPen(QColor("#fffaff"), 4.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(93, 42), QPointF(111, 73))
        p.drawLine(QPointF(132, 39), QPointF(125, 69))
        p.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        sx = self.width() / BASE_W
        sy = self.height() / BASE_H
        p.scale(sx, sy)
        style = STYLES[self.visual_age]
        wave = 0 if self._reduced_motion else math.sin(self.step)
        bob = wave*2.2 if self.pose in ("idle","walk") else 0
        sit = self.pose == "sit"
        reaching = self.pose in ("grip","pull","reach")
        cursor = QCursor.pos()
        global_center = self.mapToGlobal(__import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(self.width()//2, 0))
        gaze = 0 if self._reduced_motion else max(-3, min(3, (cursor.x() - global_center.x()) / 90))
        blink = (self._tick % 105) in (0, 1, 2)
        hair_shift = 0 if self._reduced_motion else 3*math.sin(self.step*.35)

        p.save()
        p.translate(0, bob + (19 if sit else 0))
        p.setBrush(QColor(26, 88, 136, 22))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(67, 299, 111, 10))
        for side in (-1, 1):
            x = 119 + side*16
            stride = 10*math.sin(self.step + (0 if side<0 else math.pi)) if self.pose=="walk" and not self._reduced_motion else 0
            knee = (x + side*(24 if sit else 3) - stride, 245)
            boot = (x + side*(39 if sit else 1)+stride*.7, 275 if sit else 296)
            self._line(p, [(x, 204), knee, boot], "#e9eefb", 17, "#566581")
            p.setBrush(QColor("#223447"))
            p.setPen(QPen(QColor("#718ca8"), 2))
            p.drawRoundedRect(QRectF(boot[0]-14,boot[1]-4,29,12),5,5)
            p.setBrush(QColor("#72dfff"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(*knee), 4, 4)

        # Compact jacket and electronic accents.
        self._fill_path(p, [(92,141),(77,157),(82,212),(99,224),(141,224),
                            (158,209),(157,157),(139,141)], style["suit"])
        p.setPen(QPen(QColor("#8594af"), 3))
        p.drawLine(QPointF(120,151), QPointF(120,220))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#243750"))
        p.drawRoundedRect(QRectF(109,169,23,29),6,6)
        p.setBrush(QColor("#7ee7fb"))
        p.drawEllipse(QPointF(120,181),5.5,5.5)

        # Arms articulate independently. One reaches out to actually grab.
        self._line(p, [(87,156),(67,187+wave*2),(65,212)], "#eef0fb",15)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#c3d8e8"))
        p.drawEllipse(QPointF(64,214),8,8)
        elbow=(172,159 if reaching else 178)
        wrist=(199,145 if reaching else 213)
        self._line(p,[(151,153),elbow,wrist],"#f0f3fc",15)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#6ee0f5"))
        p.drawEllipse(QPointF(*elbow),5,5)

        self._head(p,style,hair_shift,blink,gaze)
        self._hand(p,wrist)
        if self.pose=="portal":
            p.setPen(QPen(QColor("#91effc"),4))
            p.setBrush(QColor(96,193,242,22))
            p.drawEllipse(QRectF(22,12,191,293))
        p.restore()
        p.end()
