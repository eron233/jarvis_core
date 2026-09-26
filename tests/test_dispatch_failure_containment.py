"""Testes da contencao de falhas de worker no despacho do runtime."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


class ExplodingWorker:
    """Worker que falha, para exercitar o limite de contencao do runtime."""

    worker_id = "runtime"

    def handle(self, task: dict) -> dict:
        raise RuntimeError("falha interna do worker")


class SilentWorker:
    """Worker que devolve algo que nao e um dicionario."""

    worker_id = "runtime"

    def handle(self, task: dict) -> dict:
        return None  # type: ignore[return-value]


class DispatchFailureContainmentTests(unittest.TestCase):
    """Uma falha de worker nao pode derrubar o ciclo nem sumir da auditoria."""

    def build_runtime(self, name: str) -> InternalAgentRuntime:
        """Monta um runtime isolado com armazenamento proprio do teste."""

        base = PROJECT_ROOT / "tests" / "_dispatch_artifacts" / name
        base.mkdir(parents=True, exist_ok=True)
        for arquivo in base.glob("*.json"):
            arquivo.unlink()

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=base / "queue.json")
        runtime.audit_logger = AuditLogger(storage_path=base / "audit.json")
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=base / "semantic.json"),
            "procedural": ProceduralMemory(),
        }
        runtime.bootstrap()
        return runtime

    @staticmethod
    def build_task(task_id: str) -> dict:
        """Tarefa simples e aprovada, para chegar ate o worker."""

        return {
            "task_id": task_id,
            "goal": "Exercitar a contencao de falha",
            "description": "Tarefa de teste que alcanca o worker",
            "domain": "runtime",
            "worker": "worker_runtime",
            "effect_scope": "internal",
            "approved": True,
        }

    def test_excecao_do_worker_vira_falha_estruturada(self) -> None:
        """
        Sem contencao a excecao subiria pelo planner e abortaria o ciclo inteiro.

        Agora ela para no limite do worker e volta no mesmo formato dos demais
        caminhos de falha do despacho.
        """

        runtime = self.build_runtime("excecao")
        runtime.workers["runtime"] = ExplodingWorker()

        resultado = runtime.dispatch_task(self.build_task("falha-1"))

        self.assertEqual(resultado["status"], "failed")
        self.assertEqual(resultado["reason"], "worker_exception")
        self.assertEqual(resultado["reason_ptbr"], "worker_lancou_excecao")
        self.assertEqual(resultado["worker_response"]["error_type"], "RuntimeError")

    def test_tarefa_que_falha_nao_fica_em_estado_nao_terminal(self) -> None:
        """A tarefa precisa terminar marcada como falha, e nao pendente."""

        runtime = self.build_runtime("estado")
        runtime.workers["runtime"] = ExplodingWorker()

        tarefa = self.build_task("falha-2")
        runtime.dispatch_task(tarefa)

        self.assertEqual(tarefa["state"], "failed")

    def test_falha_do_worker_chega_a_auditoria(self) -> None:
        """
        O runtime ja tinha um watchdog para isso, mas o caminho de despacho
        nunca o acionava: a falha nao deixava rastro.
        """

        runtime = self.build_runtime("auditoria")
        runtime.workers["runtime"] = ExplodingWorker()

        runtime.dispatch_task(self.build_task("falha-3"))

        entradas = runtime.audit_logger.snapshot()["entries"]
        eventos = [entrada.get("event") for entrada in entradas]
        self.assertIn("runtime_watchdog", eventos)

    def test_falha_do_worker_e_lembrada_na_memoria_episodica(self) -> None:
        """O episodio de despacho precisa existir como qualquer outro."""

        runtime = self.build_runtime("episodica")
        runtime.workers["runtime"] = ExplodingWorker()

        runtime.dispatch_task(self.build_task("falha-4"))

        eventos = runtime.memory["episodic"].recent(limit=10)
        despachos = [evento for evento in eventos if evento.get("event") == "dispatch"]
        self.assertTrue(despachos)
        self.assertEqual(despachos[-1]["status"], "failed")

    def test_resposta_de_worker_invalida_e_recusada(self) -> None:
        """Um worker que devolve algo fora do contrato nao pode quebrar o despacho."""

        runtime = self.build_runtime("resposta_invalida")
        runtime.workers["runtime"] = SilentWorker()

        resultado = runtime.dispatch_task(self.build_task("falha-5"))

        self.assertEqual(resultado["status"], "failed")
        self.assertEqual(resultado["reason"], "invalid_worker_response")

    def test_runtime_continua_utilizavel_apos_a_falha(self) -> None:
        """O ciclo seguinte precisa funcionar; a falha e de uma tarefa, nao do sistema."""

        runtime = self.build_runtime("continuidade")
        runtime.workers["runtime"] = ExplodingWorker()
        runtime.dispatch_task(self.build_task("falha-6"))

        estado = runtime.describe_state()
        self.assertEqual(estado["status"], "initialized")
        ciclo = runtime.run_planner_cycle()
        self.assertIsInstance(ciclo, dict)


if __name__ == "__main__":
    unittest.main()
