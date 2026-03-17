"""
JARVIS - Configuracao de Ambiente

Responsavel por:
- carregar variaveis de ambiente do sistema
- validar host, porta, seguranca e paths persistentes
- fornecer um resumo seguro do ambiente para runtime e API

Integracoes principais:
- runtime.server
- interface.api.app
- main
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
from typing import Any, Dict, Mapping

#
# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Parsing e validacao da configuracao de ambiente
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Valores legados inseguros mantidos apenas para deteccao e bloqueio.
DEFAULT_API_TOKEN = "jarvis-local-dev-token"
DEFAULT_TRUSTED_DEVICE_ID = "jarvis-dispositivo-local"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000
DEFAULT_LOOP_INTERVAL_SECONDS = 5.0
DEFAULT_IDLE_SLEEP_SECONDS = 10.0
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_ADMIN_PASSWORD = "alter ego"
DEFAULT_ACCESS_BOOTSTRAP_FILENAME = "jarvis_access_bootstrap.json"
DEFAULT_ADMIN_BOOTSTRAP_REPORT_FILENAME = "JARVIS_ADMIN_BOOTSTRAP_CREDENTIAL_PTBR.txt"
PBKDF2_ITERATIONS = 200_000
_WEAK_TOKEN_VALUES = {"", DEFAULT_API_TOKEN}
_WEAK_DEVICE_VALUES = {"", DEFAULT_TRUSTED_DEVICE_ID}
_WEAK_ADMIN_PASSWORDS = {"", DEFAULT_ADMIN_PASSWORD}
_DEVICE_ID_PATTERN = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class JarvisAccessBootstrap:
    """Material efetivo de acesso usado por runtime, API, cliente e launchers."""

    token: str
    token_source: str
    trusted_device_id: str
    trusted_device_source: str
    admin_password_hash: str
    admin_password_salt: str
    admin_password_iterations: int
    admin_password_source: str
    credentials_path: Path
    admin_bootstrap_report_path: Path
    admin_bootstrap_pending_rotation: bool


def _parse_bool(value: str | None, default: bool) -> bool:
    """
    Converte uma string de ambiente para booleano.

    Parametros:
    - value: valor textual recebido do ambiente.
    - default: valor padrao quando nada foi informado.

    Retorno:
    - booleano convertido.

    Efeitos no sistema:
    - nenhum; utilitario de normalizacao de configuracao.
    """

    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "sim", "yes", "on"}:
        return True
    if normalized in {"0", "false", "nao", "no", "off"}:
        return False
    raise ValueError(f"Valor booleano invalido: {value}")


def _parse_int(value: str | None, default: int, field_name: str) -> int:
    """
    Converte um valor textual para inteiro validado.

    Parametros:
    - value: valor bruto recebido do ambiente.
    - default: padrao aplicado quando o campo nao existe.
    - field_name: nome do campo para mensagens de erro.

    Retorno:
    - inteiro validado.

    Efeitos no sistema:
    - nenhum; protege a configuracao contra tipos invalidos.
    """

    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"O campo {field_name} deve ser um numero inteiro.") from exc


def _parse_float(value: str | None, default: float, field_name: str) -> float:
    """
    Converte um valor textual para decimal validado.

    Parametros:
    - value: valor bruto recebido do ambiente.
    - default: padrao aplicado quando o campo nao existe.
    - field_name: nome do campo para mensagens de erro.

    Retorno:
    - decimal validado.

    Efeitos no sistema:
    - nenhum; protege intervalos do loop e temporizadores.
    """

    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"O campo {field_name} deve ser um numero decimal.") from exc


@dataclass
class JarvisEnvironmentConfig:
    """Configuracao central usada para subir o JARVIS fora do ambiente local."""

    env: str = "development"
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    loop_interval_seconds: float = DEFAULT_LOOP_INTERVAL_SECONDS
    idle_sleep_seconds: float = DEFAULT_IDLE_SLEEP_SECONDS
    log_level: str = DEFAULT_LOG_LEVEL
    enable_runtime_loop: bool = True
    enable_dashboard: bool = True
    data_dir: Path = PROJECT_ROOT / "data"
    logs_dir: Path = PROJECT_ROOT / "logs"
    reports_dir: Path = PROJECT_ROOT / "reports"
    token: str = DEFAULT_API_TOKEN
    trusted_device_id: str = DEFAULT_TRUSTED_DEVICE_ID
    access_bootstrap_path: Path | None = None
    admin_bootstrap_report_path: Path | None = None
    queue_storage_path: Path | None = None
    semantic_storage_path: Path | None = None
    procedural_storage_path: Path | None = None
    goals_storage_path: Path | None = None
    device_registry_path: Path | None = None
    cognitive_evolution_storage_path: Path | None = None
    audit_storage_path: Path | None = None
    self_defense_report_path: Path | None = None
    _access_bootstrap: JarvisAccessBootstrap | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """
        Normaliza os paths configurados logo apos a construcao do dataclass.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - garante que diretorios e arquivos persistentes estejam padronizados como `Path`.
        """

        self.data_dir = Path(self.data_dir)
        self.logs_dir = Path(self.logs_dir)
        self.reports_dir = Path(self.reports_dir)

        if self.access_bootstrap_path is None:
            self.access_bootstrap_path = self.data_dir / DEFAULT_ACCESS_BOOTSTRAP_FILENAME
        else:
            self.access_bootstrap_path = Path(self.access_bootstrap_path)

        if self.admin_bootstrap_report_path is None:
            self.admin_bootstrap_report_path = self.reports_dir / DEFAULT_ADMIN_BOOTSTRAP_REPORT_FILENAME
        else:
            self.admin_bootstrap_report_path = Path(self.admin_bootstrap_report_path)

        if self.queue_storage_path is None:
            self.queue_storage_path = self.data_dir / "task_queue_store.json"
        else:
            self.queue_storage_path = Path(self.queue_storage_path)

        if self.semantic_storage_path is None:
            self.semantic_storage_path = self.data_dir / "semantic_memory_store.json"
        else:
            self.semantic_storage_path = Path(self.semantic_storage_path)

        if self.procedural_storage_path is None:
            self.procedural_storage_path = self.data_dir / "procedural_memory_store.json"
        else:
            self.procedural_storage_path = Path(self.procedural_storage_path)

        if self.goals_storage_path is None:
            self.goals_storage_path = self.data_dir / "goals.json"
        else:
            self.goals_storage_path = Path(self.goals_storage_path)

        if self.device_registry_path is None:
            self.device_registry_path = self.data_dir / "device_registry.json"
        else:
            self.device_registry_path = Path(self.device_registry_path)

        if self.cognitive_evolution_storage_path is None:
            self.cognitive_evolution_storage_path = self.data_dir / "cognitive_evolution_history.json"
        else:
            self.cognitive_evolution_storage_path = Path(self.cognitive_evolution_storage_path)

        if self.audit_storage_path is None:
            self.audit_storage_path = self.data_dir / "runtime_audit_store.json"
        else:
            self.audit_storage_path = Path(self.audit_storage_path)

        if self.self_defense_report_path is None:
            self.self_defense_report_path = self.reports_dir / "self_defense_latest.json"
        else:
            self.self_defense_report_path = Path(self.self_defense_report_path)

        self.env = self.env.strip().lower() or "development"
        self.log_level = self.log_level.strip().upper() or DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        project_root: Path | None = None,
    ) -> "JarvisEnvironmentConfig":
        """Constroi a configuracao do ambiente a partir das variaveis de ambiente."""

        env_map = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)
        data_dir = Path(env_map.get("JARVIS_DATA_DIR", root / "data"))
        logs_dir = Path(env_map.get("JARVIS_LOGS_DIR", root / "logs"))
        reports_dir = Path(env_map.get("JARVIS_REPORTS_DIR", root / "reports"))

        config = cls(
            env=str(env_map.get("JARVIS_ENV", "development")),
            api_host=str(env_map.get("JARVIS_API_HOST", DEFAULT_API_HOST)),
            api_port=_parse_int(env_map.get("JARVIS_API_PORT"), DEFAULT_API_PORT, "JARVIS_API_PORT"),
            loop_interval_seconds=_parse_float(
                env_map.get("JARVIS_LOOP_INTERVAL_SECONDS"),
                DEFAULT_LOOP_INTERVAL_SECONDS,
                "JARVIS_LOOP_INTERVAL_SECONDS",
            ),
            idle_sleep_seconds=_parse_float(
                env_map.get("JARVIS_IDLE_SLEEP_SECONDS"),
                DEFAULT_IDLE_SLEEP_SECONDS,
                "JARVIS_IDLE_SLEEP_SECONDS",
            ),
            log_level=str(env_map.get("JARVIS_LOG_LEVEL", DEFAULT_LOG_LEVEL)),
            enable_runtime_loop=_parse_bool(
                env_map.get("JARVIS_ENABLE_RUNTIME_LOOP"),
                True,
            ),
            enable_dashboard=_parse_bool(
                env_map.get("JARVIS_ENABLE_DASHBOARD"),
                True,
            ),
            data_dir=data_dir,
            logs_dir=logs_dir,
            reports_dir=reports_dir,
            token=str(env_map.get("JARVIS_TOKEN", "")).strip(),
            trusted_device_id=str(env_map.get("JARVIS_TRUSTED_DEVICE_ID", "")).strip(),
            access_bootstrap_path=env_map.get("JARVIS_ACCESS_BOOTSTRAP_PATH"),
            admin_bootstrap_report_path=env_map.get("JARVIS_ADMIN_BOOTSTRAP_REPORT_PATH"),
            queue_storage_path=env_map.get("JARVIS_QUEUE_STORAGE_PATH"),
            semantic_storage_path=env_map.get("JARVIS_SEMANTIC_STORAGE_PATH"),
            procedural_storage_path=env_map.get("JARVIS_PROCEDURAL_STORAGE_PATH"),
            goals_storage_path=env_map.get("JARVIS_GOALS_STORAGE_PATH"),
            device_registry_path=env_map.get("JARVIS_DEVICE_REGISTRY_PATH"),
            cognitive_evolution_storage_path=env_map.get("JARVIS_COGNITIVE_EVOLUTION_STORAGE_PATH"),
            audit_storage_path=env_map.get("JARVIS_AUDIT_STORAGE_PATH"),
            self_defense_report_path=env_map.get("JARVIS_SELF_DEFENSE_REPORT_PATH"),
        )
        config._access_bootstrap = resolve_access_bootstrap(
            environ=env_map,
            project_root=root,
            data_dir=config.data_dir,
            reports_dir=config.reports_dir,
            credentials_path=config.access_bootstrap_path,
            admin_bootstrap_report_path=config.admin_bootstrap_report_path,
        )
        config.token = config._access_bootstrap.token
        config.trusted_device_id = config._access_bootstrap.trusted_device_id
        config.validate()
        return config

    def validate(self) -> None:
        """Valida os campos essenciais para deploy seguro."""

        errors: list[str] = []
        access_bootstrap = self.get_access_bootstrap()

        if _is_weak_token(self.token):
            self.token = access_bootstrap.token
        if _is_weak_device_id(self.trusted_device_id):
            self.trusted_device_id = access_bootstrap.trusted_device_id

        if not self.api_host.strip():
            errors.append("JARVIS_API_HOST nao pode ficar vazio.")
        if not 1 <= self.api_port <= 65535:
            errors.append("JARVIS_API_PORT deve ficar entre 1 e 65535.")
        if self.loop_interval_seconds < 0:
            errors.append("JARVIS_LOOP_INTERVAL_SECONDS nao pode ser negativo.")
        if self.idle_sleep_seconds < 0:
            errors.append("JARVIS_IDLE_SLEEP_SECONDS nao pode ser negativo.")
        if _is_weak_token(self.token):
            errors.append("O token da API permanece em valor fraco ou ausente.")
        if _is_weak_device_id(self.trusted_device_id):
            errors.append("O device id confiavel principal permanece em valor fraco ou ausente.")
        if not access_bootstrap.admin_password_hash or not access_bootstrap.admin_password_salt:
            errors.append("A credencial administrativa segura nao foi inicializada corretamente.")

        if errors:
            formatted_errors = "\n".join(f"- {error}" for error in errors)
            raise ValueError(f"Configuracao de ambiente invalida para o JARVIS:\n{formatted_errors}")

    def ensure_directories(self) -> None:
        """Cria os diretorios necessarios para persistencia e observabilidade."""

        directories = {
            self.data_dir,
            self.logs_dir,
            self.reports_dir,
            self.access_bootstrap_path.parent,
            self.admin_bootstrap_report_path.parent,
            self.queue_storage_path.parent,
            self.semantic_storage_path.parent,
            self.procedural_storage_path.parent,
            self.goals_storage_path.parent,
            self.device_registry_path.parent,
            self.cognitive_evolution_storage_path.parent,
            self.audit_storage_path.parent,
            self.self_defense_report_path.parent,
        }
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_access_bootstrap(self) -> JarvisAccessBootstrap:
        """Retorna as credenciais efetivas do ambiente, bootstrapando quando necessario."""

        if self._access_bootstrap is None:
            self._access_bootstrap = resolve_access_bootstrap(
                project_root=PROJECT_ROOT,
                data_dir=self.data_dir,
                reports_dir=self.reports_dir,
                credentials_path=self.access_bootstrap_path,
                admin_bootstrap_report_path=self.admin_bootstrap_report_path,
            )
            self.token = self._access_bootstrap.token
            self.trusted_device_id = self._access_bootstrap.trusted_device_id
        return self._access_bootstrap

    def build_environment_report(self) -> Dict[str, Any]:
        """Retorna um resumo seguro do ambiente atual."""

        access_bootstrap = self.get_access_bootstrap()
        return {
            "ambiente": self.env,
            "host_api": self.api_host,
            "porta_api": self.api_port,
            "loop_runtime_ativo": self.enable_runtime_loop,
            "painel_ativo": self.enable_dashboard,
            "nivel_log": self.log_level,
            "paths_persistentes": {
                "data_dir": str(self.data_dir),
                "logs_dir": str(self.logs_dir),
                "reports_dir": str(self.reports_dir),
                "access_bootstrap_path": str(self.access_bootstrap_path),
                "admin_bootstrap_report_path": str(self.admin_bootstrap_report_path),
                "queue_storage_path": str(self.queue_storage_path),
                "semantic_storage_path": str(self.semantic_storage_path),
                "procedural_storage_path": str(self.procedural_storage_path),
                "goals_storage_path": str(self.goals_storage_path),
                "device_registry_path": str(self.device_registry_path),
                "cognitive_evolution_storage_path": str(self.cognitive_evolution_storage_path),
                "audit_storage_path": str(self.audit_storage_path),
                "self_defense_report_path": str(self.self_defense_report_path),
            },
            "autenticacao_configurada": {
                "token_configurado": not _is_weak_token(self.token),
                "token_source": access_bootstrap.token_source,
                "dispositivo_confiavel_configurado": not _is_weak_device_id(self.trusted_device_id),
                "dispositivo_confiavel_source": access_bootstrap.trusted_device_source,
                "senha_admin_configurada": bool(access_bootstrap.admin_password_hash),
                "senha_admin_source": access_bootstrap.admin_password_source,
                "rotacao_admin_recomendada": access_bootstrap.admin_bootstrap_pending_rotation,
            },
        }

    @property
    def log_file_path(self) -> Path:
        """
        Retorna o caminho padrao do arquivo de log principal.

        Parametros:
        - nenhum.

        Retorno:
        - `Path` do log do servidor.

        Efeitos no sistema:
        - nenhum; facilita a configuracao de logging.
        """

        return self.logs_dir / "jarvis.log"

    @property
    def startup_report_path(self) -> Path:
        """
        Retorna o caminho do relatorio de startup.

        Parametros:
        - nenhum.

        Retorno:
        - `Path` do resumo de ambiente gerado na inicializacao.

        Efeitos no sistema:
        - nenhum; padroniza observabilidade de deploy.
        """

        return self.reports_dir / "environment_report.json"

    @property
    def shutdown_report_path(self) -> Path:
        """
        Retorna o caminho do relatorio de encerramento.

        Parametros:
        - nenhum.

        Retorno:
        - `Path` do resumo final de desligamento.

        Efeitos no sistema:
        - nenhum; padroniza persistencia do estado final.
        """

        return self.reports_dir / "shutdown_report.json"


def resolve_access_bootstrap(
    environ: Mapping[str, str] | None = None,
    *,
    project_root: Path | None = None,
    data_dir: Path | None = None,
    reports_dir: Path | None = None,
    credentials_path: Path | None = None,
    admin_bootstrap_report_path: Path | None = None,
) -> JarvisAccessBootstrap:
    """Resolve token, device confiavel e senha admin segura sem defaults previsiveis."""

    env_map = dict(environ or os.environ)
    root = Path(project_root or PROJECT_ROOT)
    effective_data_dir = Path(data_dir or env_map.get("JARVIS_DATA_DIR", root / "data"))
    effective_reports_dir = Path(reports_dir or env_map.get("JARVIS_REPORTS_DIR", root / "reports"))
    effective_credentials_path = Path(
        credentials_path or env_map.get("JARVIS_ACCESS_BOOTSTRAP_PATH", effective_data_dir / DEFAULT_ACCESS_BOOTSTRAP_FILENAME)
    )
    effective_admin_report_path = Path(
        admin_bootstrap_report_path
        or env_map.get(
            "JARVIS_ADMIN_BOOTSTRAP_REPORT_PATH",
            effective_reports_dir / DEFAULT_ADMIN_BOOTSTRAP_REPORT_FILENAME,
        )
    )

    effective_data_dir.mkdir(parents=True, exist_ok=True)
    effective_reports_dir.mkdir(parents=True, exist_ok=True)

    bootstrap_payload = _load_json_payload(effective_credentials_path)

    env_token = str(env_map.get("JARVIS_TOKEN", "")).strip()
    env_device_id = str(env_map.get("JARVIS_TRUSTED_DEVICE_ID", "")).strip()
    env_admin_password = env_map.get("JARVIS_ADMIN_PASSWORD")

    if env_token and _is_weak_token(env_token):
        raise ValueError(
            "JARVIS_TOKEN foi definido com valor fraco. Configure um token proprio ou remova a variavel para bootstrap seguro."
        )
    if env_device_id and _is_weak_device_id(env_device_id):
        raise ValueError(
            "JARVIS_TRUSTED_DEVICE_ID foi definido com valor fraco. Configure um identificador proprio ou remova a variavel para bootstrap seguro."
        )
    if env_admin_password is not None and not _is_strong_admin_password(env_admin_password):
        raise ValueError(
            "JARVIS_ADMIN_PASSWORD precisa ter pelo menos 12 caracteres e nao pode reutilizar a credencial fraca legada."
        )

    resolved_token = env_token or str(bootstrap_payload.get("api_token", "")).strip()
    resolved_token_source = "environment" if env_token else str(bootstrap_payload.get("token_source", ""))
    if _is_weak_token(resolved_token):
        resolved_token = _generate_secure_token()
        resolved_token_source = "bootstrap_file"

    resolved_device_id = env_device_id or str(bootstrap_payload.get("trusted_device_id", "")).strip()
    resolved_device_source = "environment" if env_device_id else str(
        bootstrap_payload.get("trusted_device_source", "")
    )
    if _is_weak_device_id(resolved_device_id):
        resolved_device_id = _generate_secure_device_id()
        resolved_device_source = "bootstrap_file"

    generated_admin_password: str | None = None
    admin_hash = str(bootstrap_payload.get("admin_password_hash", "")).strip()
    admin_salt = str(bootstrap_payload.get("admin_password_salt", "")).strip()
    admin_iterations = int(bootstrap_payload.get("admin_password_iterations", PBKDF2_ITERATIONS))
    admin_source = str(bootstrap_payload.get("admin_password_source", "")).strip() or "bootstrap_file"
    admin_pending_rotation = bool(bootstrap_payload.get("admin_bootstrap_pending_rotation", True))

    if env_admin_password is not None:
        admin_hash, admin_salt = derive_password_hash(env_admin_password)
        admin_iterations = PBKDF2_ITERATIONS
        admin_source = "environment"
        admin_pending_rotation = False
    elif not admin_hash or not admin_salt:
        generated_admin_password = _generate_secure_admin_password()
        admin_hash, admin_salt = derive_password_hash(generated_admin_password)
        admin_iterations = PBKDF2_ITERATIONS
        admin_source = "bootstrap_file"
        admin_pending_rotation = True

    persisted_payload = {
        "version": "1.0",
        "updated_at": _utc_now(),
        "api_token": resolved_token,
        "token_source": resolved_token_source or "bootstrap_file",
        "trusted_device_id": resolved_device_id,
        "trusted_device_source": resolved_device_source or "bootstrap_file",
        "admin_password_hash": admin_hash,
        "admin_password_salt": admin_salt,
        "admin_password_iterations": admin_iterations,
        "admin_password_source": admin_source,
        "admin_bootstrap_pending_rotation": admin_pending_rotation,
    }
    _write_json_atomic(effective_credentials_path, persisted_payload)
    _write_admin_bootstrap_report(
        report_path=effective_admin_report_path,
        access_payload=persisted_payload,
        generated_admin_password=generated_admin_password,
    )

    return JarvisAccessBootstrap(
        token=resolved_token,
        token_source=persisted_payload["token_source"],
        trusted_device_id=resolved_device_id,
        trusted_device_source=persisted_payload["trusted_device_source"],
        admin_password_hash=admin_hash,
        admin_password_salt=admin_salt,
        admin_password_iterations=admin_iterations,
        admin_password_source=admin_source,
        credentials_path=effective_credentials_path,
        admin_bootstrap_report_path=effective_admin_report_path,
        admin_bootstrap_pending_rotation=admin_pending_rotation,
    )


def derive_password_hash(
    password: str,
    *,
    salt_hex: str | None = None,
    iterations: int = PBKDF2_ITERATIONS,
) -> tuple[str, str]:
    """Deriva hash PBKDF2-HMAC-SHA256 para senha administrativa."""

    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt,
        iterations,
    )
    return derived.hex(), salt.hex()


def verify_password_hash(
    password: str,
    *,
    password_hash: str,
    password_salt: str,
    iterations: int = PBKDF2_ITERATIONS,
) -> bool:
    """Compara uma senha informada com o hash PBKDF2 persistido."""

    if not password_hash or not password_salt:
        return False
    derived_hash, _ = derive_password_hash(
        password,
        salt_hex=password_salt,
        iterations=iterations,
    )
    return hmac.compare_digest(derived_hash, password_hash)


def _load_json_payload(path: Path) -> Dict[str, Any]:
    """Carrega um JSON de bootstrap, isolando arquivos corrompidos."""

    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup_path = path.with_name(f"{path.stem}.corrompido-{_utc_now_for_filename()}{path.suffix}")
        os.replace(path, backup_path)
        return {}

    return payload if isinstance(payload, dict) else {}


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    """Grava JSON com replace atomico para evitar corrupcao parcial."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, path)


