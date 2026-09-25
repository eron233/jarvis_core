"""Testes das novas intencoes conversacionais de handle_command (runtime/internal_agent_runtime.py)."""

from pathlib import Path
import shutil
import sys
import unittest
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry
from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from intent_layer.goal_manager import GoalManager
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.graphify_engine import GraphifyEngine
from runtime.internal_agent_runtime import InternalAgentRuntime
from security.access_control import AccessControl
from security.lightweight_sandbox_engine import UltraLightweightSandboxEngine
from security.vulnerability_hunter import AgenticVulnerabilityHunter

ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "_command_intents_artifacts"
ADMIN_PASSWORD = "senha-de-teste-comandos"


class _FakeWebBrowserEngine:
    """Dublê deterministico do motor de pesquisa web, sem depender de rede."""

    def __init__(self) -> None:
        self.last_query: Optional[str] = None

    def search_and_extract(self, query: str, max_results: int = 3, html_content=None) -> Dict[str, Any]:
        self.last_query = query
        return {
            "pesquisa": query,
            "realizada_em": "2026-09-25T00:00:00+00:00",
            "status": "sucesso",
            "total_fontes_encontradas": 2,
            "fontes": [
                {"posicao": 1, "url": "https://exemplo.com/1", "titulo": "Fonte 1", "resumo_snippet": "trecho 1"},
                {"posicao": 2, "url": "https://exemplo.com/2", "titulo": "Fonte 2", "resumo_snippet": "trecho 2"},
            ],
        }


def make_artifact_path(name: str, suffix: str) -> Path:
    """Retorna o path isolado usado nos testes de intencoes de comando."""

    return ARTIFACTS_DIR / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa o artefato antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def build_runtime(name: str) -> InternalAgentRuntime:
    """Constroi um runtime totalmente isolado (sem tocar em dados reais do projeto) e o inicializa."""

    queue_path = make_artifact_path(name, "queue")
    goals_path = make_artifact_path(name, "goals")
    device_path = make_artifact_path(name, "devices")
    semantic_path = make_artifact_path(name, "semantic")
    procedural_path = make_artifact_path(name, "procedural")
    audit_path = make_artifact_path(name, "audit")
    for path in (queue_path, goals_path, device_path, semantic_path, procedural_path, audit_path):
        reset_storage_path(path)

    runtime = InternalAgentRuntime()
    runtime.task_queue = TaskQueue(storage_path=queue_path)
    runtime.goal_manager = GoalManager(storage_path=goals_path)
    runtime.device_registry = DeviceRegistry(storage_path=device_path)
    runtime.audit_logger = AuditLogger(storage_path=audit_path)
    runtime.memory = {
        "episodic": EpisodicMemory(),
        "semantic": SemanticMemory(storage_path=semantic_path),
        "procedural": ProceduralMemory(storage_path=procedural_path),
    }
    runtime.access_control = AccessControl.from_plaintext(ADMIN_PASSWORD)

    runtime.bootstrap()

    # Apos o bootstrap (que roda uma unica vez), substituimos os motores reais por
    # instancias isoladas em diretorios de teste (ou por um duble deterministico,
    # no caso da pesquisa web, que depende de rede).
    vuln_dir = ARTIFACTS_DIR / f"{name}_vulnerability_reports"
    graphify_dir = ARTIFACTS_DIR / f"{name}_graphify_analyses"
    sandbox_dir = ARTIFACTS_DIR / f"{name}_sandbox_runs"
    for directory in (vuln_dir, graphify_dir, sandbox_dir):
        if directory.exists():
            shutil.rmtree(directory)

    runtime.vulnerability_hunter = AgenticVulnerabilityHunter(
        tool_evolver=runtime.subagent_tool_evolver,
        data_dir=vuln_dir,
        project_root=PROJECT_ROOT,
    )
    runtime.graphify_engine = GraphifyEngine(data_dir=graphify_dir)
    runtime.lightweight_sandbox_engine = UltraLightweightSandboxEngine(data_dir=sandbox_dir)
    runtime.web_browser_engine = _FakeWebBrowserEngine()

    return runtime


