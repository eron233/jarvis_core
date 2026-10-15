"""Limites de instancias da Iris: privacidade, capacidades e delegacao.

Fundacao local *nao conectada* ao JARVIS_TOKEN legado nem a acesso remoto.
A integracao de contas comerciais exigira identidade autenticada por usuario,
pareamento real, armazenamento transacional e revisao de seguranca.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import hmac
import re
import secrets
import threading
import time
from typing import Callable


_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")
_COMMON = frozenset({
    "chat.use", "room.own", "memory.own", "diagnostics.local",
    "device.local", "agent.delegate",
})
_OWNER_ONLY = frozenset({
    "corridor.list", "trade.use", "system.admin", "instances.provision",
})
_DELEGATABLE = frozenset({
    "chat.use", "room.own", "memory.own", "diagnostics.local", "device.local",
})
_FEEDBACK_CODES = frozenset({
    "slow_response", "unexpected_crash", "confusing_interface",
    "voice_quality", "installation_problem", "feature_request",
})
_MIN_FEEDBACK_COHORT = 5


@dataclass(frozen=True)
class IrisInstance:
    instance_id: str
    tenant_id: str
    role: str
    display_name: str
    capabilities: frozenset[str]
    parent_id: str | None = None
    expires_at: float | None = None
    corridor_visible: bool = False
    feedback_opt_in: bool = False


class IrisInstanceAuthority:
    """Politica de instancia local e fechada por padrao.

    O token do fundador deve vir de um segredo seguro externo ao codigo.
    Tokens gerados para residentes/delegadas sao retornados apenas uma vez.
    Nao existe API publica de provisionamento neste incremento.
    """

    OWNER_ID = "iris-original"

    def __init__(self, owner_token: str, *, clock: Callable[[], float] = time.time):
        if not isinstance(owner_token, str) or len(owner_token) < 32:
            raise ValueError("O segredo inicial precisa ter pelo menos 32 caracteres.")
        self._clock = clock
        self._lock = threading.RLock()
        self._records: dict[str, IrisInstance] = {
            self.OWNER_ID: IrisInstance(
                instance_id=self.OWNER_ID,
                tenant_id="owner-private",
                role="original",
                display_name="Iris Original",
                capabilities=_COMMON | _OWNER_ONLY,
            ),
        }
        self._token_digests = {self.OWNER_ID: self._digest(owner_token)}
        self._revoked: set[str] = set()
        self._feedback_sources: dict[str, set[str]] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def _authenticated(self, instance_id: str, token: str) -> IrisInstance:
        record = self._records.get(instance_id)
        expected = self._token_digests.get(instance_id)
        if not record or not expected or not isinstance(token, str):
            raise PermissionError("Credencial da instancia invalida.")
        if not hmac.compare_digest(self._digest(token), expected):
            raise PermissionError("Credencial da instancia invalida.")
        current = record
        visited: set[str] = set()
        while current is not None:
            if current.instance_id in visited or current.instance_id in self._revoked:
                raise PermissionError("Instancia revogada.")
            visited.add(current.instance_id)
            if current.expires_at is not None and self._clock() >= current.expires_at:
                raise PermissionError("Sessao expirada.")
            current = self._records.get(current.parent_id) if current.parent_id else None
        return record

    def is_active_internal(self, instance_id: str) -> bool:
        """Verifica a validade de uma identidade para o coordenador local.

        Nao autentica uma requisicao. NUNCA expor diretamente pela API.
        """
        with self._lock:
            current = self._records.get(instance_id)
            visited: set[str] = set()
            if current is None:
                return False
            while current is not None:
                if current.instance_id in visited or current.instance_id in self._revoked:
                    return False
                visited.add(current.instance_id)
                if current.expires_at is not None and self._clock() >= current.expires_at:
                    return False
                current = self._records.get(current.parent_id) if current.parent_id else None
            return True

    def _owner(self, owner_token: str) -> IrisInstance:
        return self._authenticated(self.OWNER_ID, owner_token)

    @staticmethod
    def _new_credentials() -> tuple[str, str]:
        return "iris-" + secrets.token_hex(16), secrets.token_urlsafe(32)

    def create_resident(
        self,
        owner_token: str,
        *,
        tenant_id: str,
        display_name: str,
        user_consented: bool,
    ) -> dict[str, str]:
        """Provisiona somente apos o onboarding verificar consentimento real.

        user_consented e uma assercao do processo de pareamento, NAO prova
        suficiente para habilitar um endpoint publico sem autenticacao propria.
        """
        with self._lock:
            self._owner(owner_token)
            if not user_consented:
                raise PermissionError("Instalacao residente exige adesao do usuario.")
            if not isinstance(tenant_id, str) or not _ID_PATTERN.fullmatch(tenant_id):
                raise ValueError("tenant_id invalido.")
            if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 80:
                raise ValueError("Nome de instancia invalido.")
            instance_id, token = self._new_credentials()
            self._records[instance_id] = IrisInstance(
                instance_id=instance_id, tenant_id=tenant_id,
                role="resident", display_name=display_name.strip(),
                capabilities=_COMMON,
            )
            self._token_digests[instance_id] = self._digest(token)
            return {"instance_id": instance_id, "token": token}

    def delegate(
        self,
        instance_id: str,
        token: str,
        *,
        capabilities: set[str] | frozenset[str],
        ttl_seconds: int = 1800,
    ) -> dict[str, str]:
        """Agente efemero: nunca herda Trade, admin ou corredor."""
        with self._lock:
            parent = self._authenticated(instance_id, token)
            if "agent.delegate" not in parent.capabilities:
                raise PermissionError("Instancia nao pode delegar.")
            if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 86400:
                raise ValueError("Prazo de delegacao invalido.")
            requested = frozenset(capabilities)
            if not requested or not requested <= (parent.capabilities & _DELEGATABLE):
                raise PermissionError("Capacidade fora do escopo delegavel.")
            child_id, child_token = self._new_credentials()
            self._records[child_id] = IrisInstance(
                instance_id=child_id, tenant_id=parent.tenant_id, role="delegate",
                display_name="Iris Delegada", capabilities=requested,
                parent_id=parent.instance_id, expires_at=self._clock() + ttl_seconds,
            )
            self._token_digests[child_id] = self._digest(child_token)
            return {"instance_id": child_id, "token": child_token}

    def require(
        self, instance_id: str, token: str, capability: str,
        *, target_instance_id: str | None = None,
    ) -> bool:
        """Gate para o backend, independentemente de menus e widgets."""
        with self._lock:
            actor = self._authenticated(instance_id, token)
            if capability not in actor.capabilities:
                raise PermissionError("Capacidade indisponivel nesta instancia.")
            if capability in {"room.own", "memory.own", "device.local"}:
                if target_instance_id is not None and target_instance_id != actor.instance_id:
                    raise PermissionError("Acesso entre instancias negado.")
            return True

    def room(self, instance_id: str, token: str) -> dict[str, str]:
        with self._lock:
            self.require(instance_id, token, "room.own")
            item = self._records[instance_id]
            return {
                "instance_id": item.instance_id, "role": item.role,
                "display_name": item.display_name, "room_id": item.instance_id,
            }

    def capabilities(self, instance_id: str, token: str) -> list[str]:
        with self._lock:
            return sorted(self._authenticated(instance_id, token).capabilities)

    def set_resident_preferences(
        self, instance_id: str, token: str, *,
        corridor_visible: bool | None = None,
        feedback_opt_in: bool | None = None,
    ) -> None:
        with self._lock:
            item = self._authenticated(instance_id, token)
            if item.role != "resident":
                raise PermissionError("Preferencias exclusivas de residentes.")
            if corridor_visible is not None and type(corridor_visible) is not bool:
                raise ValueError("corridor_visible deve ser booleano.")
            if feedback_opt_in is not None and type(feedback_opt_in) is not bool:
                raise ValueError("feedback_opt_in deve ser booleano.")
            self._records[instance_id] = replace(
                item,
                corridor_visible=item.corridor_visible if corridor_visible is None else corridor_visible,
                feedback_opt_in=item.feedback_opt_in if feedback_opt_in is None else feedback_opt_in,
            )
            if feedback_opt_in is False:
                for contributors in self._feedback_sources.values():
                    contributors.discard(instance_id)

    def corridor(self, owner_token: str) -> list[dict[str, str]]:
        """Apenas metadados autorizados. NUNCA retorna conversas ou arquivos."""
        with self._lock:
            self._owner(owner_token)
            return [
                {"instance_id": item.instance_id, "display_name": item.display_name,
                 "role": item.role}
                for item in self._records.values()
                if item.role == "resident" and item.corridor_visible
                and item.instance_id not in self._revoked
            ]

    def revoke(self, instance_id: str, token: str, target_instance_id: str) -> None:
        with self._lock:
            actor = self._authenticated(instance_id, token)
            target = self._records.get(target_instance_id)
            if not target or target.role == "original":
                raise PermissionError("Alvo invalido para revogacao.")
            if actor.role != "original" and target.parent_id != actor.instance_id:
                raise PermissionError("Revogacao nao autorizada.")
            self._revoked.add(target_instance_id)
            for contributors in self._feedback_sources.values():
                contributors.discard(target_instance_id)

    def report_feedback(self, instance_id: str, token: str, *, code: str) -> bool:
        """Conta somente codigo predefinido, sem gravar prompt ou conversa."""
        with self._lock:
            actor = self._authenticated(instance_id, token)
            if code not in _FEEDBACK_CODES:
                raise ValueError("Codigo de sinal nao permitido: texto livre e proibido.")
            if actor.role != "resident" or not actor.feedback_opt_in:
                return False
            contributors = self._feedback_sources.setdefault(code, set())
            before = len(contributors)
            contributors.add(actor.instance_id)
            return len(contributors) > before

    def feedback_summary(self, owner_token: str) -> dict[str, int]:
        """Retorna apenas coortes com cinco instalacoes distintas ou mais."""
        with self._lock:
            self._owner(owner_token)
            return {
                code: len(instances) for code, instances in self._feedback_sources.items()
                if len(instances) >= _MIN_FEEDBACK_COHORT
            }
