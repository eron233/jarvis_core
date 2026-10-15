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

    def test_studio_room_matches_reference_environment(self):
        from PySide6.QtGui import QPixmap
        from interface.native_app.iris_lab import IrisLabWindow
        self.assertTrue(IrisLabWindow.ROOM_IMAGE.is_file())
        self.assertFalse(QPixmap(str(IrisLabWindow.ROOM_IMAGE)).isNull())
        room = IrisLabWindow()
        self.assertIsNotNone(room.room_background)
        self.assertEqual(len(room.cards), 3)
        self.assertIn("HOME OFFICE", room.findChildren(
            __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
        )[1].text())
        room.close()

    def test_studio_room_drag_reset_and_lighting(self):
        room = IrisLabWindow()
        initial = room.cards[0].pos()
        room.cards[0].moveBy(190, -80)
        self.assertNotEqual(room.cards[0].pos(), initial)
        room.reset_cards()
        self.assertEqual(room.cards[0].pos(), initial)
        self.assertFalse(room._lights_dimmed)
        room.toggle_lights()
        self.assertTrue(room._lights_dimmed)
        room.toggle_lights()
        self.assertFalse(room._lights_dimmed)
        room.close()

    def test_lab_has_movable_tabs(self):
        from PySide6.QtWidgets import QGraphicsItem
        lab = IrisLabWindow()
        self.assertEqual(len(lab.cards), 3)
        self.assertTrue(all(card.flags() & QGraphicsItem.ItemIsMovable for card in lab.cards))
        lab.close()


    def test_portal_is_actually_shown_and_completes_animation(self):
        from PySide6.QtTest import QTest
        mascot = IrisMascotWindow(settings=FakeSettings())
        mascot.show()
        self.app.processEvents()
        mascot.open_lab()
        self.assertTrue(mascot.door.isVisible())
        self.assertTrue(mascot._portal_pending)
        QTest.qWait(750)
        self.assertFalse(mascot._portal_pending)
        self.assertFalse(mascot.door.isVisible())
        self.assertIsNotNone(mascot.lab)
        self.assertTrue(mascot.lab.isVisible())
        self.assertTrue(mascot.lab.lab_actor_proxy.isVisible())
        mascot.lab.close()
        mascot.close()

    def test_portal_can_be_cancelled_before_entry(self):
        from PySide6.QtTest import QTest
        mascot = IrisMascotWindow(settings=FakeSettings())
        mascot.show()
        mascot.open_lab()
        mascot.hide_by_user()
        QTest.qWait(700)
        self.assertFalse(mascot._portal_pending)
        self.assertIsNone(mascot.lab)
        mascot.close()

    def test_studio_iris_keeps_chosen_identity(self):
        mascot = IrisMascotWindow(settings=FakeSettings())
        mascot.set_visual_age("madura")
        mascot.show()
        mascot.open_lab(instant=True)
        self.app.processEvents()
        self.assertEqual(mascot.lab.lab_actor.visual_age, "madura")
        self.assertEqual(mascot.lab.lab_actor_proxy.zValue(), 2)
        mascot.lab.close()
        mascot.open_lab(instant=True)
        self.app.processEvents()
        self.assertTrue(mascot.lab.lab_actor.motion_timer.isActive())
        mascot.lab.close()
        mascot.close()

    def test_seated_iris_follows_window_without_moving_it(self):
        from interface.native_app.iris_window_bridge import WindowEdge
        class Bridge:
            def __init__(self):
                self.target = WindowEdge(99, "Editor", 100, 400, 600, 320)
                self.moves = 0
            def find_edge(self, point, max_distance=96):
                return self.target
            def current_edge(self, hwnd):
                return self.target
            def move(self, target, dx, dy):
                self.moves += 1
                return True
        bridge = Bridge()
        mascot = IrisMascotWindow(settings=FakeSettings(), bridge=bridge)
        mascot.show()
        self.assertTrue(mascot.sit_on_nearest_window())
        self.assertTrue(mascot._seat_timer.isActive())
        self.assertEqual(mascot.puppet.pose, "sit")
        initial_y = mascot.y()
        bridge.target = WindowEdge(99, "Editor", 160, 440, 600, 320)
        mascot._maintain_seat()
        self.assertGreater(mascot.y(), initial_y)
        self.assertEqual(mascot.puppet.pose, "sit")
        self.assertEqual(bridge.moves, 0)
        bridge.target = None
        mascot._maintain_seat()
        self.assertFalse(mascot._seat_timer.isActive())
        self.assertEqual(mascot.puppet.pose, "idle")
        mascot.close()

    def test_user_drag_stops_seat_tracking(self):
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        from interface.native_app.iris_window_bridge import WindowEdge
        class Bridge:
            target = WindowEdge(88, "Editor", 100, 400, 600, 350)
            def find_edge(self, point, max_distance=96):
                return self.target
            def current_edge(self, hwnd):
                return self.target
        mascot = IrisMascotWindow(settings=FakeSettings(), bridge=Bridge())
        mascot.show()
        self.assertTrue(mascot.sit_on_nearest_window())
        QTest.mousePress(mascot.puppet, Qt.LeftButton, Qt.NoModifier, QPoint(50, 70))
        self.assertIsNone(mascot._seat_target)
        self.assertFalse(mascot._seat_timer.isActive())
        QTest.mouseRelease(mascot.puppet, Qt.LeftButton, Qt.NoModifier, QPoint(50, 70))
        mascot.close()

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
