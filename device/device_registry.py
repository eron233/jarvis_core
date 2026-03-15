"""
JARVIS - Registro de Dispositivos

Responsavel por:
- manter a lista de dispositivos autorizados do sistema
- persistir o inventario de dispositivos confiaveis
- permitir evolucao futura para multiplos clientes leves

Integracoes principais:
- interface.api.app
- runtime.internal_agent_runtime
- security.access_control
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List


# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Registro persistente de dispositivos confiaveis
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "data" / "device_registry.json"
DEFAULT_DEVICES: List[Dict[str, Any]] = [
    {
        "device_id": "celular",
        "nome": "Celular principal",
        "tipo": "mobile",
        "trusted": True,
        "primary": True,
        "metadata": {"perfil": "cliente_leve"},
    },
    {
        "device_id": "notebook_atual",
        "nome": "Notebook atual",
        "tipo": "desktop",
        "trusted": True,
        "primary": False,
        "metadata": {"perfil": "operacao_local"},
    },
    {
        "device_id": "future_workstations",
        "nome": "Future workstations",
        "tipo": "workstation",
        "trusted": True,
        "primary": False,
        "metadata": {"perfil": "expansao_futura"},
    },
]


@dataclass
class DeviceRegistry:
    """Mantem um inventario simples e persistente de dispositivos confiaveis."""

    storage_path: Path = field(default_factory=lambda: DEFAULT_REGISTRY_PATH)
    devices: List[Dict[str, Any]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        """Normaliza o path e garante um registro inicial utilizavel."""

        self.storage_path = Path(self.storage_path)
        if not self.devices:
            self.devices = deepcopy(DEFAULT_DEVICES)
        self.load()

    def load(self) -> Dict[str, Any]:
        """Carrega o registro persistente do disco."""

        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self.devices = [self._normalize_device(device) for device in deepcopy(DEFAULT_DEVICES)]
                return self.save()

            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            persisted_devices = data.get("devices", [])
            if isinstance(persisted_devices, list) and persisted_devices:
                self.devices = [self._normalize_device(device) for device in persisted_devices]
            else:
                self.devices = [self._normalize_device(device) for device in deepcopy(DEFAULT_DEVICES)]
            return self.snapshot()

    def save(self) -> Dict[str, Any]:
        """Persiste o registro atual no disco."""

        with self._lock:
            snapshot = self.snapshot()
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.storage_path.with_name(
                f"{self.storage_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temp_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

            for attempt in range(5):
                try:
                    os.replace(temp_path, self.storage_path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return snapshot

    def snapshot(self) -> Dict[str, Any]:
        """Retorna o estado serializavel do registro."""

        with self._lock:
            trusted_total = len([device for device in self.devices if device.get("trusted")])
            primary_devices = [device["device_id"] for device in self.devices if device.get("primary")]
            return {
                "updated_at": self._utc_now(),
                "device_count": len(self.devices),
                "trusted_device_count": trusted_total,
                "primary_devices": primary_devices,
                "devices": [deepcopy(self._normalize_device(device)) for device in self.devices],
            }

    def list_devices(self, trusted_only: bool = False) -> List[Dict[str, Any]]:
        """Lista os dispositivos conhecidos, opcionalmente filtrando os confiaveis."""

        with self._lock:
            devices = [deepcopy(self._normalize_device(device)) for device in self.devices]
            if trusted_only:
                devices = [device for device in devices if device.get("trusted")]
            return devices

    def ensure_device(
        self,
        device_id: str,
        nome: str | None = None,
        tipo: str = "client",
        trusted: bool = True,
        primary: bool = False,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Garante que um dispositivo exista no registro, atualizando sua confianca quando necessario."""

        with self._lock:
            normalized_id = str(device_id).strip()
            if not normalized_id:
                raise ValueError("device_id nao pode ficar vazio.")

            for device in self.devices:
                if device["device_id"] != normalized_id:
                    continue

                new_name = nome or device.get("nome") or normalized_id
                new_type = tipo or device.get("tipo", "client")
                new_trusted = bool(trusted)
                new_primary = bool(primary or device.get("primary", False))
                merged_metadata = dict(device.get("metadata", {}))
                merged_metadata.update(metadata or {})

                changed = any(
                    (
                        device.get("nome") != new_name,
                        device.get("tipo") != new_type,
                        bool(device.get("trusted")) != new_trusted,
                        bool(device.get("primary")) != new_primary,
                        dict(device.get("metadata", {})) != merged_metadata,
                    )
                )

                if changed:
                    device["nome"] = new_name
                    device["tipo"] = new_type
                    device["trusted"] = new_trusted
                    device["primary"] = new_primary
                    device["updated_at"] = self._utc_now()
                    device["metadata"] = merged_metadata
                    self.save()

                return deepcopy(self._normalize_device(device))

            device = self._normalize_device(
                {
                    "device_id": normalized_id,
                    "nome": nome or normalized_id,
                    "tipo": tipo,
                    "trusted": trusted,
                    "primary": primary,
                    "metadata": metadata or {},
                }
            )
            self.devices.append(device)
            self.save()
            return deepcopy(device)

    def is_trusted(self, device_id: str | None) -> bool:
        """Informa se o device id informado esta autorizado."""

        with self._lock:
            if not device_id:
                return False
            normalized = str(device_id).strip()
            return any(
                device["device_id"] == normalized and bool(device.get("trusted"))
                for device in self.devices
            )

    def build_report(self) -> Dict[str, Any]:
        """Retorna um resumo amigavel do registro de dispositivos."""

        trusted_devices = self.list_devices(trusted_only=True)
        return {
            "mensagem": "Registro de dispositivos carregado com sucesso.",
            "caminho_registro": str(self.storage_path),
            "total_dispositivos": len(self.devices),
            "total_dispositivos_confiaveis": len(trusted_devices),
            "dispositivo_principal": next(
                (device["device_id"] for device in trusted_devices if device.get("primary")),
                None,
            ),
            "dispositivos_confiaveis": trusted_devices,
        }

    def _normalize_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        normalized_device = deepcopy(device)
        now = self._utc_now()
        normalized_device["device_id"] = str(normalized_device.get("device_id", "")).strip()
        normalized_device["nome"] = str(
            normalized_device.get("nome") or normalized_device["device_id"]
        ).strip()
        normalized_device["tipo"] = str(normalized_device.get("tipo", "client")).strip()
        normalized_device["trusted"] = bool(normalized_device.get("trusted", False))
        normalized_device["primary"] = bool(normalized_device.get("primary", False))
        normalized_device["metadata"] = dict(normalized_device.get("metadata", {}))
        normalized_device["registered_at"] = str(normalized_device.get("registered_at") or now)
        normalized_device["updated_at"] = str(normalized_device.get("updated_at") or now)
        return normalized_device

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
