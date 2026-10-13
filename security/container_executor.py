"""Experimental Twin: opt-in Docker executor for untrusted generated Python.

A container is a kernel-shared isolation boundary, NOT a VM. No host folders,
credentials or sockets are mounted. A pinned, already-local image is mandatory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import secrets
import selectors
import shutil
import socket
import stat
import subprocess
import tempfile
import time
from typing import Any

IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}$")
DOCKER_SOCKET = "/var/run/docker.sock"
MAX_SOURCE_BYTES = 128 * 1024
MAX_INPUT_BYTES = 192 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
RESULT_PREFIX = "JARVIS_TWIN_RESULT:"

# A funcao nao roda no host. Apenas o processo Python dentro do container
# compila e executa o codigo. O resultado da ferramenta NAO prova conclusao.
HARNESS = """
import json
import sys
try:
    payload = json.load(sys.stdin)
    scope = {"__name__": "jarvis_generated_tool"}
    exec(compile(payload["source"], "<generated-tool>", "exec"), scope)
    result = scope["run_tool"](payload["params"])
    print("JARVIS_TWIN_RESULT:" + json.dumps(
        {"ok": True, "value": result}, ensure_ascii=False, allow_nan=False))
except BaseException as exc:
    print("JARVIS_TWIN_RESULT:" + json.dumps(
        {"ok": False, "error_type": type(exc).__name__,
         "error": str(exc)[:250]}, ensure_ascii=False))