def _write_admin_bootstrap_report(
    *,
    report_path: Path,
    access_payload: Dict[str, Any],
    generated_admin_password: str | None,
) -> None:
    """Atualiza o relatorio textual de bootstrap seguro de acesso."""

    report_path.parent.mkdir(parents=True, exist_ok=True)

    if generated_admin_password is not None:
        content = "\n".join(
            [
                "JARVIS - CREDENCIAIS BOOTSTRAP SEGURAS",
                "",
                f"Gerado em: {_utc_now()}",
                "",
                "O sistema criou credenciais seguras por nao encontrar segredos validos no ambiente.",
                "Guarde estas informacoes em local seguro e rotacione-as assim que possivel.",
                "",
                f"Token da API: {access_payload['api_token']}",
                f"Dispositivo confiavel principal: {access_payload['trusted_device_id']}",
                f"Senha administrativa inicial: {generated_admin_password}",
                "",
                "Recomendacao:",
                "- defina JARVIS_TOKEN, JARVIS_TRUSTED_DEVICE_ID e JARVIS_ADMIN_PASSWORD no ambiente alvo",
                "- apos a rotacao, reinicie o Jarvis para persistir o novo conjunto",
            ]
        )
    else:
        content = "\n".join(
            [
                "JARVIS - CREDENCIAIS SEGURAS CONFIGURADAS",
                "",
                f"Atualizado em: {_utc_now()}",
                "",
                "O acesso administrativo nao depende mais da credencial fraca legada.",
                "As credenciais efetivas atuais ja estao resolvidas por ambiente e/ou bootstrap persistido.",
                "",
                f"Token da API em uso: {access_payload['api_token']}",
                f"Dispositivo confiavel principal em uso: {access_payload['trusted_device_id']}",
                f"Fonte da senha admin: {access_payload['admin_password_source']}",
                "",
                "A senha administrativa em texto puro nao e mantida neste arquivo.",
            ]
        )

    report_path.write_text(content, encoding="utf-8")


