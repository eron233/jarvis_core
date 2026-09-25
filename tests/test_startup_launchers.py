import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestStartupLaunchers(unittest.TestCase):
    def test_bat_launcher_exists(self):
        bat_file = PROJECT_ROOT / "INICIAR_JARVIS.bat"
        self.assertTrue(bat_file.exists())
        content = bat_file.read_text(encoding="utf-8")
        self.assertIn("http://localhost:8000/painel", content)
        self.assertIn("python main.py", content)

    def test_sh_launcher_exists(self):
        sh_file = PROJECT_ROOT / "INICIAR_JARVIS.sh"
        self.assertTrue(sh_file.exists())
        content = sh_file.read_text(encoding="utf-8")
        self.assertIn("http://localhost:8000/painel", content)
        self.assertIn("python3 main.py", content)

    def test_cmd_launcher(self):
        cmd_file = PROJECT_ROOT / "jarvis.cmd"
        self.assertTrue(cmd_file.exists())
        content = cmd_file.read_text(encoding="utf-8")
        self.assertIn("http://localhost:8000/painel", content)


if __name__ == "__main__":
    unittest.main()
