"""Testes de que executar um comando nao concede confianca a um dispositivo."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry
from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


class CommandDoesNotGrantTrustTests(unittest.TestCase):
    """O comando atualiza metadados; quem concede confianca e a camada de acesso."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.runtime = InternalAgentRuntime()
        self.runtime.task_queue = TaskQueue(storage_path=self.tmp / "queue.json")
        self.runtime.device_registry = DeviceRegistry(storage_path=self.tmp / "devices.json")
        self.runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=self.tmp / "semantic.json"),
            "procedural": ProceduralMemory(),
        }
        self.runtime.bootstrap()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_identificador_desconhecido_nao_vira_dispositivo_confiavel(self) -> None:
        """
        O modo emergencial de acesso web usa um identificador fixo e publico.

        Gravado como confiavel, ele permanecia no registro depois de o modo ser
        desligado, e entao o token sozinho voltava a bastar para passar pela
        verificacao de dispositivo que o operador acreditava ter reativado.
        """

        self.runtime.handle_command(text="status", source_device_id="web-access-recovery")

        self.assertFalse(self.runtime.device_registry.is_trusted("web-access-recovery"))

    def test_nenhum_identificador_novo_entra_no_registro_pelo_comando(self) -> None:
        """Executar um comando nao pode criar dispositivos."""

        antes = {device["device_id"] for device in self.runtime.device_registry.list_devices()}

        self.runtime.handle_command(text="status", source_device_id="dispositivo-inventado")

        depois = {device["device_id"] for device in self.runtime.device_registry.list_devices()}
        self.assertEqual(antes, depois)

    def test_dispositivo_ja_confiavel_continua_sendo_atualizado(self) -> None:
        """A atualizacao de metadados de um dispositivo legitimo segue funcionando."""

        self.runtime.device_registry.ensure_device(
            device_id="celular-do-dono",
            nome="celular-do-dono",
            tipo="client",
            trusted=True,
        )

        self.runtime.handle_command(text="status", source_device_id="celular-do-dono")

        registrado = next(
            device
            for device in self.runtime.device_registry.list_devices()
            if device["device_id"] == "celular-do-dono"
        )
        self.assertTrue(registrado["trusted"])
        self.assertEqual(registrado["metadata"].get("source"), "api_command")


if __name__ == "__main__":
    unittest.main()
