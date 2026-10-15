"""Regressões da presença visual da Íris."""
from __future__ import annotations

import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from interface.native_app.iris_state import STATES, normalize_state, state_metadata


class IrisStateTests(unittest.TestCase):
    def test_invalid_state_must_fail_closed(self):
        self.assertEqual(normalize_state("online-inventado"), "offline")
        self.assertEqual(normalize_state(""), "offline")

    def test_every_state_has_metadata(self):
        for state in STATES:
            self.assertEqual(normalize_state(state), state)
            label, detail, color = state_metadata(state)
            self.assertTrue(label and detail and color.startswith("#"))

    def test_svg_is_valid_xml(self):
        for name in ("iris_portrait.svg", "iris_mark.svg"):
            path = Path(__file__).resolve().parents[1] / "interface/native_app/assets" / name
            self.assertEqual(ET.parse(path).getroot().tag, "{http://www.w3.org/2000/svg}svg")

    def test_photo_asset_exists(self):
        path = Path(__file__).resolve().parents[1] / "interface/native_app/assets/iris_photo.jpg"
        self.assertGreater(path.stat().st_size, 1024)


try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from interface.native_app.iris_presence import IrisPresenceWidget
    QT_READY = True
except ImportError:
    QT_READY = False


@unittest.skipUnless(QT_READY, "Qt/PySide6 não instalado")
class IrisQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_real_command_states(self):
        avatar = IrisPresenceWidget()
        self.assertFalse(avatar.portrait.pixmap().isNull())
        self.assertEqual(avatar.state, "offline")
        avatar.set_state("working", "Comando em execução")
        self.assertEqual(avatar.state, "working")
        self.assertIn("Comando em execução", avatar.detail_label.text())
        avatar.set_state("idle", "Resposta concluída.")
        self.assertEqual(avatar.state, "idle")
        avatar.set_state("error")
        self.assertEqual(avatar.state, "error")
        avatar.close()

    def test_reduced_motion_disables_pulse(self):
        old_value = os.environ.get("IRIS_REDUCED_MOTION")
        os.environ["IRIS_REDUCED_MOTION"] = "1"
        try:
            avatar = IrisPresenceWidget()
            avatar.set_state("working")
            self.assertFalse(avatar._timer.isActive())
            avatar.close()
        finally:
            if old_value is None:
                os.environ.pop("IRIS_REDUCED_MOTION", None)
            else:
                os.environ["IRIS_REDUCED_MOTION"] = old_value


if __name__ == "__main__":
    unittest.main()
