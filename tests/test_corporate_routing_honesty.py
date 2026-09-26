"""Testes de que o despacho corporativo relata roteamento, nao execucao."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.corporate_agent_hierarchy import CorporateAgentHierarchyEngine


class CorporateRoutingHonestyTests(unittest.TestCase):
    """O motor escolhe setor e porte do modelo; nao executa a tarefa."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.engine = CorporateAgentHierarchyEngine(data_dir=self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rotear(self, carga: dict | None = None) -> dict:
        """Roteia uma tarefa de engenharia."""

        return self.engine.dispatch_corporate_task(
            department="Engenharia",
            task_title="Refatorar modulo",
            task_payload=carga if carga is not None else {},
            task_complexity="critica",
        )

    def test_nao_afirma_que_a_tarefa_foi_executada(self) -> None:
        """
        O resumo dizia que o sub-agente "executou a tarefa", mas `task_payload`
        nunca era lido e nenhum modelo era chamado.
        """

        relatorio = self.rotear()

        self.assertFalse(relatorio["tarefa_executada"])
        self.assertIn("nao esta ligado", relatorio["motivo_nao_execucao"])
        self.assertIn("roteada", relatorio["decisao_roteamento"])
        self.assertNotIn("executou", relatorio["decisao_roteamento"])

    def test_registra_a_carga_recebida(self) -> None:
        """O conteudo da tarefa era descartado; agora fica registrado para o executor."""

        relatorio = self.rotear({"arquivo": "modulo.py", "prioridade": "alta"})

        self.assertTrue(relatorio["carga_recebida"]["possui_conteudo"])
        self.assertEqual(relatorio["carga_recebida"]["campos"], ["arquivo", "prioridade"])

    def test_carga_vazia_e_declarada_como_vazia(self) -> None:
        """Roteamento sem conteudo precisa dizer isso."""

        relatorio = self.rotear({})

        self.assertFalse(relatorio["carga_recebida"]["possui_conteudo"])
        self.assertEqual(relatorio["carga_recebida"]["campos"], [])

    def test_contador_do_agente_conta_despachos_e_nao_conclusoes(self) -> None:
        """
        O contador se chamava `tarefas_concluidas` e subia a cada roteamento,
        inflando a estatistica com trabalho que nunca foi feito.
        """

        relatorio = self.rotear()

        agente = relatorio["subagente_responsavel"]
        self.assertEqual(agente["tarefas_despachadas"], 1)
        self.assertNotIn("tarefas_concluidas", agente)

    def test_roteamento_e_ciclo_de_vida_continuam_reais(self) -> None:
        """A escolha de setor, o porte do modelo e a hibernacao sao a parte genuina."""

        relatorio = self.rotear()

        self.assertEqual(relatorio["roteamento_modelo"]["tier"], "pesado")
        self.assertEqual(relatorio["estado_final_subagente"], "hibernating")
        self.assertIn("Engenharia", relatorio["departamento"])


if __name__ == "__main__":
    unittest.main()
