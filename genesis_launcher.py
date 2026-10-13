"""Ponto de entrada portatil do Gênesis / ZERO (Windows).

O mesmo executavel inicia GUI e servidor local; nao requer Python instalado
no computador final. Opcao de captura existe apenas para homologacao visual.
Os nomes JARVIS_* permanecem compatibilidade de config interna no MVP.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def _prepare_portable_environment() -> None:
    if not getattr(sys, "frozen", False):
        return
    root = Path(sys.executable).resolve().parent
    # Pastas gravaveis junto ao instalavel portatil; os modulos/codigo ficam
    # isolados no _internal de PyInstaller.
    for name, folder in (
        ("JARVIS_DATA_DIR", "data"),
        ("JARVIS_LOGS_DIR", "logs"),
        ("JARVIS_REPORTS_DIR", "reports"),
    ):
        os.environ.setdefault(name, str(root / folder))
    # Protecao padrao contra exposicao de API para toda a rede.
    os.environ.setdefault("JARVIS_API_HOST", "127.0.0.1")
    os.environ.setdefault("JARVIS_INFERENCE_OFFLINE_MODE", "true")
    os.environ.setdefault("JARVIS_FREELLMAPI_ENABLED", "false")
    os.environ.setdefault("JARVIS_AGENCY_ENABLED", "false")
    os.environ.setdefault("JARVIS_NATIVE_BRAIN_FORCE_FALLBACK", "1")


def main() -> int:
    _prepare_portable_environment()
    args = sys.argv[1:]
    if args and args[0] == "--server":
        from runtime.server import main as server_main
        return server_main(args[1:])
    if args and args[0] == "--capture-ui":
        if len(args) != 2:
            print("Uso: Genesis.exe --capture-ui DIRETORIO", file=sys.stderr)
            return 2
        from interface.native_app.preview import capture_previews
        return capture_previews(Path(args[1]))
    from interface.native_app.main import main as native_main
    return native_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
