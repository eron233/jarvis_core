"""Articulation, hand curl, explicit grip and safe window boundaries."""
from __future__ import annotations

import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from interface.native_app.iris_window_bridge import DesktopWindowBridge, WindowEdge, nearest_edge


class DesktopEdgeTests(unittest.TestCase):
    def setUp(self):
        self.windows = [
            WindowEdge(100, "Editor", 120, 170, 650, 510),
            WindowEdge(200, "Terminal", 900, 280, 460, 390),
        ]

    def test_nearest_window_edge(self):
        self.assertEqual(nearest_edge(self.windows, (170, 175)).hwnd, 100)
        self.assertEqual(nearest_edge(self.windows, (940, 290)).hwnd, 200)

    def test_outside_edges_returns_none(self):
        self.assertIsNone(nearest_edge(self.windows, (90, 800)))
        self.assertIsNone(nearest_edge(self.windows, (400, 650)))

    def test_no_external_move_on_other_operating_systems(self):
        bridge = DesktopWindowBridge()
        if not bridge.supported:
            self.assertEqual(bridge.windows(), [])
            self.assertFalse(bridge.move(self.windows[0], 35, 15))


try:
    from PySide6.QtWidgets import QApplication
    from interface.native_app.iris_puppet import IrisPuppet
    from interface.native_app.iris_mascot import IrisMascotWindow
    from interface.native_app.iris_lab import IrisLabWindow
    QT_READY = True
except ImportError:
    QT_READY = False


class MemorySettings:
    def __init__(self):
        self.data = {}
    def value(self, key, default=None, type=None):
        return self.data.get(key, default)
    def setValue(self, key, value):
        self.data[key] = value


class FakeBridge:
    supported = True
    def __init__(self, found=True, allowed=True):
        self.target = WindowEdge(41, "Fake document", 90, 120, 700, 550)
        self.found = found
        self.allowed = allowed
        self.moves = []
    def find_edge(self, point, max_distance=96):
        return self.target if self.found else None
    def current_edge(self, hwnd):
        return self.target if self.found and hwnd == 41 else None
    def move(self, target, dx, dy):
        if not self.allowed:
            return False
        self.moves.append((target.hwnd, dx, dy))
        return True


@unittest.skipUnless(QT_READY, "PySide6 not installed")
class IrisInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pose_and_grip_are_real_independent_joints(self):
        puppet = IrisPuppet()
        self.assertGreaterEqual(puppet.height(), 300)
        puppet.close_hand(instant=True)
        self.assertEqual(puppet.grip, 1.0)
        puppet.show()
        for pose in ("walk", "sit", "reach", "grip", "pull", "portal"):
            puppet.set_pose(pose)
            self.app.processEvents()
            self.assertFalse(puppet.grab().isNull())
        puppet.open_hand(instant=True)
        self.assertEqual(puppet.grip, 0.0)
        with self.assertRaises(ValueError):
            puppet.set_pose("unsupported")
        puppet.close()

    def test_fingers_curl_over_time(self):
        from PySide6.QtTest import QTest
        puppet = IrisPuppet()
        puppet.show()
        puppet.close_hand()
        QTest.qWait(150)
        self.assertGreater(puppet.grip, 0.0)
        self.assertLess(puppet.grip, 1.0)
        QTest.qWait(450)
        self.assertAlmostEqual(puppet.grip, 1.0, delta=.02)
        puppet.close()

    def test_grip_requires_actual_window(self):
        fake = FakeBridge(found=False)
        mascot = IrisMascotWindow(settings=MemorySettings(), bridge=fake)
        self.assertFalse(mascot.select_window_edge())
        self.assertFalse(mascot.move_gripped_window(30, 8))
        self.assertEqual(fake.moves, [])
        mascot.close()

    def test_explicit_grip_drags_window_then_releases(self):
        fake = FakeBridge()
        mascot = IrisMascotWindow(settings=MemorySettings(), bridge=fake)
        self.assertFalse(mascot.move_gripped_window(20, 8))
        self.assertTrue(mascot.select_window_edge())
        mascot.puppet.close_hand(instant=True)
        self.assertEqual(mascot.puppet.grip, 1.0)
        self.assertTrue(mascot.move_gripped_window(20, 8))
        self.assertEqual(fake.moves, [(41, 20, 8)])
        mascot.release_window()
        self.assertIsNone(mascot._gripped_window)
        self.assertFalse(mascot.move_gripped_window(5, 6))
        mascot.close()

    def test_denied_move_releases_grip(self):
        mascot = IrisMascotWindow(settings=MemorySettings(), bridge=FakeBridge(allowed=False))
        self.assertTrue(mascot.select_window_edge())
        self.assertFalse(mascot.move_gripped_window(5, 6))
        self.assertIsNone(mascot._gripped_window)
        mascot.close()

    def test_sit_and_internal_draggable_tabs(self):
        mascot = IrisMascotWindow(settings=MemorySettings(), bridge=FakeBridge())
        self.assertTrue(mascot.sit_on_nearest_window())
        self.assertEqual(mascot.puppet.pose, "sit")
        room = IrisLabWindow()
        self.assertTrue(room.lab_tabs.tabBar().isMovable())
        self.assertEqual(room.lab_tabs.count(), 3)
        room.close()
        mascot.close()
