"""Testes do registro de dispositivos autorizados do Jarvis."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry


def make_registry_path(name: str) -> Path:
    """Retorna o path isolado usado pelos testes do registro de dispositivos."""

    return PROJECT_ROOT / "tests" / "_device_artifacts" / f"{name}_devices.json"


def reset_storage_path(path: Path) -> None:
    """Garante que o artefato de teste inicie vazio."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class DeviceRegistryTests(unittest.TestCase):
    """Valida persistencia e confianca do registro de dispositivos."""

    def test_registry_loads_default_devices(self) -> None:
        """Confirma que o inventario inicial do Jarvis esta disponivel em memoria."""

        path = make_registry_path("defaults")
        reset_storage_path(path)

        registry = DeviceRegistry(storage_path=path)

        self.assertGreaterEqual(len(registry.list_devices()), 3)
        self.assertTrue(registry.is_trusted("celular"))

    def test_registry_persists_new_trusted_device(self) -> None:
        """Garante roundtrip de persistencia ao registrar um novo dispositivo confiavel."""

        path = make_registry_path("persist")
        reset_storage_path(path)

        registry = DeviceRegistry(storage_path=path)
        registry.ensure_device(
            device_id="eron-celular-principal",
            nome="Celular do Eron",
            trusted=True,
            primary=True,
            metadata={"source": "unit-test"},
        )

        reloaded = DeviceRegistry(storage_path=path)
        self.assertTrue(reloaded.is_trusted("eron-celular-principal"))
        self.assertTrue(any(device["primary"] for device in reloaded.list_devices(trusted_only=True)))

    def test_registry_avoids_rewriting_when_device_is_unchanged(self) -> None:
        """Evita salvar em disco a cada request identica do app nativo."""

        path = make_registry_path("unchanged")
        reset_storage_path(path)

        registry = DeviceRegistry(storage_path=path)
        registry.ensure_device(
            device_id="jarvis-dispositivo-local",
            nome="jarvis-dispositivo-local",
            trusted=True,
            primary=True,
            metadata={"source": "api_security_gate", "last_client_host": "127.0.0.1"},
        )

        with patch.object(registry, "save", wraps=registry.save) as save_mock:
            registry.ensure_device(
                device_id="jarvis-dispositivo-local",
                nome="jarvis-dispositivo-local",
                trusted=True,
                primary=True,
                metadata={"source": "api_security_gate", "last_client_host": "127.0.0.1"},
            )

        save_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
