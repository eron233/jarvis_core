"""Íris chibi: presets, rendering, autostart and standalone executable intent."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from interface.native_app.iris_startup import StartupError, startup_command, startup_supported
from interface.native_app.iris_puppet import SIZE_PRESETS, STYLES, valid_scale


class IrisConfigurationTests(unittest.TestCase):
    def test_all_styles_defined(self):
        self.assertEqual(set(STYLES), {"nova", "padrao", "madura"})
        self.assertEqual(set(SIZE_PRESETS), {"mini", "normal", "grande"})
        self.assertLess(SIZE_PRESETS["mini"], SIZE_PRESETS["normal"])
        self.assertLess(SIZE_PRESETS["normal"], SIZE_PRESETS["grande"])

    def test_user_scale_is_bounded(self):
        self.assertEqual(valid_scale(.1), .40)
        self.assertEqual(valid_scale(5), 2.15)
        with self.assertRaises(ValueError):
            valid_scale(float("nan"))

    def test_startup_command_has_explicit_mascot_only_flag(self):
        executable = Path("C:/Program Files/Genesis/Genesis.exe")
        self.assertEqual(startup_command(executable).count("--mascot-only"), 1)
        self.assertTrue(startup_command(executable).startswith('"'))
        with self.assertRaises(StartupError):
            startup_command("python.exe")

    def test_startup_requires_packaged_windows_and_opt_in(self):
        with patch("interface.native_app.iris_startup.sys.platform", "linux"), patch(
            "interface.native_app.iris_startup.sys.frozen", True, create=True
        ):
            self.assertFalse(startup_supported())

    def test_installer_is_explicit_and_has_validate_only_mode(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "installation" / "Instalar-Iris.ps1").read_text(encoding="utf-8")
        launcher = (root / "installation" / "Instalar-Iris.cmd").read_text(encoding="utf-8")
        self.assertIn("$ValidateOnly", installer)
        self.assertIn("Start-Process -FilePath $installed", installer)
        self.assertIn("if ($StartWithWindows)", installer)
        self.assertIn("HKCU:", installer)
        self.assertIn("Instalar-Iris.ps1", launcher)


try:
    from PySide6.QtWidgets import QApplication
    from interface.native_app.iris_puppet import IrisPuppet
    from interface.native_app.iris_mascot import IrisMascotWindow
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


class MemorySettings:
    def __init__(self): self.data = {}
    def value(self, key, default=None, type=None): return self.data.get(key, default)
    def setValue(self, key, value): self.data[key] = value


@unittest.skipUnless(QT_AVAILABLE, "PySide6 opcional")
class IrisVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_visual_ages_render_and_are_distinct(self):
        puppet = IrisPuppet()
        puppet.show()
        images = []
        for style in STYLES:
            puppet.set_visual_age(style)
            self.app.processEvents()
            frame = puppet.grab()
            self.assertFalse(frame.isNull())
            images.append(frame.toImage().pixelColor(119, 97).name())
        self.assertEqual(puppet.visual_age, "madura")
        puppet.close()

    def test_scale_resizes_actual_overlay_and_hand_alignment(self):
        settings = MemorySettings()
        mascot = IrisMascotWindow(settings=settings)
        self.assertEqual(mascot.puppet.visual_age, "nova")
        self.assertAlmostEqual(mascot.puppet.scale_factor, SIZE_PRESETS["mini"])
        for value in (.56, 1.0, 1.45, 1.89):
            mascot.set_scale(value)
            self.assertEqual(mascot.size(), mascot.puppet.size())
            self.assertAlmostEqual(mascot.puppet.scale_factor, value)
            hx, hy = mascot._hand_global_position()
            self.assertEqual(hx, mascot.x() + round(201 * value))
            self.assertEqual(hy, mascot.y() + round(146 * value))
        self.assertEqual(settings.data["iris_mascot/scale"], 1.89)
        mascot.close()

    def test_saved_preferences_survive_restart(self):
        settings = MemorySettings()
        mascot = IrisMascotWindow(settings=settings)
        mascot.set_scale(.73)
        mascot.set_visual_age("madura")
        mascot.close()
        other = IrisMascotWindow(settings=settings)
        self.assertAlmostEqual(other.puppet.scale_factor, .73)
        self.assertEqual(other.puppet.visual_age, "madura")
        with self.assertRaises(ValueError):
            other.set_visual_age("inventado")
        other.close()

    def test_mascot_only_cli_flag_skips_runtime(self):
        from interface.native_app.main import build_arg_parser
        args = build_arg_parser().parse_args(["--mascot-only", "--auto-close-ms", "100"])
        self.assertTrue(args.mascot_only)
        self.assertEqual(args.auto_close_ms, 100)


if __name__ == "__main__":
    unittest.main()
