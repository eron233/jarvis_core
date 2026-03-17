"""Wrapper tecnico sem console do aplicativo nativo real do JARVIS."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from interface.native_app.main import main as native_app_main


if __name__ == "__main__":
    raise SystemExit(native_app_main())

