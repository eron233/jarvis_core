"""Malha de presenca da Iris em aparelhos autorizados.

Uma instancia logica pode usar varios dispositivos. Nao ha propagacao, scan,
instalacao automatica, acesso remoto ou controle fisico neste modulo.
Roteadores/switches/IoT podem ser *adaptadores*; nao se presume que rodem Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import re
import secrets
import threading
import time
from typing import Callable

from security.iris_instance_policy import IrisInstanceAuthority


NAME_MAX = 80
PAIR_TTL_SECONDS = 300
HEARTBEAT_TTL_SECONDS = 90
VISIT_MAX_SECONDS = 7200
MAX_DEVICES_PER_INSTANCE = 32

# Recursos que um adaptador pode anunciar; nao sao permissoes de SO.
_SURFACES = frozenset({
    "presence.display", "audio.input", "audio.output",
    "diagnostics.read", "compute.infer", "compute.light",
    "media.read", "sensor.read", "automation.authorized",
})
_DEVICE_TYPES = frozenset({
    "windows", "linux", "macos", "android", "ios", "smart_tv",
    "router", "switch", "scooter", "coffee_machine", "iot", "generic",
})
_NATIVE = frozenset({"windows", "linux", "macos", "android"})
_UI_ONLY = frozenset({"ios", "smart_tv"})
_BRIDGE = frozenset({"router", "switch", "scooter", "coffee_machine", "iot", "generic"})
_SAFE_BRIDGE = frozenset({"diagnostics.read", "sensor.read", "media.read"})
_DEVICE_ID_RE = re.compile(r"^iris-node-[a-f0-9]{32}$")


@dataclass(frozen=True)
class DeviceOffer:
    offer_id: str
    code_digest: str
    device_name: str
    device_type: str
    surfaces: frozenset[str]
    mode: str
    created_at: float
    locally_approved: bool


@dataclass
class MeshDevice:
    node_id: str
    instance_id: str
    display_name: str
    device_type: str
    execution_kind: str
    surfaces: frozenset[str]
    mode: str
    token_digest: str
    joined_at: float
    last_seen_at: float
    expires_at: float | None
    revoked: bool = False


class IrisDeviceMesh:
    """Cadastro + selecao de nos: transporte e instalacao ficam fora deste core.

    offer_device deve ser usado apenas por um agente instalado legalmente no
    dispositivo com comprovacao real de consentimento na camada de SO/UI.
    O argumento locally_approved nao substitui essa comprovacao.
    A API publica nao expoe offer_device/approve_offer neste incremento.
    """

    def __init__(
        self, authority: IrisInstanceAuthority,
        *, clock: Callable[[], float] = time.time,
    ) -> None:
        self.authority = authority
        self.clock = clock
        self._lock = threading.RLock()
        self._offers: dict[str, DeviceOffer] = {}
        self._devices: dict[str, MeshDevice] = {}

    @staticmethod
    def _digest(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _execution_kind(kind: str) -> str:
        if kind in _NATIVE:
            return "native_agent"
        if kind in _UI_ONLY:
            return "display_client"
        return "gateway_adapter"

    @staticmethod
    def _allowed_surfaces(kind: str, surfaces: frozenset[str]) -> bool:
        if not surfaces or not surfaces <= _SURFACES:
            return False
        if kind in _BRIDGE and not surfaces <= _SAFE_BRIDGE:
            return False
        if kind in _UI_ONLY and not surfaces <= {
            "presence.display", "audio.output", "media.read",
        }:
            return False
        return True

    def offer_device(
        self,
        *,
        device_name: str,
        device_type: str,
        surfaces: frozenset[str] | set[str],
        mode: str = "integrated",
        locally_approved: bool,
    ) -> dict[str, str]:
        """Cria um desafio de cinco minutos apresentado NO dispositivo.

        O futuro instalador verificara o usuario local antes de chamar isto.
        A visita so e admitida por pedido explicito.
        """
        with self._lock:
            if locally_approved is not True:
                raise PermissionError("Pareamento exige aprovacao local do proprietario.")
            if device_type not in _DEVICE_TYPES:
                raise ValueError("Tipo de dispositivo nao suportado.")
            if mode not in {"integrated", "visit"}:
                raise ValueError("Modo de conexao invalido.")
            if not isinstance(device_name, str) or not 1 <= len(device_name.strip()) <= NAME_MAX:
                raise ValueError("Nome do dispositivo invalido.")
            offered = frozenset(surfaces)
            if not self._allowed_surfaces(device_type, offered):
                raise PermissionError("Capacidade nao suportada neste tipo de dispositivo.")
            offer_id = "iris-offer-" + secrets.token_hex(16)
            code = secrets.token_urlsafe(16)
            self._offers[offer_id] = DeviceOffer(
                offer_id=offer_id, code_digest=self._digest(code),
                device_name=device_name.strip(), device_type=device_type,
                surfaces=offered, mode=mode, created_at=self.clock(),
                locally_approved=True,
            )
            return {"offer_id": offer_id, "verification_code": code}

    def approve_offer(
        self,
        instance_id: str,
        instance_token: str,
        *,
        offer_id: str,
        verification_code: str,
        visit_seconds: int = 1800,
    ) -> dict[str, str]:
        """A identidade dona da Iris confirma o codigo mostrado no aparelho."""
        with self._lock:
            self.authority.require(instance_id, instance_token, "device.local")
            offer = self._offers.get(offer_id)
            if not offer or self.clock() - offer.created_at >= PAIR_TTL_SECONDS:
                self._offers.pop(offer_id, None)
                raise PermissionError("Desafio de pareamento invalido ou expirado.")
            # Desafio de uso unico, inclusive em caso de codigo errado.
            self._offers.pop(offer_id)
            if not isinstance(verification_code, str) or not hmac.compare_digest(
                self._digest(verification_code), offer.code_digest
            ):
                raise PermissionError("Codigo de pareamento incorreto.")
            if offer.mode == "visit" and (
                type(visit_seconds) is not int or not 60 <= visit_seconds <= VISIT_MAX_SECONDS
            ):
                raise ValueError("Duracao de visita fora do limite.")
            existing = [device for device in self._devices.values()
                        if device.instance_id == instance_id and not device.revoked
                        and self._is_alive(device)]
            if len(existing) >= MAX_DEVICES_PER_INSTANCE:
                raise PermissionError("Limite de dispositivos por instancia atingido.")
            node_id = "iris-node-" + secrets.token_hex(16)
            node_token = secrets.token_urlsafe(32)
            now = self.clock()
            self._devices[node_id] = MeshDevice(
                node_id=node_id, instance_id=instance_id,
                display_name=offer.device_name, device_type=offer.device_type,
                execution_kind=self._execution_kind(offer.device_type),
                surfaces=offer.surfaces, mode=offer.mode,
                token_digest=self._digest(node_token),
                joined_at=now, last_seen_at=now,
                expires_at=now + visit_seconds if offer.mode == "visit" else None,
            )
            return {"node_id": node_id, "node_token": node_token, "mode": offer.mode}

    def _is_alive(self, device: MeshDevice) -> bool:
        if device.revoked or (device.expires_at is not None and self.clock() >= device.expires_at):
            return False
        if not self.authority.is_active_internal(device.instance_id):
            return False
        return self.clock() - device.last_seen_at <= HEARTBEAT_TTL_SECONDS

    def heartbeat(self, node_id: str, node_token: str) -> None:
        """Apenas o token individual deste aparelho pode renovar seu lease."""
        with self._lock:
            device = self._devices.get(node_id)
            if (not _DEVICE_ID_RE.fullmatch(str(node_id)) or device is None
                or not isinstance(node_token, str)
                or not hmac.compare_digest(self._digest(node_token), device.token_digest)
                or device.revoked or (
                    device.expires_at is not None and self.clock() >= device.expires_at
                ) or not self.authority.is_active_internal(device.instance_id)):
                raise PermissionError("No desconhecido, revogado ou expirado.")
            device.last_seen_at = self.clock()

    def disconnect(
        self, instance_id: str, instance_token: str, *, node_id: str,
    ) -> dict[str, bool]:
        """Revoga as credenciais. Limpeza de arquivos e feita pelo agente local."""
        with self._lock:
            self.authority.require(instance_id, instance_token, "device.local")
            node = self._devices.get(node_id)
            if not node or node.instance_id != instance_id:
                raise PermissionError("Dispositivo pertence a outra instancia.")
            node.revoked = True
            return {"disconnected": True, "local_cleanup_required": True}

    def _public_node(self, device: MeshDevice) -> dict[str, object]:
        return {
            "node_id": device.node_id,
            "name": device.display_name,
            "device_type": device.device_type,
            "execution_kind": device.execution_kind,
            "mode": device.mode,
            "connected": self._is_alive(device),
            "surfaces": sorted(device.surfaces),
        }

    def devices(self, instance_id: str, instance_token: str) -> list[dict[str, object]]:
        """Uma Iris so enxerga os aparelhos de sua propria instancia."""
        with self._lock:
            self.authority.require(instance_id, instance_token, "device.local")
            return [
                self._public_node(device) for device in self._devices.values()
                if device.instance_id == instance_id and not device.revoked
                and (device.expires_at is None or self.clock() < device.expires_at)
            ]

    def route(
        self, instance_id: str, instance_token: str, *, surface: str,
    ) -> dict[str, object]:
        """Escolhe o melhor no disponivel. Apenas planeja, nunca executa."""
        with self._lock:
            self.authority.require(instance_id, instance_token, "device.local")
            if surface not in _SURFACES:
                raise ValueError("Recurso de dispositivo desconhecido.")
            eligible = [
                d for d in self._devices.values()
                if d.instance_id == instance_id and surface in d.surfaces
                and self._is_alive(d)
            ]
            eligible.sort(key=lambda d: (
                d.execution_kind != "native_agent",
                d.mode != "integrated",
                d.node_id,
            ))
            if not eligible:
                return {"status": "unavailable", "surface": surface, "executed": False}
            return {
                "status": "routed", "surface": surface,
                "node_id": eligible[0].node_id,
                "execution_kind": eligible[0].execution_kind,
                "executed": False,
            }

    def continuity(
        self, instance_id: str, instance_token: str,
    ) -> dict[str, object]:
        """Saude da presenca logica, nao promessa de replicacao de memoria."""
        with self._lock:
            self.authority.require(instance_id, instance_token, "device.local")
            alive = [d for d in self._devices.values()
                     if d.instance_id == instance_id and self._is_alive(d)]
            runners = sorted(
                (d for d in alive if d.mode == "integrated"
                 and d.execution_kind == "native_agent"
                 and "compute.light" in d.surfaces),
                key=lambda d: d.node_id,
            )
            return {
                "logical_instance_id": instance_id,
                "active_nodes": len(alive),
                "coordinator_candidate": runners[0].node_id if runners else None,
                "alternate_nodes": max(0, len(runners) - 1),
                "control_plane_running": bool(runners),
                "durable_state_replication": False,
                "guaranteed_failover": False,
            }
