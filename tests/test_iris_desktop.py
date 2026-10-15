"""Regressoes da geometria e do laboratorio visual da Iris."""
from __future__ import annotations

import os
import unittest

from interface.native_app.iris_desktop import (
    clamp_to_screens, next_monitor_position, nearest_edge_position,
)


class DesktopGeometryTests(unittest.TestCase):
    def test_no_monitor_is_noop(self):
        self.assertEqual(clamp_to_screens((99, -9), (180, 230), []), (99, -9))

    def test_negative_monitor_coordinates(self):
        screens = [(-1920, -100, 1920, 1080), (0, 0, 1920, 1080)]
        self.assertEqual(clamp_to_screens((-1850, 300), (180, 200), screens), (-1850, 300))
        self.assertEqual(next_monitor_position((-1850, 300), (180, 200), screens), (870, 440))
        self.assertEqual(next_monitor_position((870, 440), (180, 200), screens), (-1050, 340))

    def test_outside_screen_never_remains_outside(self):
        screens = [(0, 0, 300, 200)]
        self.assertEqual(clamp_to_screens((900, -1000), (120, 80), screens), (180, 0))
        self.assertEqual(clamp_to_screens((900, 300), (400, 300), screens), (0, 0))

    def test_gap_between_screens_is_not_target(self):
        screens = [(0, 0, 1024, 768), (1500, -400, 1920, 1080)]
        target = next_monitor_position((100, 200), (170, 200), screens)
        self.assertGreaterEqual(target[0], 1500)
        self.assertLessEqual(target[0], 1500 + 1920 - 170)

    def test_dock_to_real_edge(self):
        screens = [(0, 0, 1024, 768)]
        target = nearest_edge_position((900, 250), (180, 220), screens)
        self.assertEqual(target[0], 838)

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from interface.native_app.iris_lab import IrisLabWindow, IrisPortalDoor
    from interface.native_app.iris_mascot import IrisMascotWindow
    QT_READY = True
except ImportError:
    QT_READY = False


class FakeSettings:
    def __init__(self):
        self.data = {}
    def value(self, key, default=None, type=None):
        return self.data.get(key, default)
    def setValue(self, key, value):
        self.data[key] = value


@unittest.skipUnless(QT_READY, "Qt nao instalado")
class IrisDesktopQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mascot_is_top_level_and_can_hide(self):
        win = IrisMascotWindow(settings=FakeSettings())
        self.assertTrue(win.windowFlags() & __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.FramelessWindowHint)
        win.show()
        self.app.processEvents()
        self.assertTrue(win.isVisible())
        win.hide()
        self.assertFalse(win.isVisible())
        win.close()

    def test_move_and_persist_location(self):
        settings = FakeSettings()
        win = IrisMascotWindow(settings=settings)
        win.show()
        self.app.processEvents()
        win.move_to((120, 130), animated=False)
        win.save_position()
        self.assertEqual(settings.data["iris_mascot/x"], win.x())
        self.assertEqual(settings.data["iris_mascot/y"], win.y())
        win.close()

    def test_portal_is_actual_animation_and_finishes(self):
        door = IrisPortalDoor()
        fired = []
        door.entered.connect(lambda: fired.append(True))
        door.enter(instant=True)
        self.assertEqual(fired, [True])
        self.assertEqual(door.openness, 1.0)
        door.reset()
        self.assertEqual(door.openness, 0.0)
        door.close()

    def test_lab_has_movable_tabs(self):
        from PySide6.QtWidgets import QGraphicsItem
        lab = IrisLabWindow()
        self.assertEqual(len(lab.cards), 3)
        self.assertTrue(all(card.flags() & QGraphicsItem.ItemIsMovable for card in lab.cards))
        lab.close()

    def test_mascot_enters_lab_and_returns(self):
        win = IrisMascotWindow(settings=FakeSettings())
        win.show()
        win.open_lab(instant=True)
        self.app.processEvents()
        self.assertIsNotNone(win.lab)
        self.assertTrue(win.lab.isVisible())
        self.assertFalse(win.isVisible())
        win.lab.close()
        self.app.processEvents()
        self.assertTrue(win.isVisible())
        win.close()


if __name__ == "__main__":
    unittest.main()
