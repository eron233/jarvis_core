"""Testes unitarios para a camada real de objetivos do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.prioritizer import Prioritizer
from executive_planner.queue import TaskQueue
from intent_layer.goal_manager import GoalManager
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_goal_storage_path(name: str) -> Path:
    """Retorna o path de goals usado nos testes da camada de objetivos."""

    return PROJECT_ROOT / "tests" / "_goal_artifacts" / f"{name}_goals.json"


def make_queue_storage_path(name: str) -> Path:
    """Retorna o path de fila usado nos cenarios de objetivo."""

    return PROJECT_ROOT / "tests" / "_goal_artifacts" / f"{name}_queue.json"


def make_semantic_storage_path(name: str) -> Path:
    """Retorna o path de memoria semantica usado nos testes de objetivos."""

    return PROJECT_ROOT / "tests" / "_goal_artifacts" / f"{name}_semantic.json"


def reset_storage_path(path: Path) -> None:
    """Limpa um arquivo de artefato antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class GoalManagerTests(unittest.TestCase):
    """Valida persistencia, vinculacao e progresso da camada de objetivos."""

    def test_goal_manager_separates_metas_estrategicas_e_objetivos_ativos(self) -> None:
        """Confirma a separacao entre metas estrategicas e objetivos ativos."""

        storage_path = make_goal_storage_path("structure")
        reset_storage_path(storage_path)
        goal_manager = GoalManager(storage_path=storage_path)

        strategic_goal = goal_manager.add_strategic_goal(
            title="Expandir capacidades cognitivas",
            description="Direcao macro do sistema",
            priority=9,
        )
        active_goal = goal_manager.add_active_goal(
            title="Organizar plano de estudo",
            description="Objetivo operacional corrente",
            priority=5,
            deadline="2026-03-20",
        )

        report = goal_manager.goal_report()

        self.assertEqual(strategic_goal["kind"], "strategic")
        self.assertEqual(active_goal["kind"], "active")
        self.assertEqual(report["resumo"]["total_metas_estrategicas"], 1)
        self.assertEqual(report["resumo"]["total_objetivos_ativos"], 1)
        self.assertEqual(report["metas_estrategicas"][0]["estado_ptbr"], "rascunho")
        self.assertEqual(report["objetivos_ativos"][0]["estado_ptbr"], "ativa")
        self.assertEqual(goal_manager.get_goal(active_goal["goal_id"])["deadline"], "2026-03-20")

    def test_link_task_to_goal_propagates_metadata_for_queue_and_priority(self) -> None:
        """Verifica propagacao de contexto do objetivo para fila e priorizacao."""

        goal_storage_path = make_goal_storage_path("link")
        queue_storage_path = make_queue_storage_path("link")
        reset_storage_path(goal_storage_path)
        reset_storage_path(queue_storage_path)

        goal_manager = GoalManager(storage_path=goal_storage_path)
        active_goal = goal_manager.add_active_goal(
            title="Revisar organizacao financeira",
            priority=7,
        )
        linked_task = goal_manager.link_task_to_goal(
            {
                "task_id": "goal-task-1",
                "goal": "Revisar organizacao financeira",
                "domain": "finance",
                "impact": 1,
                "urgency": 1,
            },
            active_goal["goal_id"],
        )

        queue = TaskQueue(storage_path=queue_storage_path)
        enqueued_task = queue.enqueue(linked_task)

        self.assertEqual(enqueued_task["parent_goal_id"], active_goal["goal_id"])
        self.assertEqual(enqueued_task["parent_goal"], "Revisar organizacao financeira")
        self.assertEqual(enqueued_task["goal_priority"], 7)
        self.assertGreater(Prioritizer().score(enqueued_task), 700)
        self.assertEqual(goal_manager.goal_report(active_goal["goal_id"])["tarefas_vinculadas"], 1)

    def test_runtime_updates_goal_progress_after_task_execution(self) -> None:
        """Confirma atualizacao de progresso apos execucao real no runtime."""

        goal_storage_path = make_goal_storage_path("runtime")
        queue_storage_path = make_queue_storage_path("runtime")
        semantic_storage_path = make_semantic_storage_path("runtime")
        reset_storage_path(goal_storage_path)
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)

        goal_manager = GoalManager(storage_path=goal_storage_path)
        active_goal = goal_manager.add_active_goal(
            title="Executar revisao de estudo",
            priority=4,
        )

        runtime = InternalAgentRuntime()
        runtime.goal_manager = goal_manager
        runtime.task_queue = TaskQueue(storage_path=queue_storage_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_storage_path),
            "procedural": ProceduralMemory(),
        }
        runtime.enqueue_task(
            {
                "task_id": "study-goal-1",
                "goal": "Executar revisao de estudo",
                "description": "Executar revisao de estudo",
                "domain": "study",
                "worker": "worker_study",
                "impact": 2,
                "urgency": 2,
                "parent_goal_id": active_goal["goal_id"],
            }
        )

        result = runtime.run_planner_cycle()
        goal_report = runtime.get_goal_report(active_goal["goal_id"])

        self.assertEqual(result["status"], "executed")
        self.assertEqual(goal_report["estado"], "completed")
        self.assertEqual(goal_report["estado_ptbr"], "concluida")
        self.assertEqual(goal_report["progresso"], 100)
        self.assertEqual(goal_report["tarefas_concluidas"], 1)
        self.assertEqual(runtime.describe_state()["active_goal_count"], 0)


if __name__ == "__main__":
    unittest.main()
