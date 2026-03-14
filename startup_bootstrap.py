"""Bootstrap leve para garantir imports do projeto nos entrypoints oficiais."""

from __future__ import annotations

from pathlib import Path
import sys


def discover_project_root(current_file: str | Path) -> Path:
    """Encontra a raiz do projeto a partir de um arquivo conhecido."""

    current_path = Path(current_file).resolve()
    search_root = current_path.parent if current_path.is_file() else current_path

    for candidate in (search_root, *search_root.parents):
        if (
            (candidate / "main.py").exists()
            and (candidate / "runtime").is_dir()
            and (candidate / "interface").is_dir()
        ):
            return candidate

    return search_root


def ensure_project_root_on_path(current_file: str | Path) -> Path:
    """Garante que a raiz do projeto esteja no ``sys.path``."""

    project_root = discover_project_root(current_file)
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    return project_root
