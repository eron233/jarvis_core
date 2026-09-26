"""Testes do isolamento de falhas entre os orgaos vitais."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.vital_organs.vital_organs_orchestrator import VitalOrgansOrchestrator


class OrgaoQuebrado:
    """Orgao que sempre falha, para exercitar o isolamento."""

    def run(self, runtime):
        raise RuntimeError("defeito permanente do orgao")


class OrgaoForaDoContrato:
    """Orgao que devolve algo sem o campo obrigatorio de status."""

    def run(self, runtime):
        return "isto nao e um relatorio"


class VitalOrgansIsolationTests(unittest.TestCase):
    """Um orgao com defeito nao pode desligar os outros quatro."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.orchestrator = VitalOrgansOrchestrator(
            project_root=self.tmp,
            report_path=self.tmp / "reports" / "vital_organs.json",
            official_paths={"data": self.tmp / "data", "reports": self.tmp / "reports"},
            official_data_dir=self.tmp / "data",
            official_reports_dir=self.tmp / "reports",
            cycle_interval_seconds=60.0,
            idle_sleep_seconds=1.0,
            background_enabled=False,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_orgao_com_defeito_nao_impede_os_demais(self) -> None:
        """
        Os orgaos rodavam em sequencia direta: o primeiro a levantar excecao
        deixava os quatro seguintes sem executar e a rodada sem relatorio.
        """

        self.orchestrator.structural_integrity_monitor = OrgaoQuebrado()

        relatorio = self.orchestrator.run_cycle(self.runtime)

        organs = relatorio["organs"]
        self.assertFalse(organs["structural_integrity_monitor"]["executado"])
        for nome in ("self_optimization_core", "runtime_hygiene_engine", "failure_prevention_engine", "autonomous_sync_engine"):
            with self.subTest(orgao=nome):
                self.assertNotEqual(organs[nome].get("executado"), False)

    def test_falha_de_orgao_aparece_no_relatorio_com_o_erro(self) -> None:
        """A rodada precisa dizer qual orgao falhou e por que."""

        self.orchestrator.failure_prevention_engine = OrgaoQuebrado()

        organs = self.orchestrator.run_cycle(self.runtime)["organs"]

        falha = organs["failure_prevention_engine"]
        self.assertEqual(falha["erro_tipo"], "RuntimeError")
        self.assertIn("defeito permanente", falha["erro_mensagem"])

    def test_falha_de_orgao_marca_a_rodada_como_critica(self) -> None:
        """Um orgao caido nao pode ser reportado como sistema saudavel."""

        self.orchestrator.runtime_hygiene_engine = OrgaoQuebrado()

        relatorio = self.orchestrator.run_cycle(self.runtime)

        self.assertEqual(relatorio["summary"]["status_geral"], "critico")

    def test_relatorio_fora_do_contrato_e_tratado_como_falha(self) -> None:
        """Um orgao que devolve algo inesperado nao pode quebrar o sumario."""

        self.orchestrator.self_optimization_core = OrgaoForaDoContrato()

        organs = self.orchestrator.run_cycle(self.runtime)["organs"]

        self.assertFalse(organs["self_optimization_core"]["executado"])
        self.assertEqual(organs["self_optimization_core"]["erro_tipo"], "RelatorioInvalido")

    def test_rodada_sem_defeito_continua_normal(self) -> None:
        """O isolamento nao pode alterar o comportamento saudavel."""

        relatorio = self.orchestrator.run_cycle(self.runtime)

        self.assertIn("summary", relatorio)
        self.assertEqual(len(relatorio["organs"]), 5)


if __name__ == "__main__":
    unittest.main()
