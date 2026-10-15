"""Captura de tela do componente real de Qt, SEM servidor e SEM dados falsos.

Uso: Genesis.exe --capture-ui pasta (Windows) ou
     python -m interface.native_app.preview pasta (desenvolvimento).
Nunca solicita credenciais, rede, arquivos pessoais ou dados de usuario.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
from unittest.mock import patch


def capture_previews(output: Path) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["JARVIS_NATIVE_BRAIN_FORCE_FALLBACK"] = "1"

    from PySide6.QtWidgets import QApplication
    from interface.native_app.main_window import JarvisMainWindow
    from interface.native_app.runtime_bootstrap import RuntimeBootstrapResult
    from interface.native_app.config import NativeAppConfig

    class EmptyClient:
        """Nunca acessa rede. Janela real com todos os valores ainda vazios."""
        pass

    app = QApplication.instance() or QApplication(["genesis-preview"])
    # O QPA offscreen do CI pode nao descobrir as fontes do sistema.
    # Carregar uma fonte nativa so para screenshot evita caracteres vazios
    # sem distribuir nem embutir arquivos de fonte no aplicativo.
    from PySide6.QtGui import QFont, QFontDatabase
    if os.name == "nt" and not getattr(sys, "frozen", False):
        fonts_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
        for font_name in ("segoeui.ttf", "arial.ttf", "tahoma.ttf"):
            candidate = fonts_dir / font_name
            if candidate.is_file():
                loaded_id = QFontDatabase.addApplicationFont(str(candidate))
                print("GENESIS_SYSTEM_FONT", candidate.name, loaded_id, flush=True)
                if loaded_id >= 0:
                    break
    app.setFont(QFont("Segoe UI", 10))
    app.setApplicationName("Gênesis")
    config = NativeAppConfig(
        api_base_url="http://127.0.0.1:8000",
        api_token="apenas-captura-sem-conexao",
        device_id="captura-de-tela",
        python_executable=Path(sys.executable),
        project_root=Path.cwd(),
        runtime_entrypoint=Path("runtime/server.py"),
        startup_timeout_seconds=2,
        startup_poll_interval_seconds=.1,
        request_timeout_seconds=2,
        status_refresh_interval_ms=60000,
        brain_refresh_interval_ms=60000,
    )
    boot = RuntimeBootstrapResult(
        health_payload={},
        started_runtime=False,
        runtime_pid=None,
        startup_duration_seconds=0,
    )
    # Evita consultas ao runtime e atualizacoes. Esta nao e tela encenada:
    # instancia a mesma classe Qt da aplicacao compilada.
    with patch.object(JarvisMainWindow, "_schedule_refresh", lambda self: None):
        window = JarvisMainWindow(config=config, api_client=EmptyClient(),
                                  bootstrap_result=boot)
    window.resize(1440, 900)
    window.show()
    output.mkdir(parents=True, exist_ok=True)
    for key, filename in (
        ("chat", "01_inicio.png"),
        ("chat", "05_iris.png"),
        ("tarefas", "02_tarefas.png"),
        ("memoria", "03_memoria.png"),
        ("seguranca", "04_seguranca.png"),
    ):
        window._set_section(key)
        app.processEvents()
        image = window.grab()
        if image.isNull() or not image.save(str(output / filename)):
            window.close()
            return 3
    # Registro de janelas Qt reais, sem conexão ou arquivos do usuário.
    from interface.native_app.iris_mascot import IrisMascotWindow

    class PreviewSettings:
        def __init__(self):
            self.data = {}
        def value(self, key, default=None, type=None):
            return self.data.get(key, default)
        def setValue(self, key, value):
            self.data[key] = value

    mascot = IrisMascotWindow(settings=PreviewSettings())
    mascot.show()
    app.processEvents()
    photo = mascot.grab()
    if photo.isNull() or not photo.save(str(output / "06_mascote.png")):
        mascot.close()
        window.close()
        return 4

    mascot.open_lab(instant=True)
    app.processEvents()
    scene = mascot.lab.grab()
    if scene.isNull() or not scene.save(str(output / "07_laboratorio.png")):
        mascot.close()
        window.close()
        return 5
    mascot.close()
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(capture_previews(Path(sys.argv[1]) if len(sys.argv) > 1
                                      else Path("previews")))
