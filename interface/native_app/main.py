"""Entrypoint real do aplicativo nativo do JARVIS."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from interface.native_app.api_client import JarvisApiClient
from interface.native_app.async_tools import BackgroundTask
from interface.native_app.config import NativeAppConfig
from interface.native_app.main_window import JarvisMainWindow
from interface.native_app.runtime_bootstrap import JarvisRuntimeBootstrapper, RuntimeBootstrapResult


def build_arg_parser() -> argparse.ArgumentParser:
    """Monta os argumentos do app nativo."""

    parser = argparse.ArgumentParser(description="Aplicativo nativo leve do JARVIS.")
    parser.add_argument("--offscreen", action="store_true", help="Usa backend Qt offscreen para smoke tests.")
    parser.add_argument(
        "--auto-close-ms",
        type=int,
        default=None,
        help="Fecha a janela automaticamente apos o tempo informado.",
    )
    parser.add_argument(
        "--initial-command",
        default=None,
        help="Comando opcional executado automaticamente apos a janela abrir.",
    )
    return parser


def apply_dark_palette(app: QApplication) -> None:
    """Configura uma paleta global escura, com preto real e baixo brilho."""

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#000000"))
    palette.setColor(QPalette.WindowText, QColor("#f5f7fa"))
    palette.setColor(QPalette.Base, QColor("#020406"))
    palette.setColor(QPalette.AlternateBase, QColor("#05080b"))
    palette.setColor(QPalette.Text, QColor("#f5f7fa"))
    palette.setColor(QPalette.Button, QColor("#0a1116"))
    palette.setColor(QPalette.ButtonText, QColor("#f5f7fa"))
    palette.setColor(QPalette.Highlight, QColor("#0f6d86"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


class StartupDialog(QDialog):
    """Tela de bootstrap que garante o runtime antes da janela principal."""

    def __init__(self, bootstrapper: JarvisRuntimeBootstrapper, parent=None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent)
        self.bootstrapper = bootstrapper
        self.thread_pool = QThreadPool.globalInstance()
        self.result_payload: RuntimeBootstrapResult | None = None
        self._build_ui()
        self._start_bootstrap()

    def _build_ui(self) -> None:
        """Monta ui para o fluxo atual."""
        self.setWindowTitle("JARVIS")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.resize(520, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Abrindo o JARVIS")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f7fa;")
        subtitle = QLabel(
            "O app nativo verifica o runtime local, sobe o servidor se necessario e so libera a janela principal depois do healthcheck positivo."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #aebdca; line-height: 1.4;")

        self.status_label = QLabel("Inicializando bootstrap local...")
        self.status_label.setStyleSheet("color: #f5f7fa; font-weight: 600;")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { background: #05080b; border: 1px solid #152028; border-radius: 10px; }"
            "QProgressBar::chunk { background: #0f6d86; border-radius: 10px; }"
        )

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QPlainTextEdit { background: #010203; border: 1px solid #141c22; color: #dbe6ef; border-radius: 12px; }"
        )

        self.retry_button = QPushButton("Tentar novamente")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._start_bootstrap)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_view, 1)
        layout.addWidget(self.retry_button)

        self.setStyleSheet(
            "QDialog { background: #000000; color: #f5f7fa; } "
            "QPushButton { background: #0a1116; border: 1px solid #1a2730; border-radius: 12px; padding: 10px 12px; color: #ffffff; }"
        )

    def _start_bootstrap(self) -> None:
        """Executa a rotina interna de start bootstrap."""
        self.retry_button.setVisible(False)
        self.progress.setRange(0, 0)
        self.log_view.clear()
        self._append_log("Bootstrap iniciado.")

        task = BackgroundTask("native_bootstrap", self._run_bootstrap)
        task.signals.result.connect(self._on_success)
        task.signals.error.connect(self._on_error)
        self.thread_pool.start(task)

    def _run_bootstrap(self) -> RuntimeBootstrapResult:
        """Executa bootstrap no contexto atual."""
        messages: list[str] = []

        def _collect(message: str) -> None:
            """Executa a coleta de bootstrap em background."""
            messages.append(message)

        result = self.bootstrapper.ensure_runtime_available(progress_callback=_collect)
        result.health_payload["_native_bootstrap_messages"] = list(messages)
        return result

    def _on_success(self, result: RuntimeBootstrapResult) -> None:
        """Executa a rotina interna de on success."""
        self.result_payload = result
        for message in result.health_payload.get("_native_bootstrap_messages", []):
            self._append_log(message)
        self._append_log("Bootstrap concluido com sucesso.")
        self.status_label.setText("Runtime pronto. Abrindo a janela principal...")
        self.accept()

    def _on_error(self, _job_name: str, traceback_text: str) -> None:
        """Executa a rotina interna de on error."""
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_label.setText("Falha ao preparar o runtime.")
        self._append_log(traceback_text.strip())
        self.retry_button.setVisible(True)

    def _append_log(self, message: str) -> None:
        """Acrescenta log ao registro correspondente."""
        self.log_view.appendPlainText(str(message))


def main(argv: list[str] | None = None) -> int:
    """Executa o bootstrap e abre a janela principal do app nativo."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([sys.argv[0], *(argv or [])])
    app.setApplicationName("Jarvis")
    app.setQuitOnLastWindowClosed(True)
    apply_dark_palette(app)

    config = NativeAppConfig.from_env()
    api_client = JarvisApiClient(config)
    bootstrapper = JarvisRuntimeBootstrapper(config=config, api_client=api_client)

    startup_dialog = StartupDialog(bootstrapper=bootstrapper)
    if startup_dialog.exec() != QDialog.Accepted or startup_dialog.result_payload is None:
        return 1

    window = JarvisMainWindow(
        config=config,
        api_client=api_client,
        bootstrap_result=startup_dialog.result_payload,
        auto_close_ms=args.auto_close_ms,
        initial_command=args.initial_command,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
