"""
JARVIS - Motor de Fracionamento de Carga e Divisão de Tarefas Multi-Dispositivo

Responsável por:
- avaliar a capacidade de hardware do dispositivo de acesso atual (RAM, CPU, nós)
- fracionar automaticamente tarefas pesadas em estilhaços (shards) distribuídos
- delegar shards pesados para servidores/nós de alta capacidade cadastrados no registro de dispositivos
- registrar o plano de fracionamento no fluxo de pensamentos privados do Dono
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHARDING_DIR = PROJECT_ROOT / "data" / "distributed_sharding"

# Limiares de capacidade pesada (RAM/CPU)
HEAVY_TASK_RAM_THRESHOLD_MB = 4096
HEAVY_TASK_CPU_THRESHOLD = 4


class DistributedTaskShardingEngine:
    """Motor de fracionamento distribuído de carga para prevenção de travamento em dispositivos leves."""

    def __init__(self, sharding_dir: Optional[Path] = None) -> None:
        self.sharding_dir = Path(sharding_dir) if sharding_dir else DEFAULT_SHARDING_DIR
        self.sharding_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def detect_total_memory_mb() -> Optional[float]:
        """Lê a RAM total real do sistema (POSIX via sysconf, ou /proc/meminfo). None se indisponível."""
        try:
            if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names and "SC_PAGE_SIZE" in os.sysconf_names:
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                if pages > 0 and page_size > 0:
                    return round(pages * page_size / (1024 * 1024), 1)
        except (ValueError, OSError):
            pass
        try:
            meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    kb = float(line.split()[1])
                    return round(kb / 1024, 1)
        except (OSError, ValueError, IndexError):
            pass
        return None

    def evaluate_and_shard_task(
        self,
        task_id: str,
        task_name: str,
        task_payload: Dict[str, Any],
        registered_devices: List[Dict[str, Any]],
        current_device_memory_mb: Optional[float] = None,
        current_device_cpu_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Avalia se o dispositivo atual suporta a carga da tarefa. Se não suportar, fraciona em shards
        e distribui entre os nós/servidores registrados.

        Quando `current_device_memory_mb`/`current_device_cpu_count` não são informados, o hardware
        real é detectado (RAM via sysconf/proc, CPUs via os.cpu_count) em vez de valores fixos.
        """
        now = datetime.now(timezone.utc).isoformat()

        autodetectado = current_device_memory_mb is None or current_device_cpu_count is None
        if current_device_memory_mb is None:
            detected = self.detect_total_memory_mb()
            current_device_memory_mb = detected if detected is not None else 2048.0
        if current_device_cpu_count is None:
            current_device_cpu_count = os.cpu_count() or 2

        # 1. Avaliação de Capacidade do Dispositivo Atual
        is_heavy_task = task_payload.get("pesada", True) or len(str(task_payload)) > 1000
        current_can_handle = (
            current_device_memory_mb >= HEAVY_TASK_RAM_THRESHOLD_MB
            and current_device_cpu_count >= HEAVY_TASK_CPU_THRESHOLD
        )

        sharding_required = is_heavy_task and not current_can_handle

        shards = []
        if sharding_required:
            # Encontra servidores/nós primários no registro
            server_nodes = [d for d in registered_devices if d.get("primary") or d.get("tipo") == "server"]
            if not server_nodes:
                server_nodes = [{"device_id": "jarvis-cloud-primary", "nome": "Nó Servidor Principal (Cloud/Local)"}]

            # Fraciona a tarefa em sub-estilhaços (shards)
            shards.append({
                "shard_id": f"{task_id}_shard_1",
                "alvo_execucao": "dispositivo_local",
                "descricao": "Pré-processamento e filtragem de contexto no dispositivo atual.",
                "porcentagem_carga": 15,
            })

            target_server = server_nodes[0]
            shards.append({
                "shard_id": f"{task_id}_shard_2",
                "alvo_execucao": target_server.get("device_id", "servidor_remoto"),
                "no_nome": target_server.get("nome", "Servidor"),
                "descricao": "Processamento pesado da árvore/banco de dados no nó de alta capacidade.",
                "porcentagem_carga": 85,
            })
        else:
            shards.append({
                "shard_id": f"{task_id}_shard_integral",
                "alvo_execucao": "dispositivo_local",
                "descricao": "Execução integral no dispositivo atual (capacidade suficiente).",
                "porcentagem_carga": 100,
            })

        sharding_plan = {
            "task_id": task_id,
            "task_name": task_name,
            "avaliado_em": now,
            "dispositivo_atual": {
                "no": platform.node(),
                "ram_mb": current_device_memory_mb,
                "cpus": current_device_cpu_count,
                "capacidade_suficiente": current_can_handle,
                "hardware_autodetectado": autodetectado,
            },
            "fracionamento_necessario": sharding_required,
            "total_shards": len(shards),
            "plano_shards": shards,
            "resumo_fracionamento_ptbr": (
                f"Fracionamento de Carga: Tarefa '{task_name}' dividida em {len(shards)} estilhaços. "
                f"Carga pesada desviada para o nó principal para evitar travamento local."
                if sharding_required else
                f"Dispositivo local suporta a tarefa '{task_name}'. Execução sem fracionamento."
            ),
        }

        return sharding_plan