class CommandIntentTests(unittest.TestCase):
    """Valida as novas intencoes conversacionais conectadas aos motores reais do runtime."""

    def test_web_search_intent_uses_web_browser_engine(self) -> None:
        """Confirma que um comando de pesquisa aciona o motor de pesquisa web e resume as fontes."""

        runtime = build_runtime("web_search")
        response = runtime.handle_command("pesquisar sobre inteligencia artificial responsavel")

        self.assertEqual(response["acao"], "web_search")
        self.assertTrue(response["dados_relacionados"])
        self.assertEqual(response["dados_relacionados"]["status"], "sucesso")
        self.assertEqual(response["dados_relacionados"]["total_fontes_encontradas"], 2)
        self.assertIn("2", response["resposta"])
        self.assertEqual(runtime.web_browser_engine.last_query, "inteligencia artificial responsavel")

    def test_graphify_intent_uses_graphify_engine(self) -> None:
        """Confirma que um comando de graphify aciona o motor topologico real."""

        runtime = build_runtime("graphify")
        response = runtime.handle_command(
            "faça um graphify do projeto: API, banco de dados e fila de mensagens"
        )

        self.assertEqual(response["acao"], "graphify_analysis")
        self.assertTrue(response["dados_relacionados"])
        estatisticas = response["dados_relacionados"]["estatisticas"]
        self.assertGreater(estatisticas["total_nos"], 0)
        self.assertGreaterEqual(estatisticas["total_arestas"], 0)

    def test_code_security_analysis_requires_sensitive_access(self) -> None:
        """Confirma que a analise de seguranca do codigo e negada sem autenticacao administrativa."""

        runtime = build_runtime("code_security_denied")
        response = runtime.handle_command("faça uma analise de seguranca do codigo")

        self.assertEqual(response["acao"], "restricted_command")
        self.assertEqual(response["status"], "denied")

    def test_code_security_analysis_uses_vulnerability_hunter(self) -> None:
        """Confirma que, com acesso administrativo, a analise de codigo usa o cacador de vulnerabilidades real."""

        runtime = build_runtime("code_security_ok")
        response = runtime.handle_command(
            "faça uma analise de seguranca do codigo em runtime/graphify_engine.py",
            password=ADMIN_PASSWORD,
        )

        self.assertEqual(response["acao"], "code_security_analysis")
        self.assertTrue(response["dados_relacionados"])
        self.assertIn("total_achados", response["dados_relacionados"])
        self.assertIn("achados_por_severidade", response["dados_relacionados"])

    def test_jev_decision_intent_returns_honest_guidance(self) -> None:
        """Confirma que um comando de decisao JEV sem opcoes estruturadas retorna orientacao honesta."""

        runtime = build_runtime("jev_decision")
        response = runtime.handle_command("preciso decidir o que fazer agora")

        self.assertEqual(response["acao"], "jev_decision_guidance")
        self.assertTrue(response["dados_relacionados"])
        self.assertTrue(response["dados_relacionados"]["requer_opcoes_estruturadas"])
        self.assertIn("/api/decisao/jev/avaliar", response["dados_relacionados"]["endpoint_recomendado"])

    def test_sandbox_intent_without_code_returns_honest_guidance(self) -> None:
        """Confirma que pedir sandbox sem codigo explicito nao executa nada e orienta o endpoint da API."""

        runtime = build_runtime("sandbox_guidance")
        response = runtime.handle_command("quero rodar isso na sandbox", password=ADMIN_PASSWORD)

        self.assertEqual(response["acao"], "sandbox_guidance")
        self.assertTrue(response["dados_relacionados"])
        self.assertIn("/api/seguranca/micro-sandbox/executar", response["dados_relacionados"]["endpoint_recomendado"])

    def test_sandbox_intent_requires_sensitive_access(self) -> None:
        """Confirma que o pedido de sandbox e negado sem autenticacao administrativa."""

        runtime = build_runtime("sandbox_denied")
        response = runtime.handle_command("executar codigo na sandbox")

        self.assertEqual(response["acao"], "restricted_command")
        self.assertEqual(response["status"], "denied")

    def test_sandbox_intent_with_explicit_code_executes_in_microsandbox(self) -> None:
        """Confirma que, com codigo explicito e acesso administrativo, o motor de micro-sandbox real e usado."""

        runtime = build_runtime("sandbox_exec")
        command = "execute este codigo na sandbox:\n```python\nresultado = 1 + 1\n```"
        response = runtime.handle_command(command, password=ADMIN_PASSWORD)

        self.assertEqual(response["acao"], "sandbox_execution")
        self.assertTrue(response["dados_relacionados"])
        self.assertIn("status", response["dados_relacionados"])

    def test_help_message_lists_new_intents(self) -> None:
        """Confirma que a mensagem de ajuda padrao agora menciona as novas intencoes."""

        runtime = build_runtime("help")
        response = runtime.handle_command("comando totalmente desconhecido xyz")

        self.assertEqual(response["acao"], "help")
        for keyword in ("pesquisa", "graphify", "vulnerabilidades", "sandbox", "jev"):
            self.assertIn(keyword, response["resposta"].lower())


if __name__ == "__main__":
    unittest.main()
