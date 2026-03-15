"""Janela principal do aplicativo nativo leve do JARVIS."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import json
import traceback
from typing import Any, Callable

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from interface.native_app.api_client import JarvisApiClient
from interface.native_app.async_tools import BackgroundTask
from interface.native_app.brain_widget import (
    NativeBrainWidget,
    format_brain_analysis,
    format_brain_summary,
)
from interface.native_app.config import NativeAppConfig
from interface.native_app.runtime_bootstrap import RuntimeBootstrapResult


SECTION_ORDER = [
    ("chat", "Chat"),
    ("status", "Status"),
    ("objetivos", "Objetivos"),
    ("tarefas", "Tarefas"),
    ("memoria", "Memoria"),
    ("logs", "Logs"),
    ("seguranca", "Seguranca"),
    ("sistema", "Sistema"),
]


def pretty_json(payload: Any) -> str:
    """Formata payloads em JSON legivel no app."""

    return json.dumps(payload, indent=2, ensure_ascii=False)


def safe_label(value: Any, fallback: str = "indisponivel") -> str:
    """Normaliza campos opcionais para exibicao curta."""

    if value in (None, "", [], {}):
        return fallback
    return str(value)


def friendly_timestamp(value: str | None) -> str:
    """Compacta timestamps ISO para leitura no rodape."""

    if not value:
        return "nao informado"
    return value.replace("T", " ").replace("+00:00", " UTC")


class SidebarButton(QPushButton):
    """Botao discreto da barra lateral do app."""

    def __init__(self, text: str, section_key: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.section_key = section_key
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(40)


class DetailPage(QWidget):
    """Pagina de detalhe simples, real e ligada a payloads da API."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.title_label = QLabel("Carregando")
        self.title_label.setObjectName("DetailTitle")
        self.summary_label = QLabel("Sem dados.")
        self.summary_label.setObjectName("DetailSummary")
        self.summary_label.setWordWrap(True)

        self.payload_view = QPlainTextEdit()
        self.payload_view.setReadOnly(True)
        self.payload_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.payload_view.setObjectName("PayloadView")
        self.payload_view.setFont(QFont("Consolas", 10))

        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.payload_view, 1)

    def set_content(self, title: str, summary_lines: list[str], payload: Any) -> None:
        """Atualiza o texto curto e o JSON bruto da secao."""

        self.title_label.setText(title)
        self.summary_label.setText("\n".join(summary_lines) if summary_lines else "Sem dados.")
        self.payload_view.setPlainText(pretty_json(payload))


class ChatMessageBubble(QFrame):
    """Bolha simples do chat nativo."""

    def __init__(self, role: str, text: str, meta: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        wrapper = QHBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)

        bubble_shell = QFrame()
        bubble_shell.setObjectName(f"BubbleShell-{role}")
        bubble_shell.setMaximumWidth(540)
        bubble_layout = QVBoxLayout(bubble_shell)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(6)

        header = QLabel(meta or role.upper())
        header.setObjectName("BubbleMeta")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setObjectName("BubbleBody")

        bubble_layout.addWidget(header)
        bubble_layout.addWidget(body)

        if role == "user":
            wrapper.addStretch(1)
            wrapper.addWidget(bubble_shell, 0, Qt.AlignRight)
        else:
            wrapper.addWidget(bubble_shell, 0, Qt.AlignLeft)
            wrapper.addStretch(1)


