"""
Testes unitários cobrindo o fracionamento de carga e divisão de tarefas multi-dispositivo.
"""

from pathlib import Path
import tempfile
import unittest

from device.distributed_task_sharding_engine import DistributedTaskShardingEngine
from runtime.internal_agent_runtime import InternalAgentRuntime


class DistributedTaskShardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_task_sharding_when_device_is_light(self) -> None:
        engine = DistributedTaskShardingEngine(sharding_dir=self.tmp_path)

        devices = [
            {"device_id": "server-node-1", "nome": "Servidor Principal", "primary": True, "tipo": "server"}
        ]

        # Simula dispositivo leve (ex: celular com 2GB de RAM e 2 CPUs)
        plan = engine.evaluate_and_shard_task(
            task_id="heavy_job_1",
            task_name="Análise de Mercado Pesada",
            task_payload={"pesada": True},
            registered_devices=devices,
            current_device_memory_mb=2048.0,
            current_device_cpu_count=2,
        )

        self.assertTrue(plan["fracionamento_necessario"])
        self.assertEqual(plan["total_shards"], 2)
        self.assertEqual(plan["plano_shards"][1]["alvo_execucao"], "server-node-1")

    def test_no_sharding_when_device_has_high_capacity(self) -> None:
        engine = DistributedTaskShardingEngine(sharding_dir=self.tmp_path)

        # Simula PC/Servidor com 16GB RAM e 8 CPUs
        plan = engine.evaluate_and_shard_task(
            task_id="job_2",
            task_name="Processamento Local",
            task_payload={"pesada": True},
            registered_devices=[],
            current_device_memory_mb=16384.0,
            current_device_cpu_count=8,
        )

        self.assertFalse(plan["fracionamento_necessario"])
        self.assertEqual(plan["total_shards"], 1)

    def test_runtime_integration_of_sharding_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "distributed_task_sharding_engine"))


if __name__ == "__main__":
    unittest.main()
