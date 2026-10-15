"""Lightweight articulated Iris desktop character. Pure Qt painter, no 3D engine.

The open/closed fingers, wrists, elbows, knees and boots are actual separately
drawn moving joints, not an unanimated photo moved across the desktop.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QPixmap
from PySide6.QtWidgets import QWidget

from interface.native_app.iris_presence import ASSET_PATH, FALLBACK_ASSET_PATH


class IrisPuppet(QWidget):
    """Full-body 2D paper puppet with a hand whose five fingers curl visibly."""

    POSES = frozenset({"idle", "walk", "sit", "reach", "grip", "pull", "portal"})
    HAND_ANCHOR = (201, 146)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(236, 318)
        self.setAccessibleName("Íris articulada, corpo inteiro e mão com dedos animados")
        self.pose = "idle"
        self.grip = 0.0
        self.step = 0.0
        self._tick = 0
        self._reduced_motion = __import__("os").environ.get("IRIS_REDUCED_MOTION", "").lower() in ("1", "true", "yes")
        self.motion_timer = QTimer(self)
        self.motion_timer.setInterval(50)
        self.motion_timer.timeout.connect(self._advance)
        self.hand_animation = QVariantAnimation(self)
        self.hand_animation.setDuration(500)
        self.hand_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.hand_animation.valueChanged.connect(self._set_grip)
        self.face = self._face_image()
        self.motion_timer.start()

    def _face_image(self):
        # Keep the original silver-haired, luminous-eyed Iris identity.
        pixmap = QPixmap(str(ASSET_PATH))
        if pixmap.isNull():
            pixmap = QPixmap(str(FALLBACK_ASSET_PATH))
        return pixmap

    def _set_grip(self, value):
        self.grip = float(value)
        self.update()

    def set_pose(self, pose):
        if pose not in self.POSES:
            raise ValueError("Pose não suportada: " + str(pose))
        self.pose = pose
        self.update()

    def close_hand(self, *, instant=False):
        self._animate_fingers(1.0, instant=instant)

    def open_hand(self, *, instant=False):
        self._animate_fingers(0.0, instant=instant)

    def _animate_fingers(self, target, *, instant=False):
        self.hand_animation.stop()
        if instant or self._reduced_motion:
            self._set_grip(target)
            return
        self.hand_animation.setStartValue(self.grip)
        self.hand_animation.setEndValue(target)
        self.hand_animation.start()

    def _advance(self):
        self._tick += 1
        if self.pose in ("walk", "pull"):
            self.step += .31
        elif self.pose == "idle":
            self.step += .045
        # Avoid repainting a stationary sprite continuously if reduced motion.
        if not self._reduced_motion and self.pose in ("walk", "pull", "idle"):
            self.update()

    @staticmethod
    def _line(p, x1, y1, x2, y2, color, width):
        p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    @staticmethod
    def _limb(p, joints, color="#e3eaf2", width=18, outline="#4e657d"):
        p.setPen(QPen(QColor(outline), width + 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for a, b in zip(joints, joints[1:]):
            p.drawLine(QPointF(*a), QPointF(*b))
        p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for a, b in zip(joints, joints[1:]):
            p.drawLine(QPointF(*a), QPointF(*b))

    def _draw_hand(self, p, center, grip):
        """All five fingers have separate two-segment curves and curl over a grip."""
        cx, cy = center
        p.setBrush(QColor("#dce7ed"))
        p.setPen(QPen(QColor("#40566b"), 2))
        p.drawRoundedRect(QRectF(cx - 12, cy - 11, 24, 26), 8, 8)
        for finger in range(5):
            # Splay the straight fingers. Then fold each around the edge.
            angle = math.radians(-72 + finger * 31)
            ox, oy = cx + 9 * math.cos(angle), cy - 5 + 9 * math.sin(angle)
            reach = 20 if finger != 0 else 15
            spread_x = ox + reach * math.cos(angle)
            spread_y = oy + reach * math.sin(angle)
            bent_x = cx + 4 + (finger - 2) * 2.3
            bent_y = cy + 9 + abs(finger - 2) * 2
            halfway = (ox + (spread_x - ox) * (1 - grip) + (bent_x - ox) * grip,
                       oy + (spread_y - oy) * (1 - grip) + (bent_y - oy) * grip)
            tip = (spread_x + (cx + 2 - spread_x) * grip,
                   spread_y + (cy + 13 - spread_y) * grip)
            self._limb(p, [(ox, oy), halfway, tip], "#eff5f8", 4, "#547188")
            p.setBrush(QColor("#65d8fb"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(*halfway), 1.6, 1.6)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # All coordinates use one world-space character rig.
        bob = 0.0 if self._reduced_motion else 1.7 * math.sin(self.step)
        sit = self.pose == "sit"
        is_gripping = self.pose in ("grip", "pull", "reach")
        p.save()
        p.translate(0, bob + (24 if sit else 0))
        # Boot/shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(64, 161, 205, 39))
        p.drawEllipse(QRectF(56, 291, 135, 16))
        # Two hips/knees/ankles articulate independently.
        for side in (-1, 1):
            x = 114 + side * 21
            stride = (math.sin(self.step + (0 if side < 0 else math.pi)) * 11
                      if self.pose == "walk" and not self._reduced_motion else 0)
            if sit:
                joints = [(x, 201), (x + side * 19, 237), (x + side * 40, 252)]
            else:
                joints = [(x, 199), (x + side * 5 - stride, 252),
                          (x + stride * .7, 289)]
            self._limb(p, joints, "#f0f0f3", 19, "#53647c")
            boot = joints[-1]
            p.setBrush(QColor("#17293d"))
            p.setPen(QPen(QColor("#7ba7ba"), 2))
            p.drawRoundedRect(QRectF(boot[0] - 13, boot[1] - 2, 31, 15), 6, 6)
            p.setBrush(QColor("#72d9fe"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(*joints[1]), 4, 4)
        # Torso of the white technological suit.
        torso = QPainterPath()
        torso.moveTo(86, 119)
        torso.cubicTo(60, 132, 67, 188, 79, 215)
        torso.quadTo(118, 231, 155, 211)
        torso.cubicTo(172, 176, 172, 130, 142, 117)
        torso.closeSubpath()
        p.setPen(QPen(QColor("#49627c"), 3))
        p.setBrush(QColor("#e3ebf4"))
        p.drawPath(torso)
        p.setPen(QPen(QColor("#5f7386"), 3))
        p.drawLine(QPointF(116, 134), QPointF(114, 203))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#10283c"))
        p.drawRoundedRect(QRectF(102, 144, 32, 52), 9, 9)
        p.setBrush(QColor("#68d7ff"))
        p.drawEllipse(QPointF(118, 168), 6, 6)
        # Left arm waves slightly, right arm reaches the edge with a wrist.
        self._limb(p, [(80, 137), (55, 172), (63, 204)], "#ecf0f5", 17)
        p.setBrush(QColor("#c7d7e2"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(65, 207), 10, 10)
        # Right shoulder, elbow, wrist. External window only moves on explicit drag.
        right_elbow = (175, 151 if is_gripping else 173)
        wrist = (200, 146 if is_gripping else 208)
        self._limb(p, [(152, 135), right_elbow, wrist], "#eaf0f7", 16)
        p.setBrush(QColor("#6adaff"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(*right_elbow), 5, 5)
        # Head: bright silver hair, preserved character portrait cropped under a mask.
        hair = QPainterPath()
        hair.addEllipse(QRectF(68, 34, 103, 113))
        p.setPen(QPen(QColor("#b2c8d9"), 2))
        p.setBrush(QColor("#cdd6e6"))
        p.drawPath(hair)
        if not self.face.isNull():
            p.save()
            face_clip = QPainterPath()
            face_clip.addEllipse(QRectF(80, 44, 79, 90))
            p.setClipPath(face_clip)
            src = QRectF(self.face.width() * .24, self.face.height() * .10,
                         self.face.width() * .67, self.face.height() * .55)
            p.drawPixmap(QRectF(77, 39, 88, 106), self.face, src)
            p.restore()
        else:
            p.setBrush(QColor("#f7d5cb"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(86, 51, 69, 85))
            p.setBrush(QColor("#56d4ff"))
            p.drawEllipse(QPointF(107, 96), 6, 5)
            p.drawEllipse(QPointF(138, 96), 6, 5)
        # Silver fringe and soft hair edges remain visible over the portrait.
        p.setPen(QPen(QColor("#edf3fc"), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(78, 35, 85, 48), 2 * 16, 145 * 16)
        p.setPen(QPen(QColor("#cad7e6"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(78, 70), QPointF(69, 134))
        p.drawLine(QPointF(166, 76), QPointF(172, 136))
        # Five articulating fingers rendered after the arm and face.
        self._draw_hand(p, wrist, self.grip)
        if self.pose == "portal":
            p.setPen(QPen(QColor("#83eaff"), 4))
            p.setBrush(QColor(54, 178, 245, 21))
            p.drawEllipse(QRectF(21, 4, 190, 303))
        p.restore()
        p.end()
