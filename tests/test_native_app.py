"""Testes do aplicativo nativo leve do JARVIS."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.native_app.config import NativeAppConfig
from interface.native_app.api_client import ApiClientError
from interface.native_app.runtime_bootstrap import JarvisRuntimeBootstrapper, RuntimeBootstrapResult

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from interface.native_app.main_window import JarvisMainWindow

    PYSIDE6_AVAILABLE = True
except ImportError:  # pragma: no cover - protegido para ambientes sem Qt
    QApplication = None
    QLabel = None
    JarvisMainWindow = None
    PYSIDE6_AVAILABLE = False


class _FakeProcess:
    """Processo minimo para simular o runtime em bootstrap."""

    def __init__(self, pid: int = 4321, return_code: int | None = None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        self.pid = pid
        self._return_code = return_code

    def poll(self) -> int | None:
        """Consulta o resultado assincrono ate a conclusao do cenario."""
        return self._return_code


def build_native_app_config() -> NativeAppConfig:
    """Monta configuracao consistente para os testes do app nativo."""

    return NativeAppConfig(
        api_base_url="http://127.0.0.1:8000",
        api_token="token-nativo-teste-seguro",
        device_id="device-nativo-teste-principal",
        python_executable=Path(sys.executable),
        project_root=PROJECT_ROOT,
        runtime_entrypoint=PROJECT_ROOT / "runtime" / "server.py",
        startup_timeout_seconds=3.0,
        startup_poll_interval_seconds=0.01,
        request_timeout_seconds=3.0,
        status_refresh_interval_ms=5000,
        brain_refresh_interval_ms=7000,
    )


class NativeAppBootstrapTests(unittest.TestCase):
    """Valida o bootstrap automatico do runtime para o app nativo."""

    def test_bootstrap_reaproveita_runtime_quando_healthcheck_ja_responde(self) -> None:
        """Valida o cenario de bootstrap reaproveita runtime quando healthcheck ja responde."""
        client = MagicMock()
        client.public_healthcheck.return_value = {"mensagem": "API do JARVIS ativa.", "status": "ok"}
        bootstrapper = JarvisRuntimeBootstrapper(config=build_native_app_config(), api_client=client)

        with patch.object(bootstrapper, "start_runtime_process") as start_mock:
            result = bootstrapper.ensure_runtime_available()

        self.assertFalse(result.started_runtime)
        self.assertIsNone(result.runtime_pid)
        self.assertEqual(result.health_payload["status"], "ok")
        start_mock.assert_not_called()

    def test_bootstrap_sobe_runtime_quando_healthcheck_inicial_falha(self) -> None:
        """Valida o cenario de bootstrap sobe runtime quando healthcheck inicial falha."""
        bootstrapper = JarvisRuntimeBootstrapper(
            config=build_native_app_config(),
            api_client=MagicMock(),
        )
        fake_process = _FakeProcess(pid=15900)

        with patch.object(
            bootstrapper,
            "probe_health",
            side_effect=[None, None, {"mensagem": "API do JARVIS ativa.", "status": "ok"}],
        ), patch.object(
            bootstrapper,
            "start_runtime_process",
            return_value=fake_process,
        ) as start_mock, patch("interface.native_app.runtime_bootstrap.time.sleep", return_value=None):
            result = bootstrapper.ensure_runtime_available()

        self.assertTrue(result.started_runtime)
        self.assertEqual(result.runtime_pid, 15900)
        self.assertEqual(result.health_payload["status"], "ok")
        start_mock.assert_called_once()


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 nao instalado.")
class NativeAppWindowSmokeTests(unittest.TestCase):
    """Smoke tests da janela nativa sem depender de navegador."""

    @classmethod
    def setUpClass(cls) -> None:
        """Executa a rotina interna de setUpClass."""
        cls.qt_app = QApplication.instance() or QApplication([])

    def build_bundle(self) -> dict:
        """Executa a rotina interna de build bundle."""
        return {
            "health": {
                "status": "ok",
                "status_ptbr": "saudavel",
                "ultima_persistencia_fila": "2026-03-15T17:00:00+00:00",
            },
            "status": {
                "mensagem": "Estado atual do sistema recuperado com sucesso.",
                "dados": {
                    "status": "initialized",
                    "status_ptbr": "inicializado",
                    "queue_depth": 0,
                },
            },
            "runtime_identity": {
                "dados": {
                    "entrypoint": "runtime.server.run_server",
                    "process_id": 15900,
                }
            },
            "system_report": {
                "status_runtime": {
                    "status": "initialized",
                    "status_ptbr": "inicializado",
                    "total_cycles_executed": 42,
                },
                "total_ciclos_executados": 42,
                "quantidade_tarefas_pendentes": 0,
                "quantidade_objetivos_ativos": 1,
                "ultimo_ciclo_executado": {"status_ptbr": "ociosa"},
                "seguranca_operacional": {
                    "risco_geral": "nao_auditado",
                    "fraquezas_detectadas": 0,
                    "acoes_automaticas_realizadas": 0,
                },
                "politica_ativa": {"identidade": {"nome_sistema": "Sistema Cognitivo JARVIS"}},
                "ambiente": {
                    "autenticacao_configurada": {
                        "token_configurado": False,
                        "dispositivo_confiavel_configurado": False,
                    }
                },
            },
            "goals_report": {"resumo": {"total_objetivos_ativos": 1, "total_metas_estrategicas": 1, "progresso_medio": 50}},
            "queue_report": {"resumo": {"tarefas_pendentes": 0, "tarefas_bloqueadas": 0, "tarefas_concluidas_total": 2}},
            "memory_report": {"resumo": {"total_entradas_semanticas": 5, "total_procedimentos": 1, "ultima_escrita": "2026-03-15T17:00:00+00:00"}},
            "audit_report": {"persistencia": {"total_eventos": 12}, "ultimas_falhas": [], "ultimas_tentativas_negadas": []},
        }

    def build_brain_bundle(self) -> dict:
        """Executa a rotina interna de build brain bundle."""
        return {
            "level": "semanal",
            "evolution": {
                "nivel": "semanal",
                "nivel_ptbr": "Nivel 2 - evolucao semanal",
                "regioes": [
                    {
                        "region_id": "cerebro_estrutural",
                        "label": "Cerebro Estrutural",
                        "x": 0.18,
                        "y": 0.52,
                        "glow_intensity": 1.0,
                        "render_weight": 1.0,
                    },
                    {
                        "region_id": "plasticidade_sinaptica",
                        "label": "Plasticidade Sinaptica",
                        "x": 0.66,
                        "y": 0.30,
                        "glow_intensity": 0.35,
                        "render_weight": 0.55,
                    },
                ],
                "trilhas_aprendizado": [
                    {
                        "source": "cerebro_estrutural",
                        "target": "plasticidade_sinaptica",
                        "intensidade": 20.0,
                        "espessura": 3.0,
                        "cor": "#d4af37",
                    }
                ],
                "resumo": {
                    "total_eventos": 12,
                    "conexoes_criadas": 18,
                    "conexoes_reforcadas": 7,
                    "impacto_cognitivo_total": 8.4,
                    "regiao_mais_ativa": {"label": "Cerebro Estrutural"},
                },
            },
            "analysis": {
                "regioes_mais_utilizadas": [{"region_id": "cerebro_estrutural", "label": "Cerebro Estrutural"}],
                "regioes_subutilizadas": [{"region_id": "plasticidade_sinaptica", "label": "Plasticidade Sinaptica"}],
                "conexoes_mais_fortes": [
                    {
                        "source_label": "Cerebro Estrutural",
                        "target_label": "Plasticidade Sinaptica",
                    }
                ],
                "estado_runtime": {"total_ciclos_executados": 42},
            },
        }

    def test_janela_nativa_renderiza_chat_sidebar_e_cerebro_sem_navegador(self) -> None:
        """Valida o cenario de janela nativa renderiza chat sidebar e cerebro sem navegador."""
        config = build_native_app_config()
        client = MagicMock()
        bootstrap_result = RuntimeBootstrapResult(
            health_payload={"mensagem": "API do JARVIS ativa.", "status": "ok"},
            started_runtime=True,
            runtime_pid=15900,
            startup_duration_seconds=1.2,
        )

        with patch.object(JarvisMainWindow, "_schedule_refresh", lambda self: None):
            window = JarvisMainWindow(config=config, api_client=client, bootstrap_result=bootstrap_result)

        window._on_bundle_ready(self.build_bundle())
        window._on_brain_bundle_ready(self.build_brain_bundle())
        window._on_command_ready({"acao": "system_report", "resposta": "Runtime em inicializado."})

        self.assertIn("Runtime", window.runtime_chip.text())
        self.assertIn("Foco atual", window.brain_summary_view.toPlainText())
        self.assertIn("Runtime em inicializado.", window.chat_timeline.container.findChildren(QLabel)[-1].text())
        window.close()

    def test_erro_de_comando_nao_deixa_chat_presente_em_processando(self) -> None:
        """Valida o cenario de erro de comando nao deixa chat presente em processando."""
        config = build_native_app_config()
        client = MagicMock()
        client.send_command.side_effect = ApiClientError("Falha HTTP 500: Internal Server Error")
        bootstrap_result = RuntimeBootstrapResult(
            health_payload={"mensagem": "API do JARVIS ativa.", "status": "ok"},
            started_runtime=False,
            runtime_pid=None,
            startup_duration_seconds=0.8,
        )

        with patch.object(JarvisMainWindow, "_schedule_refresh", lambda self: None):
            window = JarvisMainWindow(config=config, api_client=client, bootstrap_result=bootstrap_result)

        window.command_input.setText("status do sistema")
        window.send_command()

        for _ in range(100):
            self.qt_app.processEvents()
            if "send_command" not in window._active_jobs:
                break

        self.assertNotIn("send_command", window._active_jobs)
        self.assertTrue(window.send_button.isEnabled())
        self.assertIn("Nao consegui", window.footer_command.text())
        window.close()


if __name__ == "__main__":
    unittest.main()
