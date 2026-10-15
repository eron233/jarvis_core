"""Bootstrap explicito da malha local Iris, SEM habilitar o JARVIS legado.

Apenas processos de teste e hosts gerenciados pelo proprietario devem criar
o stack. Estado single-process. Credenciais precisam vir de um vault/secret
manager ou variaveis restritas do proprio sistema, NUNCA de repositório.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Mapping

from device.iris_mesh_persistence import PersistentIrisDeviceMesh
from device.iris_task_persistence import PersistentIrisTaskBroker
from device.iris_state_replication import IrisReplicaSource
from memory_system.iris_state_store import IrisEncryptedStateStore
from runtime.iris_dialogue_service import IrisDialogueService
from security.iris_instance_persistence import PersistentIrisInstanceAuthority


@dataclass
class IrisDistributedStack:
    authority: PersistentIrisInstanceAuthority
    mesh: PersistentIrisDeviceMesh
    store: IrisEncryptedStateStore
    broker: PersistentIrisTaskBroker
    replica_source: IrisReplicaSource
    dialogue: IrisDialogueService

    def close(self):
        self.store.close()

    def api_options(self):
        """Passe estes parametros para create_app(), sem remover acesso legado."""
        return {
            "iris_instance_authority": self.authority,
            "iris_device_mesh": self.mesh,
            "iris_state_store": self.store,
            "iris_task_broker": self.broker,
            "iris_replica_source": self.replica_source,
            "iris_dialogue_service": self.dialogue,
        }


def _key(env: Mapping[str, str], name: str) -> bytes:
    raw = env.get(name, "")
    if not isinstance(raw, str) or len(raw) != 64:
        raise ValueError(f"{name} precisa de chave hexadecimal de 32 bytes.")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"{name} invalida.") from exc
    if len(key) != 32:
        raise ValueError(f"{name} precisa de 32 bytes.")
    return key


def create_local_iris_stack(
    data_dir: Path, *, environ: Mapping[str, str] | None = None,
) -> IrisDistributedStack:
    """Construcao opt-in, recusando segredos ausentes, repetidos ou fracos."""
    env = environ if environ is not None else os.environ
    owner_secret = env.get("IRIS_OWNER_TOKEN", "")
    if not isinstance(owner_secret, str) or len(owner_secret) < 32:
        raise ValueError("IRIS_OWNER_TOKEN ausente ou fraco.")
    owner_secret = owner_secret.strip()
    if len(owner_secret) < 32:
        raise ValueError("IRIS_OWNER_TOKEN fraco.")
    keys = [
        _key(env, "IRIS_IDENTITY_KEY_HEX"),
        _key(env, "IRIS_MESH_KEY_HEX"),
        _key(env, "IRIS_STATE_KEY_HEX"),
        _key(env, "IRIS_BROKER_KEY_HEX"),
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("Chaves independentes exigidas por componente.")
    source_id = env.get("IRIS_SOURCE_ID", "")
    if not isinstance(source_id, str) or not source_id.startswith("iris-source-"):
        raise ValueError("IRIS_SOURCE_ID persistente nao configurado.")
    directory = Path(data_dir).resolve()
    if directory.exists() and directory.is_symlink():
        raise ValueError("Diretorio nao pode ser symlink.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        perms = stat.S_IMODE(directory.stat().st_mode)
        if perms & 0o077:
            raise PermissionError("Diretorio de estado Iris nao pode ser publico.")
    authority = PersistentIrisInstanceAuthority(
        owner_secret, directory / "identity.iris", storage_key=keys[0],
    )
    mesh = PersistentIrisDeviceMesh(
        authority, directory / "devices.iris", storage_key=keys[1],
    )
    store = IrisEncryptedStateStore(
        directory / "state.sqlite3", authority, root_key=keys[2],
    )
    try:
        broker = PersistentIrisTaskBroker(
            mesh, directory / "tasks.iris", storage_key=keys[3],
        )
        source = IrisReplicaSource(mesh, store, source_id=source_id)
        dialogue = IrisDialogueService(broker, store)
        return IrisDistributedStack(
            authority=authority, mesh=mesh, store=store, broker=broker,
            replica_source=source, dialogue=dialogue,
        )
    except BaseException:
        store.close()
        raise
