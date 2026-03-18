"""Widget Qt que hospeda o cerebro visual oficial do JARVIS no app nativo."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEB_ENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - protegido para ambientes sem addon web
    QWebEngineSettings = None
    QWebEngineView = QWidget
    WEB_ENGINE_AVAILABLE = False


VISIBLE_NEURON_COUNT = 1560
VISIBLE_SYNAPSE_COUNT = 14800
SCENE_HTML_PATH = Path(__file__).with_name("brain_scene.html")


def format_brain_summary(payload: dict[str, Any]) -> str:
    """Resume o mapa cognitivo para leitura rapida na UI nativa."""

    summary = payload.get("resumo", {})
    region = (summary.get("regiao_mais_ativa") or {}).get("label", "nenhuma")
    return "\n".join(
        [
            f"Foco atual: {region}",
            f"Eventos analisados: {summary.get('total_eventos', 0)}",
            f"Neuronios visiveis: {VISIBLE_NEURON_COUNT}",
            f"Sinapses visiveis: {VISIBLE_SYNAPSE_COUNT}",
        ]
    )


def format_brain_analysis(payload: dict[str, Any]) -> str:
    """Resume a analise cognitiva para o painel lateral do app."""

    top_regions = ", ".join(item.get("label", "-") for item in payload.get("regioes_mais_utilizadas", [])[:4])
    low_regions = ", ".join(item.get("label", "-") for item in payload.get("regioes_subutilizadas", [])[:2])
    strong_trails = ", ".join(
        f"{item.get('source_label', '?')} -> {item.get('target_label', '?')}"
        for item in payload.get("conexoes_mais_fortes", [])[:3]
    )
    return "\n".join(
        [
            f"Regioes em destaque: {top_regions or 'nenhuma'}",
            f"Menor atividade: {low_regions or 'nenhuma'}",
            f"Trilhas dominantes: {strong_trails or 'nenhuma'}",
            "Rede integrada: memoria, planejamento, execucao, seguranca e evolucao.",
            "Interacao: clique no cerebro para expandir e navegar em 3D.",
        ]
    )


def _should_use_web_brain() -> bool:
    """Indica se o host web oficial do cerebro pode ser usado neste ambiente."""
    platform = str(os.environ.get("QT_QPA_PLATFORM", "")).lower()
    if platform == "offscreen":
        return False
    if os.environ.get("JARVIS_NATIVE_BRAIN_FORCE_FALLBACK") == "1":
        return False
    return WEB_ENGINE_AVAILABLE and SCENE_HTML_PATH.exists()


class _BrainWebView(QWebEngineView):
    """Web view do cerebro com clique compacto para expansao."""

    compactClicked = Signal()

    def __init__(self, compact_mode: bool, parent: QWidget | None = None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent)
        self.compact_mode = compact_mode
        self._press_pos = QPoint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Registra o pressionamento do mouse neste widget."""
        self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Registra a liberacao do mouse neste widget."""
        if self.compact_mode and event.button() == Qt.LeftButton:
            current_pos = event.position().toPoint()
            if (current_pos - self._press_pos).manhattanLength() <= 6:
                self.compactClicked.emit()
                event.accept()
                return
        super().mouseReleaseEvent(event)


class _WebBrainCanvas(QWidget):
    """Container reutilizavel da cena web do cerebro."""

    expandRequested = Signal()

    def __init__(self, *, compact_mode: bool, parent: QWidget | None = None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent)
        self.compact_mode = compact_mode
        self._scene_ready = False
        self._evolution_payload: dict[str, Any] = {}
        self._analysis_payload: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = _BrainWebView(compact_mode=compact_mode, parent=self)
        self.view.compactClicked.connect(self.expandRequested.emit)
        layout.addWidget(self.view)

        self._configure_view()
        self.view.loadFinished.connect(self._on_scene_loaded)
        self.view.load(self._build_scene_url())

    def _build_scene_url(self) -> QUrl:
        """Monta scene url para o fluxo atual."""
        url = QUrl.fromLocalFile(str(SCENE_HTML_PATH))
        query = QUrlQuery()
        query.addQueryItem("mode", "compact" if self.compact_mode else "expanded")
        url.setQuery(query)
        return url

    def _configure_view(self) -> None:
        """Executa a rotina interna de configure view."""
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, False)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)

    def set_payload(self, evolution_payload: dict[str, Any], analysis_payload: dict[str, Any]) -> None:
        """Atualiza a carga de dados exibida por este componente."""
        self._evolution_payload = evolution_payload or {}
        self._analysis_payload = analysis_payload or {}
        self._push_payload_to_scene()

    def _on_scene_loaded(self, ok: bool) -> None:
        """Executa a rotina interna de on scene loaded."""
        self._scene_ready = ok
        if ok:
            self._push_payload_to_scene()

    def _push_payload_to_scene(self) -> None:
        """Executa a rotina interna de push payload to scene."""
        if not self._scene_ready:
            return

        payload = {
            "evolution": self._evolution_payload,
            "analysis": self._analysis_payload,
        }
        payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        script = f"window.jarvisNativeBrainScene && window.jarvisNativeBrainScene.updateState({payload_json});"
        self.view.page().runJavaScript(script)


class _ExpandedBrainDialog(QDialog):
    """Sobreposicao para navegar no cerebro em destaque."""

    def __init__(self, parent: QWidget, evolution_payload: dict[str, Any], analysis_payload: dict[str, Any]) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent.window())
        self.setModal(True)
        self.setWindowTitle("JARVIS Brain")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(
            """
            QDialog {
                background: rgba(2, 6, 10, 242);
            }
            QLabel#BrainOverlayTitle {
                color: #f1f7fb;
                font: 700 15px 'Bahnschrift';
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel#BrainOverlayHint {
                color: #8fa5b4;
                font: 11px 'Bahnschrift';
            }
            QPushButton#BrainOverlayClose {
                background: #0b1620;
                color: #f1f7fb;
                border: 1px solid #294356;
                border-radius: 14px;
                padding: 8px 14px;
            }
            QPushButton#BrainOverlayClose:hover {
                background: #132330;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        title = QLabel("Cerebro do Jarvis")
        title.setObjectName("BrainOverlayTitle")
        hint = QLabel("A visualizacao ampliada reutiliza a mesma biblioteca oficial do painel web.")
        hint.setObjectName("BrainOverlayHint")

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(4)
        title_block.addWidget(title)
        title_block.addWidget(hint)

        close_button = QPushButton("Fechar")
        close_button.setObjectName("BrainOverlayClose")
        close_button.clicked.connect(self.close)

        header.addLayout(title_block, 1)
        header.addWidget(close_button, 0, Qt.AlignRight)

        layout.addLayout(header)

        self.canvas = _WebBrainCanvas(compact_mode=False, parent=self)
        self.canvas.set_payload(evolution_payload, analysis_payload)
        layout.addWidget(self.canvas, 1)

        parent_window = parent.window()
        self.resize(parent_window.size())
        self.move(parent_window.pos())

    def keyPressEvent(self, event) -> None:
        """Trata o pressionamento de tecla neste componente."""
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


