"""Regressões para configuração de exemplo e documentação enxuta.

Não remove arquivos de usuários nem dados operacionais durante os testes.
"""
from pathlib import Path
import unittest

from memory_system.advanced_memory import AdvancedMemoryConfig


ROOT = Path(__file__).resolve().parents[1]


class RepositoryHygieneTests(unittest.TestCase):
    def test_environment_example_does_not_duplicate_active_keys(self):
        entries = [
            line.partition("=")[0]
            for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "=" in line
        ]
        self.assertEqual(len(entries), len(set(entries)))
        self.assertIn("JARVIS_OLLAMA_BASE_URL", entries)
        self.assertIn("JARVIS_MEM0_OLLAMA_BASE_URL", entries)

    def test_mem0_can_use_different_endpoint_from_inference(self):
        config = AdvancedMemoryConfig.from_env(
            environ={
                "JARVIS_OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
                "JARVIS_MEM0_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            },
            project_root=ROOT,
        )
        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")

    def test_mem0_legacy_url_remains_supported(self):
        config = AdvancedMemoryConfig.from_env(
            environ={"JARVIS_OLLAMA_BASE_URL": "http://localhost:11434"},
            project_root=ROOT,
        )
        self.assertEqual(config.ollama_base_url, "http://localhost:11434")

    def test_readme_keeps_owner_only_and_limits_explicit(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Íris Original", readme)
        self.assertIn("device.local", readme)
        self.assertIn("dois computadores", readme.lower())
        self.assertLess(len(readme), 12000)

    def test_generated_report_dir_is_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("reports/*", ignore)
        self.assertIn("!reports/.gitkeep", ignore)
        self.assertNotIn("!reports/relatorios_txt/", ignore)


if __name__ == "__main__":
    unittest.main()
