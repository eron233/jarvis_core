"""Utilitarios simples para tarefas em background na interface nativa."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class TaskSignals(QObject):
    """Sinais emitidos por uma tarefa de background."""

    result = Signal(object)
    error = Signal(str, str)
    finished = Signal()


class BackgroundTask(QRunnable):
    """Executa um callable fora da thread principal e devolve o resultado via sinais."""

    def __init__(self, name: str, fn: Callable[[], Any]) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        super().__init__()
        self.name = name
        self.fn = fn
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        """Executa a tarefa configurada e publica sucesso ou erro."""

        try:
            result = self.fn()
        except Exception:
            self.signals.error.emit(self.name, traceback.format_exc())
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
