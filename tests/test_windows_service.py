"""Testes leves do launcher do servico Windows do Jarvis."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from service.jarvis_windows_service import build_runtime_command


class WindowsServiceTests(unittest.TestCase):
    """Valida apenas o contrato leve do servico, sem instalar no Windows durante os testes."""

    def test_build_runtime_command_uses_runtime_server_module(self) -> None:
        """Confirma que o servico sobe o entrypoint unificado do servidor por script."""

        command = build_runtime_command(
            python_executable=Path(r"C:\Python\python.exe"),
            project_root=PROJECT_ROOT,
        )

        self.assertEqual(command[0], r"C:\Python\python.exe")
        self.assertEqual(command[1], str(PROJECT_ROOT / "runtime" / "server.py"))


if __name__ == "__main__":
    unittest.main()