class _FallbackBrainWidget(QWidget):
    """Fallback leve para testes headless e ambientes sem WebEngine."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent)
        self._evolution_payload: dict[str, Any] = {}
        self._analysis_payload: dict[str, Any] = {}
        self._focus_labels: list[str] = []
        self._pulse_phase = 0.0
        self.setMinimumSize(320, 360)
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._advance_animation)
        self._animation_timer.start(45)

    def set_payload(self, evolution_payload: dict[str, Any], analysis_payload: dict[str, Any]) -> None:
        """Atualiza a carga de dados exibida por este componente."""
        self._evolution_payload = evolution_payload or {}
        self._analysis_payload = analysis_payload or {}
        focus_labels = [item.get("label") for item in self._analysis_payload.get("regioes_mais_utilizadas", [])[:4]]
        dominant = (self._evolution_payload.get("resumo", {}).get("regiao_mais_ativa") or {}).get("label")
        if dominant:
            focus_labels.insert(0, dominant)
        self._focus_labels = [label for label in focus_labels if label]
        self.update()

    def _advance_animation(self) -> None:
        """Executa a rotina interna de advance animation."""
        self._pulse_phase = (self._pulse_phase + 0.016) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:
        """Desenha o frame atual deste widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        rect = QRectF(self.rect())
        self._paint_background(painter, rect)
        self._paint_brain_shell(painter, rect)
        self._paint_cognitive_regions(painter, rect)
        self._paint_overlay_text(painter, rect)

    def _paint_background(self, painter: QPainter, rect: QRectF) -> None:
        """Desenha background neste widget."""
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#020508"))
        gradient.setColorAt(0.45, QColor("#06111a"))
        gradient.setColorAt(1.0, QColor("#010305"))
        painter.fillRect(rect, gradient)

    def _paint_brain_shell(self, painter: QPainter, rect: QRectF) -> None:
        """Desenha brain shell neste widget."""
        shell_rect = rect.adjusted(30, 24, -30, -34)
        painter.save()
        painter.setPen(Qt.NoPen)

        gradient = QRadialGradient(shell_rect.center(), shell_rect.width() * 0.55)
        gradient.setColorAt(0.0, QColor(22, 36, 54, 132))
        gradient.setColorAt(0.7, QColor(8, 14, 24, 90))
        gradient.setColorAt(1.0, QColor(3, 6, 10, 14))
        painter.setBrush(gradient)
        painter.drawEllipse(shell_rect)

        left_path = QPainterPath()
        left_path.moveTo(shell_rect.center().x(), shell_rect.top() + 26)
        left_path.cubicTo(
            shell_rect.left() + 24,
            shell_rect.top() - 6,
            shell_rect.left() - 4,
            shell_rect.center().y() - 36,
            shell_rect.left() + 32,
            shell_rect.bottom() - 56,
        )
        left_path.cubicTo(
            shell_rect.left() + 74,
            shell_rect.bottom() - 6,
            shell_rect.center().x() - 34,
            shell_rect.bottom() - 18,
            shell_rect.center().x() - 10,
            shell_rect.top() + 34,
        )

        right_path = QPainterPath()
        right_path.moveTo(shell_rect.center().x(), shell_rect.top() + 26)
        right_path.cubicTo(
            shell_rect.right() - 24,
            shell_rect.top() - 6,
            shell_rect.right() + 4,
            shell_rect.center().y() - 36,
            shell_rect.right() - 32,
            shell_rect.bottom() - 56,
        )
        right_path.cubicTo(
            shell_rect.right() - 74,
            shell_rect.bottom() - 6,
            shell_rect.center().x() + 34,
            shell_rect.bottom() - 18,
            shell_rect.center().x() + 10,
            shell_rect.top() + 34,
        )

        painter.setBrush(QColor(10, 18, 28, 72))
        painter.drawPath(left_path)
        painter.drawPath(right_path)

        painter.setPen(QPen(QColor(124, 160, 188, 70), 1.4))
        painter.drawPath(left_path)
        painter.drawPath(right_path)
        painter.setPen(QPen(QColor(145, 172, 195, 62), 1.2, Qt.DashLine))
        painter.drawLine(
            QPointF(shell_rect.center().x(), shell_rect.top() + 34),
            QPointF(shell_rect.center().x(), shell_rect.bottom() - 36),
        )
        painter.restore()

    def _paint_cognitive_regions(self, painter: QPainter, rect: QRectF) -> None:
        """Desenha cognitive regions neste widget."""
        shell_rect = rect.adjusted(44, 48, -44, -58)
        labels = self._focus_labels or ["Memoria", "Planejamento", "Execucao", "Seguranca"]
        base_points = [
            QPointF(shell_rect.center().x() - (shell_rect.width() * 0.22), shell_rect.center().y() - 26),
            QPointF(shell_rect.center().x() + (shell_rect.width() * 0.2), shell_rect.center().y() - 52),
            QPointF(shell_rect.center().x() - (shell_rect.width() * 0.14), shell_rect.center().y() + 28),
            QPointF(shell_rect.center().x() + (shell_rect.width() * 0.1), shell_rect.center().y() + 14),
        ]
        palette = ["#4f8cff", "#ffd74a", "#54de73", "#ff5d5d"]

        painter.save()
        painter.setPen(Qt.NoPen)
        for index, point in enumerate(base_points):
            color = QColor(palette[index % len(palette)])
            intensity = 0.48 + (0.28 * ((self._pulse_phase + (index * 0.18)) % 1.0))
            halo = QRadialGradient(point, 54 + (index * 6))
            halo.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), int(148 * intensity)))
            halo.setColorAt(0.52, QColor(color.red(), color.green(), color.blue(), int(84 * intensity)))
            halo.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(halo)
            painter.drawEllipse(point, 34 + (index * 4), 26 + (index * 3))

            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 214))
            painter.drawEllipse(point, 4.6 + index, 4.6 + index)
        painter.restore()

        painter.save()
        painter.setFont(QFont("Bahnschrift", 8))
        for index, point in enumerate(base_points):
            label = labels[index % len(labels)]
            target = QPointF(point.x() + 44, point.y() + 16)
            painter.setPen(QPen(QColor("#7ec7df"), 1.0))
            painter.drawLine(point, target)
            painter.setPen(QColor("#eef6fb"))
            painter.drawText(QRectF(target.x() + 6, target.y() - 12, 140, 24), Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.restore()

    def _paint_overlay_text(self, painter: QPainter, rect: QRectF) -> None:
        """Desenha overlay text neste widget."""
        summary = self._evolution_payload.get("resumo", {})
        caption = (
            f"Cerebro 3D em fallback  |  eventos {summary.get('total_eventos', 0)}"
            f"  |  neuronios {VISIBLE_NEURON_COUNT}"
        )
        painter.save()
        painter.setPen(QColor("#dce7ed"))
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(rect.adjusted(16, 10, -16, -10), Qt.AlignLeft | Qt.AlignTop, caption)
        painter.restore()


class NativeBrainWidget(QWidget):
    """Renderiza o cerebro do Jarvis em cena 3D local ou fallback headless."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__(parent)
        self._evolution_payload: dict[str, Any] = {}
        self._analysis_payload: dict[str, Any] = {}
        self._use_web_brain = _should_use_web_brain()
        self._expanded_dialog: _ExpandedBrainDialog | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if self._use_web_brain:
            self._backend: QWidget = _WebBrainCanvas(compact_mode=True, parent=self)
            self._backend.expandRequested.connect(self._open_expanded_view)
        else:
            self._backend = _FallbackBrainWidget(self)

        layout.addWidget(self._backend)
        self.setMinimumSize(320, 360)

    def sizeHint(self) -> QSize:
        """Retorna o tamanho sugerido deste widget."""
        return QSize(420, 520)

    def set_payload(self, evolution_payload: dict[str, Any], analysis_payload: dict[str, Any]) -> None:
        """Atualiza o cerebro com o estado cognitivo mais recente."""

        self._evolution_payload = evolution_payload or {}
        self._analysis_payload = analysis_payload or {}

        if self._use_web_brain:
            backend = self._backend
            if isinstance(backend, _WebBrainCanvas):
                backend.set_payload(self._evolution_payload, self._analysis_payload)
            if self._expanded_dialog is not None:
                self._expanded_dialog.canvas.set_payload(self._evolution_payload, self._analysis_payload)
            return

        fallback = self._backend
        if isinstance(fallback, _FallbackBrainWidget):
            fallback.set_payload(self._evolution_payload, self._analysis_payload)

    def _open_expanded_view(self) -> None:
        """Abre expanded view no fluxo atual."""
        if not self._use_web_brain:
            return
        if self._expanded_dialog is not None and self._expanded_dialog.isVisible():
            self._expanded_dialog.raise_()
            self._expanded_dialog.activateWindow()
            return

        self._expanded_dialog = _ExpandedBrainDialog(self, self._evolution_payload, self._analysis_payload)
        self._expanded_dialog.finished.connect(self._clear_expanded_dialog)
        self._expanded_dialog.show()

    def _clear_expanded_dialog(self) -> None:
        """Limpa expanded dialog do contexto atual."""
        self._expanded_dialog = None