"""


class ContainerExecutor:
    """Tier 2 Linux-only: Docker with immutable image, no network/mounts.

    Disabled by default. Docker Desktop/Windows must use a separately validated
    Linux/WSL2 host. This never promises VM-grade isolation.
    """

    def __init__(self, *, enabled: bool = False, image: str = "") -> None:
        self.enabled = enabled
        self.image = image

    @staticmethod
    def _refusal(reason: str) -> dict[str, Any]:
        return {
            "status": "bloqueado_por_seguranca",
            "motivo": reason,
            "executado": False,
            "concluido_verificado": False,
            "isolamento_validado": False,
        }

    def execute(self, source: str, params: dict[str, Any] | None = None,
                timeout_seconds: float = 5.0) -> dict[str, Any]:
        if not self.enabled:
            return self._refusal("Executor de container nao habilitado pelo operador.")
        if platform.system() != "Linux":
            return self._refusal("Backend validado apenas para host Linux.")
        if not IMAGE_RE.fullmatch(self.image):
            return self._refusal("Imagem deve conter digest sha256 imutavel.")
        if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            return self._refusal("Codigo invalido ou maior que o limite.")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._refusal("Argumentos precisam ser um objeto JSON.")
        if not isinstance(timeout_seconds, (float, int)) or isinstance(timeout_seconds, bool) or not (1 <= timeout_seconds <= 30):
            return self._refusal("Tempo deve ser de 1 a 30 segundos.")
        try:
            payload = json.dumps({"source": source, "params": params},
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            return self._refusal("Argumentos nao serializaveis em JSON.")
        if len(payload) > MAX_INPUT_BYTES:
            return self._refusal("Entrada excede limite de bytes.")

        docker = shutil.which("docker")
        if not docker or not Path(docker).is_file():
            return self._refusal("Docker CLI indisponivel.")
        # Recusar DOCKER_HOST/context remoto e ambientes sem daemon local.
        try:
            if not stat.S_ISSOCK(os.stat(DOCKER_SOCKET).st_mode):
                return self._refusal("Socket Docker local indisponivel.")
        except OSError:
            return self._refusal("Socket Docker local indisponivel.")

        container_name = "jarvis-twin-" + secrets.token_hex(12)
        argv = [
            docker, "--host", "unix://" + DOCKER_SOCKET, "run",
            "--rm", "--name", container_name, "--pull", "never",
            "--network", "none", "--read-only",
            "--security-opt", "no-new-privileges:true",
            "--security-opt", "seccomp=builtin",
            "--cap-drop", "ALL", "--user", "65534:65534",
            "--pids-limit", "32", "--memory", "256m", "--memory-swap", "256m",
            "--cpus", "1", "--ipc", "none", "--cgroupns", "private",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--workdir", "/tmp", "--log-driver", "none",
            "--ulimit", "nofile=64:64",
            "-i", "--entrypoint", "python",
            self.image, "-I", "-B", "-c", HARNESS,
        ]
        # DOCKER_CONFIG vazio impede heranca de login/credenciais do dono.
        with tempfile.TemporaryDirectory(prefix="jarvis-docker-client-") as config_dir:
            cli_env = {"PATH": "/usr/local/bin:/usr/bin:/bin",
                       "HOME": config_dir, "DOCKER_CONFIG": config_dir}
            started = False
            try:
                started = True
                return_code, stdout, stderr = self._invoke(argv, payload,
                                                            float(timeout_seconds) + 3, cli_env)
            except (TimeoutError, OSError, ValueError) as exc:
                return {
                    "status": "erro_executor", "motivo": type(exc).__name__,
                    "executado": started, "concluido_verificado": False,
                    "isolamento_validado": False,
                }
            finally:
                # Se o cliente Docker caiu ou expirou, a criacao pode ter
                # continuado no daemon. Remocao forcada nao depende de stdout.
                if started:
                    try:
                        subprocess.run(
                            [docker, "--host", "unix://" + DOCKER_SOCKET,
                             "rm", "-f", container_name],
                            capture_output=True, timeout=4, env=cli_env,
                            check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        pass

        if return_code != 0:
            return {"status": "erro_container",
                    "motivo": stderr.decode("utf-8", "replace")[-500:],
                    "executado": True, "concluido_verificado": False,
                    "isolamento_validado": False}
        try:
            found = [line[len(RESULT_PREFIX):] for line in
                     stdout.decode("utf-8").splitlines()
                     if line.startswith(RESULT_PREFIX)]
            report = json.loads(found[-1])
            if not isinstance(report, dict) or not isinstance(report.get("ok"), bool):
                raise ValueError("Contrato invalido")
        except (ValueError, IndexError, UnicodeError, TypeError):
            return {"status": "erro_saida_invalida", "executado": True,
                    "concluido_verificado": False, "isolamento_validado": False}

        if not report["ok"]:
            return {"status": "erro_ferramenta", "executado": True,
                    "erro": report.get("error_type", "Erro"),
                    "motivo": report.get("error", "")[:250],
                    "concluido_verificado": False, "isolamento_validado": True}
        return {
            "status": "executado_sem_verificacao",
            "executado": True,
            "concluido_verificado": False,  # resposta do proprio codigo nao e prova
            "isolamento_validado": True,  # configuracao imposta pelo comando
            "resultado_declarado": report.get("value"),
        }

    @staticmethod
    def _invoke(argv: list[str], payload: bytes, timeout: float,
                env: dict[str, str]) -> tuple[int, bytes, bytes]:
        """I/O nao bloqueante e limitado. Mata o cliente no excesso/timeout."""
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, start_new_session=True)
        outputs: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        offset = 0
        deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as poll:
                for stream, label, event in (
                    (proc.stdin, "stdin", selectors.EVENT_WRITE),
                    (proc.stdout, "stdout", selectors.EVENT_READ),
                    (proc.stderr, "stderr", selectors.EVENT_READ),
                ):
                    os.set_blocking(stream.fileno(), False)
                    poll.register(stream, event, label)
                while poll.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Tempo excedido")
                    for key, _ in poll.select(min(remaining, 0.2)):
                        label = key.data
                        if label == "stdin":
                            if offset >= len(payload):
                                poll.unregister(key.fileobj)
                                key.fileobj.close()
                            else:
                                try:
                                    offset += os.write(key.fileobj.fileno(),
                                                       payload[offset:offset + 4096])
                                except BlockingIOError:
                                    pass
                        else:
                            chunk = os.read(key.fileobj.fileno(), 4096)
                            if not chunk:
                                poll.unregister(key.fileobj)
                                key.fileobj.close()
                                continue
                            outputs[label].extend(chunk)
                            if len(outputs["stdout"]) + len(outputs["stderr"]) > MAX_OUTPUT_BYTES:
                                raise ValueError("Saida excede limite")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Tempo excedido")
            rc = proc.wait(timeout=remaining)
            return rc, bytes(outputs["stdout"]), bytes(outputs["stderr"])
        except BaseException:
            proc.kill()
            proc.wait(timeout=3)
            raise
        finally:
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
