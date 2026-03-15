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

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, Mapping

#
# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Parsing e validacao da configuracao de ambiente
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_API_TOKEN = "jarvis-local-dev-token"
DEFAULT_TRUSTED_DEVICE_ID = "jarvis-dispositivo-local"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000
DEFAULT_LOOP_INTERVAL_SECONDS = 5.0
DEFAULT_IDLE_SLEEP_SECONDS = 10.0
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_ADMIN_PASSWORD = "alter ego"


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
    queue_storage_path: Path | None = None
    semantic_storage_path: Path | None = None
    procedural_storage_path: Path | None = None
    goals_storage_path: Path | None = None
    device_registry_path: Path | None = None
    cognitive_evolution_storage_path: Path | None = None
    audit_storage_path: Path | None = None

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
            token=str(env_map.get("JARVIS_TOKEN", DEFAULT_API_TOKEN)),
            trusted_device_id=str(
                env_map.get("JARVIS_TRUSTED_DEVICE_ID", DEFAULT_TRUSTED_DEVICE_ID)
            ),
            queue_storage_path=env_map.get("JARVIS_QUEUE_STORAGE_PATH"),
            semantic_storage_path=env_map.get("JARVIS_SEMANTIC_STORAGE_PATH"),
            procedural_storage_path=env_map.get("JARVIS_PROCEDURAL_STORAGE_PATH"),
            goals_storage_path=env_map.get("JARVIS_GOALS_STORAGE_PATH"),
            device_registry_path=env_map.get("JARVIS_DEVICE_REGISTRY_PATH"),
            cognitive_evolution_storage_path=env_map.get("JARVIS_COGNITIVE_EVOLUTION_STORAGE_PATH"),
            audit_storage_path=env_map.get("JARVIS_AUDIT_STORAGE_PATH"),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Valida os campos essenciais para deploy seguro."""

        errors: list[str] = []

        if not self.api_host.strip():
            errors.append("JARVIS_API_HOST nao pode ficar vazio.")
        if not 1 <= self.api_port <= 65535:
            errors.append("JARVIS_API_PORT deve ficar entre 1 e 65535.")
        if self.loop_interval_seconds < 0:
            errors.append("JARVIS_LOOP_INTERVAL_SECONDS nao pode ser negativo.")
        if self.idle_sleep_seconds < 0:
            errors.append("JARVIS_IDLE_SLEEP_SECONDS nao pode ser negativo.")
        if self.env in {"production", "prod"} and self.token == DEFAULT_API_TOKEN:
            errors.append("Defina JARVIS_TOKEN com um valor proprio antes de subir em producao.")
        if self.env in {"production", "prod"} and self.trusted_device_id == DEFAULT_TRUSTED_DEVICE_ID:
            errors.append(
                "Defina JARVIS_TRUSTED_DEVICE_ID com o identificador do dispositivo confiavel antes de subir em producao."
            )
        if self.env in {"production", "prod"} and str(os.environ.get("JARVIS_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)) == DEFAULT_ADMIN_PASSWORD:
            errors.append("Defina JARVIS_ADMIN_PASSWORD com um valor proprio antes de subir em producao.")

        if errors:
            formatted_errors = "\n".join(f"- {error}" for error in errors)
            raise ValueError(f"Configuracao de ambiente invalida para o JARVIS:\n{formatted_errors}")

    def ensure_directories(self) -> None:
        """Cria os diretorios necessarios para persistencia e observabilidade."""

        directories = {
            self.data_dir,
            self.logs_dir,
            self.reports_dir,
            self.queue_storage_path.parent,
            self.semantic_storage_path.parent,
            self.procedural_storage_path.parent,
            self.goals_storage_path.parent,
            self.device_registry_path.parent,
            self.cognitive_evolution_storage_path.parent,
            self.audit_storage_path.parent,
        }
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def build_environment_report(self) -> Dict[str, Any]:
        """Retorna um resumo seguro do ambiente atual."""

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
                "queue_storage_path": str(self.queue_storage_path),
                "semantic_storage_path": str(self.semantic_storage_path),
                "procedural_storage_path": str(self.procedural_storage_path),
                "goals_storage_path": str(self.goals_storage_path),
                "device_registry_path": str(self.device_registry_path),
                "cognitive_evolution_storage_path": str(self.cognitive_evolution_storage_path),
                "audit_storage_path": str(self.audit_storage_path),
            },
            "autenticacao_configurada": {
                "token_configurado": self.token != DEFAULT_API_TOKEN,
                "dispositivo_confiavel_configurado": self.trusted_device_id != DEFAULT_TRUSTED_DEVICE_ID,
                "senha_admin_configurada": str(os.environ.get("JARVIS_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)) != DEFAULT_ADMIN_PASSWORD,
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
