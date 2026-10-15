"""Interface nativa da Íris: apresentação separada do runtime e sem sensores simulados."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from interface.native_app.iris_state import normalize_state, state_metadata


ASSET_PATH = Path(__file__).resolve().parent / "assets" / "iris_photo.jpg"
FALLBACK_ASSET_PATH = Path(__file__).resolve().parent / "assets" / "iris_portrait.svg"


class IrisPresenceWidget(QFrame):
    """Retrato configurável, indicadores verídicos e animação econômica."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("IrisPresence")
        self.setAccessibleName("Íris, assistente virtual do Gênesis")
        self.state = "offline"
        self._reduced_motion = os.environ.get("IRIS_REDUCED_MOTION", "").lower() in ("1", "true", "yes")
        self._pulse_visible = True
        self._timer = QTimer(self)
        self._timer.setInterval(460)
        self._timer.timeout.connect(self._pulse)
        self.setStyleSheet("""
            #IrisPresence { background: #090f17; border: 1px solid #213747; border-radius: 22px; }
            #IrisName { color: #e9f7ff; font-size: 25px; font-weight: 700; letter-spacing: 3px; }
            #IrisEyebrow { color: #96afc1; font-size: 10px; letter-spacing: 2px; }
            #IrisState { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            #IrisDetail { color: #bed0dc; font-size: 12px; }
            #IrisFooter { color: #7796a9; font-size: 10px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 17, 14, 17)
        layout.setSpacing(8)

        heading = QLabel("PRESENÇA DIGITAL   /   GÊNESIS")
        heading.setObjectName("IrisEyebrow")
        heading.setAlignment(Qt.AlignCenter)
        layout.addWidget(heading)

        self.portrait = QLabel()
        self.portrait.setFixedSize(216, 216)
        self.portrait.setAlignment(Qt.AlignCenter)
        self.portrait.setAccessibleName("Retrato ilustrado de Íris, androide prateada")
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.portrait)
        row.addStretch()
        layout.addLayout(row)
        self._load_portrait()

        name = QLabel("Í R I S")
        name.setObjectName("IrisName")
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)

        status_row = QHBoxLayout()
        status_row.addStretch()
        self.state_dot = QLabel("●")
        self.state_label = QLabel()
        self.state_label.setObjectName("IrisState")
        status_row.addWidget(self.state_dot)
        status_row.addWidget(self.state_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.detail_label = QLabel()
        self.detail_label.setObjectName("IrisDetail")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumHeight(32)
        layout.addWidget(self.detail_label)

        footer = QLabel("CONVERSA  ·  EXECUÇÃO SUPERVISIONADA")
        footer.setObjectName("IrisFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
        self.set_state("offline")

    def _load_portrait(self) -> None:
        """IRIS_AVATAR_PATH permite usar a imagem original sem publicar dados pessoais."""
        override = os.environ.get("IRIS_AVATAR_PATH", "").strip()
        source_path = Path(override).expanduser() if override else ASSET_PATH
        if not source_path.is_file():
            source_path = ASSET_PATH
        original = QPixmap(str(source_path))
        if original.isNull():
            original = QPixmap(str(FALLBACK_ASSET_PATH))
        if original.isNull():
            self.portrait.setText("Í")
            self.portrait.setStyleSheet("font-size: 90px; color: #a3f1ff; background: #142738;")
            return
        scaled = original.scaled(216, 216, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        out = QPixmap(216, 216)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        mask = QPainterPath()
        mask.addRoundedRect(QRectF(0, 0, 216, 216), 20, 20)
        painter.setClipPath(mask)
        painter.drawPixmap((216 - scaled.width()) // 2, (216 - scaled.height()) // 2, scaled)
        painter.end()
        self.portrait.setPixmap(out)

    def set_state(self, state: str, detail: str = "") -> None:
        """Somente eventos reais do cliente alteram o estado."""
        self.state = normalize_state(state)
        label, default_detail, color = state_metadata(self.state)
        self.state_label.setText(label)
        self.state_label.setStyleSheet("color: " + color + ";")
        self.detail_label.setText(detail or default_detail)
        self.setAccessibleDescription(label + ". " + (detail or default_detail))
        self.state_dot.show()
        self.state_dot.setStyleSheet("color: " + color + ";")
        self._pulse_visible = True
        if self.state in ("listening", "thinking", "working") and not self._reduced_motion:
            self._timer.start()
        else:
            self._timer.stop()

    def _pulse(self) -> None:
        if self.isVisible():
            self._pulse_visible = not self._pulse_visible
            self.state_dot.setVisible(self._pulse_visible)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
