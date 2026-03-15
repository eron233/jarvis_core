"""Entrypoint sem console do aplicativo nativo do JARVIS."""

from __future__ import annotations

from startup_bootstrap import ensure_project_root_on_path

ensure_project_root_on_path(__file__)

from interface.native_app.main import main


if __name__ == "__main__":
    raise SystemExit(main())