def _generate_secure_token() -> str:
    """Gera um token de API suficientemente forte para bootstrap local."""

    return f"jarvis-{secrets.token_urlsafe(24)}"


def _generate_secure_device_id() -> str:
    """Gera um identificador confiavel inicial baseado no host atual."""

    hostname = _DEVICE_ID_PATTERN.sub("-", socket.gethostname().strip().lower()).strip("-")
    if not hostname:
        hostname = secrets.token_hex(4)
    return f"jarvis-{hostname}-principal"


def _generate_secure_admin_password() -> str:
    """Gera a senha administrativa inicial segura para primeiro uso."""

    return secrets.token_urlsafe(18)


def _is_weak_token(value: str | None) -> bool:
    """Informa se o token permanece em estado ausente ou legadamente inseguro."""

    return str(value or "").strip() in _WEAK_TOKEN_VALUES


def _is_weak_device_id(value: str | None) -> bool:
    """Informa se o device id permanece em estado ausente ou legadamente inseguro."""

    return str(value or "").strip() in _WEAK_DEVICE_VALUES


def _is_strong_admin_password(value: str | None) -> bool:
    """Valida a senha administrativa minima exigida para operacao segura."""

    normalized = str(value or "")
    return len(normalized) >= 12 and normalized.strip().lower() not in _WEAK_ADMIN_PASSWORDS


def _utc_now() -> str:
    """Retorna timestamp UTC atual em ISO 8601."""

    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _utc_now_for_filename() -> str:
    """Retorna timestamp UTC compacto apropriado para nomes de arquivo."""

    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
