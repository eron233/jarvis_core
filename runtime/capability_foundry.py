"""Fabrica de Capacidades do JARVIS: catalogo, admissibilidade e execucao limitada.

Primeiro caso funcional: corte de video utilizando FFmpeg preinstalado.
Nao copia produtos proprietarios, nao instala dependencias ou executa
codigo gerado sem sandbox. Recursos desconhecidos ficam em planejamento.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Capability:
    id: str
    title_ptbr: str
    required_executable: str
    operation: str
    license_note: str


_BUILTINS = {
    "video.trim": Capability(
        id="video.trim",
        title_ptbr="Cortar um video em um intervalo",
        required_executable="ffmpeg",
        operation="video_trim",
        license_note=(
            "Utiliza FFmpeg instalado separadamente. Verifique licenca e "
            "opcoes de compilacao/distribuicao antes de empacotar."
        ),
    ),
}


class CapabilityFoundry:
    """Decide usar capacidade existente antes de prometer geracao autonoma."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = Path(workspace) if workspace is not None else (
            Path(__file__).resolve().parents[1] / "data" / "studio_media"
        )

    def list_capabilities(self) -> list[Dict[str, Any]]:
        result = []
        for spec in _BUILTINS.values():
            result.append({
                "id": spec.id,
                "nome": spec.title_ptbr,
                "backend": spec.required_executable,
                "instalado": bool(shutil.which(spec.required_executable)),
                "licenca": spec.license_note,
                "execucao_automatica": False,
            })
        return result

    def plan(self, request: str, capability_id: str | None = None) -> Dict[str, Any]:
        """Planejamento deterministico: sem IA, sem procurar nem baixar codigo."""
        if not isinstance(request, str) or not request.strip():
            return {"status": "entrada_invalida", "motivo": "Descreva a capacidade desejada."}
        requested = str(capability_id or "").strip()
        spec = _BUILTINS.get(requested)
        if not spec:
            return {
                "status": "requer_pesquisa",
                "pedido": request[:500],
                "capacidade": requested or None,
                "gerada": False,
                "executada": False,
                "motivo": (
                    "Nao existe receita validada para esta capacidade. "
                    "Pesquisa, engenharia reversa e implementacao sao etapas futuras, "
                    "dependentes de escopo, licenca e testes."
                ),
            }
        binary = shutil.which(spec.required_executable)
        return {
            "status": "disponivel" if binary else "dependencia_indisponivel",
            "pedido": request[:500],
            "capacidade": spec.id,
            "ferramenta": spec.title_ptbr,
            "backend": spec.required_executable,
            "backend_disponivel": bool(binary),
            "licenca": spec.license_note,
            "gerada": False,
            "executada": False,
            "aprovacao_necessaria_para_executar": True,
        }

    def trim_video(
        self, input_name: str, output_name: str,
        start_seconds: float, duration_seconds: float,
        *, approved: bool = False,
    ) -> Dict[str, Any]:
        """Corta arquivo do workspace apos autorizacao, SEM shell e SEM overwrite.

        ffmpeg e codigo de terceiros e processa midia potencialmente hostil:
        este adapter nao e sandbox forte. Nao o exponha a usuarios nao confiaveis.
        """
        if not approved:
            return {"status": "aguardando_aprovacao", "executado": False}
        if not isinstance(start_seconds, (int, float)) or not isinstance(duration_seconds, (int, float)):
            return {"status": "entrada_invalida", "executado": False}
        if (isinstance(start_seconds, bool) or isinstance(duration_seconds, bool)
            or not math.isfinite(start_seconds) or not math.isfinite(duration_seconds)
            or start_seconds < 0 or not 0 < duration_seconds <= 3600):
            return {"status": "entrada_invalida", "executado": False,
                    "motivo": "Inicio deve ser >= 0 e duracao deve estar entre 0 e 3600 s."}
        # Somente nomes planos ASCII: sem caminhos, flags, links ou traversal.
        def permitted(name: Any) -> bool:
            return (
                isinstance(name, str) and 1 <= len(name) <= 120
                and name.isascii() and
                all(ch.isalnum() or ch in "._-" for ch in name)
                and name not in {".", ".."} and not name.startswith("-")
                and name.lower().endswith(".mp4")
            )
        if not permitted(input_name) or not permitted(output_name) or input_name == output_name:
            return {"status": "entrada_invalida", "executado": False,
                    "motivo": "Use nomes .mp4 locais e distintos, sem pastas."}

        root = self.workspace.resolve()
        source = root / input_name
        dest = root / output_name
        if (not root.is_dir() or source.is_symlink() or not source.is_file()
            or not source.resolve().is_relative_to(root)):
            return {"status": "entrada_indisponivel", "executado": False}
        if dest.exists() or dest.is_symlink():
            return {"status": "saida_existente", "executado": False}

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return {"status": "dependencia_indisponivel", "executado": False,
                    "motivo": "FFmpeg precisa estar instalado pelo operador."}

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=root, prefix=".jarvis-video-", suffix=".mp4", delete=False
            ) as out:
                temp_path = Path(out.name)
            args = [
                ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                "-i", str(source), "-ss", str(start_seconds),
                "-t", str(duration_seconds),
                "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
                "-preset", "ultrafast", "-c:a", "aac",
                "-movflags", "+faststart", "-f", "mp4", "-y", str(temp_path),
            ]
            proc = subprocess.run(
                args, cwd=root, capture_output=True, timeout=120, check=False,
            )
            if proc.returncode != 0:
                return {"status": "erro_processamento", "executado": True,
                        "arquivo_criado": False, "codigo_saida": proc.returncode}
            if not temp_path.is_file() or temp_path.stat().st_size <= 0:
                return {"status": "saida_invalida", "executado": True,
                        "arquivo_criado": False}
            # link atomico impede sobrescrever destino criado por outra tarefa.
            try:
                os.link(temp_path, dest)
            except FileExistsError:
                return {"status": "saida_existente", "executado": True,
                        "arquivo_criado": False}
            return {
                "status": "arquivo_criado_nao_homologado",
                "executado": True,
                "arquivo_criado": True,
                "resultado": str(dest),
                "tamanho_bytes": dest.stat().st_size,
                "resultado_verificado_por_reproducao": False,
                "motivo": "Arquivo gerado. Integridade visual/audio requer validacao adicional.",
            }
        except subprocess.TimeoutExpired:
            return {"status": "tempo_excedido", "executado": True, "arquivo_criado": False}
        except OSError:
            return {"status": "erro_operacional", "executado": False, "arquivo_criado": False}
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