class ChatTimeline(QScrollArea):
    """Timeline vertical do chat principal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("ChatTimeline")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(12)
        self.container_layout.addStretch(1)
        self.setWidget(self.container)

    def add_message(self, role: str, text: str, meta: str = "") -> None:
        """Adiciona uma nova bolha ao fluxo do chat."""

        bubble = ChatMessageBubble(role=role, text=text, meta=meta)
        self.container_layout.insertWidget(self.container_layout.count() - 1, bubble)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        """Mantem o fluxo visual no fim da conversa."""

        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class JarvisMainWindow(QMainWindow):
    """Janela principal do aplicativo nativo leve."""

    def __init__(
        self,
        config: NativeAppConfig,
        api_client: JarvisApiClient,
        bootstrap_result: RuntimeBootstrapResult,
        *,
        auto_close_ms: int | None = None,
        initial_command: str | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.api_client = api_client
        self.bootstrap_result = bootstrap_result
        self.auto_close_ms = auto_close_ms
        self.initial_command = initial_command
        self.thread_pool = QThreadPool.globalInstance()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._active_jobs: set[str] = set()
        self._running_tasks: dict[str, BackgroundTask] = {}
        self._running_futures: dict[str, Future[Any]] = {}
        self._latest_bundle: dict[str, Any] = {}
        self._latest_brain_bundle: dict[str, Any] = {}
        self._last_command_payload: dict[str, Any] = {}
        self._current_section = "chat"
        self._authenticated_local_session = False

        self.setWindowTitle("JARVIS")
        self.resize(1540, 940)
        self.setMinimumSize(1280, 760)
        self._build_ui()
        self._apply_styles()
        self._connect_signals()
        self._apply_bootstrap_state()
        self._schedule_refresh()

        if self.initial_command:
            QTimer.singleShot(900, self._send_initial_command)

        if self.auto_close_ms is not None:
            QTimer.singleShot(self.auto_close_ms, self.close)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_brain_panel())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([190, 820, 420])

        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        self.footer_runtime = QLabel("Runtime aguardando.")
        self.footer_refresh = QLabel("Sem refresh.")
        self.footer_command = QLabel("Chat pronto.")
        status_bar.addPermanentWidget(self.footer_runtime)
        status_bar.addPermanentWidget(self.footer_refresh)
        status_bar.addPermanentWidget(self.footer_command, 1)
        self.setStatusBar(status_bar)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(210)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(14)

        brand = QLabel("JARVIS")
        brand.setObjectName("BrandTitle")
        subtitle = QLabel("")
        subtitle.setObjectName("BrandSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(brand)
        subtitle.hide()

        self.runtime_chip = QLabel("Runtime")
        self.health_chip = QLabel("Saude")
        self.device_chip = QLabel("Dispositivo")
        for chip in (self.runtime_chip, self.health_chip, self.device_chip):
            chip.setObjectName("SidebarChip")
            chip.setWordWrap(True)
            layout.addWidget(chip)

        self.sidebar_group = QButtonGroup(self)
        self.sidebar_group.setExclusive(True)
        self.sidebar_buttons: dict[str, SidebarButton] = {}
        for section_key, label in SECTION_ORDER:
            button = SidebarButton(label, section_key)
            self.sidebar_group.addButton(button)
            self.sidebar_buttons[section_key] = button
            layout.addWidget(button)

        layout.addStretch(1)

        self.sidebar_refresh_button = QPushButton("Atualizar agora")
        self.sidebar_refresh_button.setObjectName("GhostButton")
        self.sidebar_refresh_button.hide()
        layout.addWidget(self.sidebar_refresh_button)

        self.sidebar_buttons["chat"].setChecked(True)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("CenterPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(8)
        hero_title = QLabel("Conversa central")
        hero_title.setObjectName("SectionTitle")
        hero_text = QLabel(
            "Converse com o Jarvis por aqui."
        )
        hero_text.setWordWrap(True)
        hero_text.setObjectName("SectionBody")
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_text)
        layout.addWidget(hero)

        self.chat_timeline = ChatTimeline()
        layout.addWidget(self.chat_timeline, 1)

        command_frame = QFrame()
        command_frame.setObjectName("ComposerFrame")
        command_layout = QVBoxLayout(command_frame)
        command_layout.setContentsMargins(16, 14, 16, 14)
        command_layout.setSpacing(12)

        command_row = QHBoxLayout()
        command_row.setSpacing(10)
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Digite um comando para o Jarvis")
        self.send_button = QPushButton("Enviar")
        self.send_button.setObjectName("PrimaryButton")
        command_row.addWidget(self.command_input, 1)
        command_row.addWidget(self.send_button)

        advanced_row = QHBoxLayout()
        advanced_row.setSpacing(10)
        self.voice_input = QLineEdit()
        self.voice_input.setPlaceholderText("Voz (opcional)")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Chave admin (opcional)")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.response_mode = QComboBox()
        self.response_mode.addItems(["conversacional", "tecnico"])
        self.voice_input.hide()
        self.response_mode.hide()
        advanced_row.addWidget(self.voice_input, 1)
        advanced_row.addWidget(self.password_input, 1)
        advanced_row.addWidget(self.response_mode, 0)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        for label, command in (
            ("Status", "status do sistema"),
            ("Objetivos", "mostrar objetivos"),
            ("Tarefas", "mostrar fila"),
            ("Memoria", "mostrar memoria"),
            ("Jarvis ta ai", "Jarvis ta ai"),
        ):
            button = QPushButton(label)
            button.setObjectName("GhostButton")
            button.clicked.connect(lambda _checked=False, value=command: self._fill_quick_command(value))
            quick_row.addWidget(button)

        command_layout.addLayout(command_row)
        command_layout.addLayout(advanced_row)
        command_layout.addLayout(quick_row)
        layout.addWidget(command_frame)

        self.detail_pages: dict[str, DetailPage] = {}
        self.detail_stack = QFrame()
        self.detail_stack.setObjectName("DetailContainer")
        detail_layout = QVBoxLayout(self.detail_stack)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        detail_layout.setSpacing(0)
        for section_key, _label in SECTION_ORDER:
            page = DetailPage()
            page.hide()
            self.detail_pages[section_key] = page
            detail_layout.addWidget(page)
        layout.addWidget(self.detail_stack, 1)

        return panel

    def _build_brain_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("BrainPanel")
        panel.setMinimumWidth(360)
        panel.setMaximumWidth(460)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Cerebro")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Estado cognitivo do runtime.")
        subtitle.setObjectName("SectionBody")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        brain_toolbar = QHBoxLayout()
        brain_toolbar.setSpacing(8)
        self.brain_level = QComboBox()
        self.brain_level.addItems(["recente", "semanal", "mensal", "historica"])
        self.brain_level.setCurrentText("semanal")
        self.refresh_brain_button = QPushButton("Atualizar cerebro")
        self.refresh_brain_button.setObjectName("GhostButton")
        brain_toolbar.addWidget(self.brain_level, 1)
        brain_toolbar.addWidget(self.refresh_brain_button)
        layout.addLayout(brain_toolbar)

        self.brain_widget = NativeBrainWidget()
        layout.addWidget(self.brain_widget, 1)

        self.brain_runtime_label = QLabel("Runtime conectando")
        self.brain_runtime_label.setObjectName("SidebarChip")
        self.brain_cycle_label = QLabel("Ciclos --")
        self.brain_cycle_label.setObjectName("SidebarChip")
        self.brain_auth_label = QLabel("Acesso aguardando")
        self.brain_auth_label.setObjectName("SidebarChip")
        layout.addWidget(self.brain_runtime_label)
        layout.addWidget(self.brain_cycle_label)
        layout.addWidget(self.brain_auth_label)

        self.brain_summary_view = QPlainTextEdit()
        self.brain_summary_view.setReadOnly(True)
        self.brain_summary_view.setObjectName("PayloadView")
        self.brain_summary_view.setMaximumBlockCount(200)
        self.brain_summary_view.setFont(QFont("Consolas", 10))
        layout.addWidget(self.brain_summary_view, 0)

        self.brain_analysis_view = QPlainTextEdit()
        self.brain_analysis_view.setReadOnly(True)
        self.brain_analysis_view.setObjectName("PayloadView")
        self.brain_analysis_view.setMaximumBlockCount(200)
        self.brain_analysis_view.setFont(QFont("Consolas", 10))
        layout.addWidget(self.brain_analysis_view, 0)

        return panel

    def _connect_signals(self) -> None:
        self.sidebar_group.buttonClicked.connect(self._handle_sidebar_click)
        self.sidebar_refresh_button.clicked.connect(self.refresh_everything)
        self.refresh_brain_button.clicked.connect(self.refresh_brain_bundle)
        self.brain_level.currentTextChanged.connect(lambda _value: self.refresh_brain_bundle(force=True))
        self.send_button.clicked.connect(self.send_command)
        self.command_input.returnPressed.connect(self.send_command)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #000000; color: #f5f7fa; font-family: "Bahnschrift"; }
            QStatusBar { background: #050505; border-top: 1px solid #11171c; }
            #Sidebar { background: #030303; border-right: 1px solid #11171c; }
            #CenterPanel { background: #010101; }
            #BrainPanel { background: #030506; border-left: 1px solid #11171c; }
            #HeroCard, #ComposerFrame, #DetailContainer {
                background: #07090c; border: 1px solid #11171c; border-radius: 18px;
            }
            #BrandTitle { font-size: 28px; font-weight: 700; letter-spacing: 2px; }
            #BrandSubtitle { color: #9ca8b5; font-size: 12px; line-height: 1.35; }
            #SidebarChip {
                background: #070d12; border: 1px solid #16222b; border-radius: 12px;
                padding: 8px 10px; color: #d8e3eb;
            }
            QPushButton {
                background: #0a1116; border: 1px solid #19262f; border-radius: 12px;
                padding: 10px 12px; color: #f4f7fb;
            }
            QPushButton:hover { border-color: #2b4f62; }
            QPushButton:checked { background: #071a22; border-color: #2bb2d3; color: #ffffff; }
            #PrimaryButton { background: #0f6d86; border-color: #1c9bc1; font-weight: 700; }
            #PrimaryButton:hover { background: #1383a0; }
            #GhostButton { background: #07090c; border-color: #172028; }
            QLineEdit, QComboBox, QPlainTextEdit {
                background: #020406; border: 1px solid #182027; border-radius: 12px;
                padding: 10px 12px; color: #f5f7fa; selection-background-color: #2bb2d3;
            }
            QComboBox QAbstractItemView {
                background: #05080b; border: 1px solid #172028;
                selection-background-color: #0f6d86; color: #f5f7fa;
            }
            #SectionTitle { font-size: 20px; font-weight: 700; }
            #SectionBody { color: #a6b2be; line-height: 1.4; }
            #DetailTitle { font-size: 18px; font-weight: 700; }
            #DetailSummary { color: #bfd1dd; line-height: 1.45; }
            #PayloadView { background: #010203; border-radius: 14px; border: 1px solid #141c22; }
            #ChatTimeline { background: #000000; border: none; }
            #BubbleShell-user { background: #0f6d86; border: 1px solid #22a7ca; border-radius: 16px; }
            #BubbleShell-assistant { background: #0a0f14; border: 1px solid #19242d; border-radius: 16px; }
            #BubbleShell-system { background: #120f05; border: 1px solid #5b4914; border-radius: 16px; }
            #BubbleMeta { color: #d6dde5; font-size: 11px; letter-spacing: 1px; }
            #BubbleBody { color: #ffffff; font-size: 14px; line-height: 1.45; }
            """
        )

    def _apply_bootstrap_state(self) -> None:
        self.chat_timeline.add_message(
            "assistant",
            "JARVIS pronto para conversar.",
            "Jarvis",
        )
        self.footer_runtime.setText(f"Conectado em {self.bootstrap_result.startup_duration_seconds:.1f}s")
        self.footer_command.setText("Pronto.")
        self._set_section("chat")

    def _schedule_refresh(self) -> None:
        self.refresh_everything()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_bundle)
        self.status_timer.start(self.config.status_refresh_interval_ms)

        self.brain_timer = QTimer(self)
        self.brain_timer.timeout.connect(self.refresh_brain_bundle)
        self.brain_timer.start(self.config.brain_refresh_interval_ms)

    def _fill_quick_command(self, text: str) -> None:
        self.command_input.setText(text)
        self.command_input.setFocus(Qt.ShortcutFocusReason)

    def _send_initial_command(self) -> None:
        """Executa um comando automatico usado em smoke tests opcionais."""

        if not self.initial_command:
            return
        self.command_input.setText(self.initial_command)
        self.send_command()

    def _set_command_busy(self, is_busy: bool) -> None:
        """Bloqueia o compositor enquanto um comando esta em andamento."""

        self.send_button.setEnabled(not is_busy)
        self.command_input.setEnabled(not is_busy)
        if not is_busy:
            self.command_input.setFocus(Qt.ShortcutFocusReason)

    def _handle_sidebar_click(self, button) -> None:
        self._set_section(getattr(button, "section_key", "chat"))

    def _set_section(self, section: str) -> None:
        self._current_section = section
        for section_key, page in self.detail_pages.items():
            page.setVisible(section_key == section)
        self._render_current_section()

    def refresh_everything(self) -> None:
        self.refresh_bundle()
        self.refresh_brain_bundle()

    def refresh_bundle(self) -> None:
        self._run_background("dashboard_bundle", self.api_client.fetch_dashboard_bundle, self._on_bundle_ready)

    def refresh_brain_bundle(self, force: bool = False) -> None:
        level = self.brain_level.currentText()
        job_name = f"brain_bundle:{level}"
        if not force and job_name in self._active_jobs:
            return
        self._run_background(
            job_name,
            lambda: self.api_client.fetch_brain_bundle(level=level),
            self._on_brain_bundle_ready,
        )

    def send_command(self) -> None:
        command_text = self.command_input.text().strip()
        if not command_text:
            self.footer_command.setText("Digite um comando antes de enviar.")
            return

        self.chat_timeline.add_message("user", command_text, "Voce")
        voice_id = self.voice_input.text().strip() or None
        password = self.password_input.text().strip() or None
        response_mode = self.response_mode.currentText()
        self.command_input.clear()
        self._set_command_busy(True)
        self.footer_command.setText("Processando...")

        self._run_background(
            "send_command",
            lambda: self.api_client.send_command(
                command_text,
                voice_id=voice_id,
                password=password,
                response_mode=response_mode,
            ),
            self._on_command_ready,
            on_finished=lambda: self._set_command_busy(False),
        )

    def _on_bundle_ready(self, bundle: dict[str, Any]) -> None:
        self._authenticated_local_session = True
        self._latest_bundle = bundle
        self._render_current_section()
        self._render_runtime_summary()
        self.footer_refresh.setText(f"Ultimo refresh {datetime.now().strftime('%H:%M:%S')}")

    def _on_brain_bundle_ready(self, bundle: dict[str, Any]) -> None:
        self._latest_brain_bundle = bundle
        evolution = bundle.get("evolution", {})
        analysis = bundle.get("analysis", {})
        self.brain_widget.set_payload(evolution, analysis)
        self.brain_summary_view.setPlainText(format_brain_summary(evolution))
        self.brain_analysis_view.setPlainText(format_brain_analysis(analysis))

    def _on_command_ready(self, payload: dict[str, Any]) -> None:
        self._authenticated_local_session = True
        self._last_command_payload = payload
        self.chat_timeline.add_message(
            "assistant",
            self._format_command_response(payload),
            "Jarvis",
        )
        self.footer_command.setText("Resposta recebida.")
        self._render_current_section()
        self.refresh_everything()

    def _extract_error_message(self, traceback_text: str) -> str:
        """Converte o traceback bruto em uma mensagem curta para a UI."""

        last_line = traceback_text.strip().splitlines()[-1] if traceback_text.strip() else "Erro desconhecido."
        if ":" in last_line:
            return last_line.split(":", 1)[-1].strip()
        return last_line.strip()

    @staticmethod
    def _looks_like_auth_error(message: str) -> bool:
        normalized = message.lower()
        return "401" in normalized or "403" in normalized or "token" in normalized or "dispositivo" in normalized

    def _format_command_response(self, payload: dict[str, Any]) -> str:
        """Transforma o payload do runtime em resposta amigavel ao usuario."""

        if payload.get("acao") == "special_phrase" and payload.get("status") == "ignored":
            return "Presenca detectada. Para a resposta reservada, informe a chave admin."
        return payload.get("resposta") or payload.get("mensagem") or "Resposta vazia."

    def _friendly_command_error(self, message: str) -> str:
        """Padroniza erros do chat sem despejar texto tecnico bruto."""

        if self._looks_like_auth_error(message):
            return "Nao consegui autenticar o app com a API local."
        if "conectar" in message.lower() or "tempo" in message.lower():
            return "Nao consegui falar com o runtime agora. Tente novamente."
        return "Nao consegui processar esse comando agora."

    def _on_background_error(self, job_name: str, traceback_text: str) -> None:
        message = self._extract_error_message(traceback_text)
        if self._looks_like_auth_error(message):
            self._authenticated_local_session = False

        if job_name == "send_command":
            friendly_message = self._friendly_command_error(message)
            self.chat_timeline.add_message("assistant", friendly_message, "Jarvis")
            self.footer_command.setText(friendly_message)
            return

        self.footer_refresh.setText("Atualizacao temporariamente indisponivel.")
        self.footer_runtime.setText("Conexao instavel com o runtime.")
        self._render_runtime_summary()

    def _render_runtime_summary(self) -> None:
        if not self._latest_bundle:
            return

        status = self._latest_bundle.get("status", {}).get("dados", {})
        system_report = self._latest_bundle.get("system_report", {})
        runtime_state = system_report.get("status_runtime", {})
        runtime_health = system_report.get("saude_runtime", {})
        runtime_identity = self._latest_bundle.get("runtime_identity", {}).get("dados", {})
        api_port = runtime_identity.get("environment", {}).get("porta_api")

        self.runtime_chip.setText(f"Runtime: {safe_label(runtime_state.get('status_ptbr'))}")
        self.health_chip.setText(f"Acesso: {'autorizado' if self._authenticated_local_session else 'indisponivel'}")
        self.device_chip.setText(f"Ciclos: {safe_label(system_report.get('total_ciclos_executados', 0), '0')}")

        self.brain_runtime_label.setText(
            f"Runtime {safe_label(runtime_health.get('status_ptbr', status.get('status_ptbr')))}"
        )
        self.brain_cycle_label.setText(
            f"Ciclos {safe_label(runtime_state.get('total_cycles_executed', system_report.get('total_ciclos_executados', 0)), '0')}"
        )
        self.brain_auth_label.setText(
            "Acesso "
            f"{'autorizado' if self._authenticated_local_session else 'indisponivel'}"
        )
        self.footer_runtime.setText(
            f"Runtime {safe_label(runtime_state.get('status_ptbr'))} | API {safe_label(api_port, 'local')}"
        )

    def _render_current_section(self) -> None:
        page = self.detail_pages.get(self._current_section)
        if page is None:
            return
        title, summary_lines, payload = self._build_section_content(self._current_section)
        page.set_content(title=title, summary_lines=summary_lines, payload=payload)

    def _build_section_content(self, section: str) -> tuple[str, list[str], Any]:
        bundle = self._latest_bundle
        system_report = bundle.get("system_report", {})
        runtime_state = system_report.get("status_runtime", {})

        if section == "chat":
            payload = self._last_command_payload or {
                "mensagem": "Use o chat central para falar com o runtime real do Jarvis.",
                "sugestoes": [
                    "status do sistema",
                    "mostrar objetivos",
                    "mostrar fila",
                    "mostrar memoria",
                    "Jarvis ta ai",
                ],
                "observacao": "Use a chave admin quando quiser liberar comandos restritos.",
            }
            summary = [
                f"Runtime atual: {safe_label(runtime_state.get('status_ptbr'))}",
                f"Fila pendente: {safe_label(system_report.get('quantidade_tarefas_pendentes', 0), '0')}",
                f"Ultimo comando: {safe_label(self._last_command_payload.get('acao'), 'nenhum')}",
            ]
            return "Chat", summary, payload

        if section == "status":
            health = bundle.get("health", {})
            status = bundle.get("status", {})
            identity = bundle.get("runtime_identity", {})
            summary = [
                f"Healthcheck autenticado: {safe_label(health.get('status_ptbr'))}",
                f"Runtime: {safe_label(status.get('dados', {}).get('status_ptbr'))}",
                f"Ultima persistencia da fila: {safe_label(health.get('ultima_persistencia_fila'))}",
                f"Entrypoint ativo: {safe_label(identity.get('dados', {}).get('entrypoint'))}",
            ]
            payload = {"health": health, "status": status, "runtime_identity": identity}
            return "Status", summary, payload

        if section == "objetivos":
            goals_report = bundle.get("goals_report", {})
            resumo = goals_report.get("resumo", {})
            return (
                "Objetivos",
                [
                    f"Objetivos ativos: {safe_label(resumo.get('total_objetivos_ativos', 0), '0')}",
                    f"Metas estrategicas: {safe_label(resumo.get('total_metas_estrategicas', 0), '0')}",
                    f"Progresso medio: {safe_label(resumo.get('progresso_medio', 0), '0')}%",
                ],
                goals_report,
            )

        if section == "tarefas":
            queue_report = bundle.get("queue_report", {})
            resumo = queue_report.get("resumo", {})
            return (
                "Tarefas",
                [
                    f"Pendentes: {safe_label(resumo.get('tarefas_pendentes', 0), '0')}",
                    f"Bloqueadas: {safe_label(resumo.get('tarefas_bloqueadas', 0), '0')}",
                    f"Concluidas: {safe_label(resumo.get('tarefas_concluidas_total', 0), '0')}",
                ],
                queue_report,
            )

        if section == "memoria":
            memory_report = bundle.get("memory_report", {})
            resumo = memory_report.get("resumo", {})
            return (
                "Memoria",
                [
                    f"Entradas semanticas: {safe_label(resumo.get('total_entradas_semanticas', 0), '0')}",
                    f"Procedimentos: {safe_label(resumo.get('total_procedimentos', 0), '0')}",
                    f"Ultima escrita: {friendly_timestamp(resumo.get('ultima_escrita'))}",
                ],
                memory_report,
            )

        if section == "logs":
            audit_report = bundle.get("audit_report", {})
            persistencia = audit_report.get("persistencia", {})
            return (
                "Logs",
                [
                    f"Eventos auditados: {safe_label(persistencia.get('total_eventos', 0), '0')}",
                    f"Ultimas falhas: {safe_label(len(audit_report.get('ultimas_falhas', [])), '0')}",
                    f"Negacoes recentes: {safe_label(len(audit_report.get('ultimas_tentativas_negadas', [])), '0')}",
                ],
                audit_report,
            )

        if section == "seguranca":
            seguranca = system_report.get("seguranca_operacional", {})
            politica = system_report.get("politica_ativa", {})
            payload = {
                "seguranca_operacional": seguranca,
                "politica_ativa": politica,
                "ultimas_tentativas_negadas": bundle.get("audit_report", {}).get("ultimas_tentativas_negadas", []),
            }
            return (
                "Seguranca",
                [
                    f"Risco geral: {safe_label(seguranca.get('risco_geral'))}",
                    f"Fraquezas: {safe_label(seguranca.get('fraquezas_detectadas', 0), '0')}",
                    f"Acoes automaticas: {safe_label(seguranca.get('acoes_automaticas_realizadas', 0), '0')}",
                ],
                payload,
            )

        payload = {
            "system_report": system_report,
            "runtime_identity": bundle.get("runtime_identity", {}),
        }
        summary = [
            f"Runtime: {safe_label(runtime_state.get('status_ptbr'))}",
            f"Ciclos executados: {safe_label(system_report.get('total_ciclos_executados', 0), '0')}",
            f"Objetivos ativos: {safe_label(system_report.get('quantidade_objetivos_ativos', 0), '0')}",
            f"Ultimo ciclo: {safe_label(system_report.get('ultimo_ciclo_executado', {}).get('status_ptbr'))}",
        ]
        return "Sistema", summary, payload

    def _run_background(
        self,
        job_name: str,
        fn: Callable[[], Any],
        on_result: Callable[[Any], None],
        *,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        if job_name in self._active_jobs:
            return

        self._active_jobs.add(job_name)
        future = self.executor.submit(fn)
        self._running_futures[job_name] = future

        def _finish_job() -> None:
            self._active_jobs.discard(job_name)
            self._running_futures.pop(job_name, None)
            if on_finished is not None:
                on_finished()

        def _poll_future() -> None:
            current_future = self._running_futures.get(job_name)
            if current_future is None:
                return
            if not current_future.done():
                QTimer.singleShot(40, _poll_future)
                return

            try:
                exception = current_future.exception()
                if exception is not None:
                    self._on_background_error(
                        job_name,
                        "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
                    )
                else:
                    on_result(current_future.result())
            finally:
                _finish_job()

        QTimer.singleShot(0, _poll_future)

    def closeEvent(self, event) -> None:
        """Encerra o pool da janela sem deixar callbacks perdidos apos o close."""

        self.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
