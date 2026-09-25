"""
JARVIS - Motor de Compactação e Descompactação de Arquivos (.zip, .tar, .gz, .bz2)

Responsável por:
- compactar qualquer arquivo ou diretório em arquivos compactados (.zip, .tar, .gz, .bz2)
- descompactar e extrair arquivos compactados com segurança
- verificar integridade de arquivos compactados
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tarfile
from typing import Any, Dict, List, Optional
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_DIR = PROJECT_ROOT / "data" / "file_archives"
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB: barreira contra zip bomb


class FileArchiveEngine:
    """Motor de gerenciamento, compactação e descompactação de arquivos."""

    def __init__(self, archive_dir: Optional[Path] = None) -> None:
        self.archive_dir = Path(archive_dir) if archive_dir else DEFAULT_ARCHIVE_DIR
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def compress_files(
        self,
        source_paths: List[str | Path],
        archive_name: str = "archive",
        format_type: str = "zip",  # "zip", "tar", "tar.gz", "tar.bz2"
    ) -> Dict[str, Any]:
        """
        Compacta uma lista de arquivos ou diretórios no formato especificado.
        """
        now = datetime.now(timezone.utc).isoformat()
        fmt = format_type.lower()
        if not fmt.startswith("."):
            ext = f".{fmt}"
        else:
            ext = fmt
            fmt = fmt.lstrip(".")

        safe_name = Path(archive_name).name or "archive"
        out_name = safe_name if safe_name.endswith(ext) else f"{safe_name}{ext}"
        out_path = self.archive_dir / out_name

        try:
            if fmt == "zip" or ext == ".zip":
                with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for src in source_paths:
                        p = Path(src)
                        if p.is_file():
                            zipf.write(p, arcname=p.name)
                        elif p.is_dir():
                            for root, _, files in os.walk(p):
                                for file in files:
                                    fp = Path(root) / file
                                    zipf.write(fp, arcname=fp.relative_to(p.parent))
            elif "tar" in fmt or "tar" in ext:
                mode = "w:gz" if "gz" in fmt else ("w:bz2" if "bz2" in fmt else "w")
                with tarfile.open(out_path, mode) as tarf:
                    for src in source_paths:
                        p = Path(src)
                        tarf.add(p, arcname=p.name)
            else:
                return {"status": "erro", "motivo": f"Formato de compactação '{format_type}' não suportado."}

            return {
                "status": "sucesso",
                "arquivo_compactado": str(out_path),
                "tamanho_bytes": out_path.stat().st_size,
                "gerado_em": now,
            }
        except Exception as e:
            return {"status": "erro", "motivo": str(e)}

    def decompress_archive(
        self,
        archive_path: str | Path,
        destination_dir: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """
        Descompacta e extrai qualquer arquivo compactado (.zip, .tar, .tar.gz, etc).
        """
        now = datetime.now(timezone.utc).isoformat()
        src_path = Path(archive_path)
        if not src_path.exists():
            return {"status": "erro", "motivo": f"Arquivo {archive_path} não encontrado."}

        target_dir = Path(destination_dir) if destination_dir else (self.archive_dir / f"extracted_{src_path.stem}")
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            extracted_files = []
            if zipfile.is_zipfile(src_path):
                with zipfile.ZipFile(src_path, "r") as zipf:
                    members = zipf.infolist()
                    self._check_archive_limits(len(members), sum(m.file_size for m in members))
                    for member in members:
                        self._safe_destination(target_dir, member.filename)
                    zipf.extractall(target_dir)
                    extracted_files = [m.filename for m in members]
            elif tarfile.is_tarfile(src_path):
                with tarfile.open(src_path, "r:*") as tarf:
                    members = tarf.getmembers()
                    self._check_archive_limits(len(members), sum(m.size for m in members))
                    for member in members:
                        # Links, dispositivos e FIFOs podem escapar do destino ou travar a extracao.
                        if not (member.isfile() or member.isdir()):
                            raise ValueError(f"Entrada nao permitida no arquivo: {member.name}")
                        self._safe_destination(target_dir, member.name)
                    tarf.extractall(target_dir, members=members)
                    extracted_files = [m.name for m in members]
            else:
                return {"status": "erro", "motivo": "Formato de arquivo compactado não reconhecido."}

            return {
                "status": "sucesso",
                "arquivo_origem": str(src_path),
                "diretorio_destino": str(target_dir),
                "total_arquivos_extraidos": len(extracted_files),
                "extraido_em": now,
            }
        except Exception as e:
            return {"status": "erro", "motivo": str(e)}

    @staticmethod
    def _safe_destination(target_dir: Path, member_name: str) -> Path:
        """Garante que a entrada do arquivo compactado nao escape do diretorio destino."""

        root = target_dir.resolve()
        destination = (root / member_name).resolve()
        if destination != root and root not in destination.parents:
            raise ValueError(f"Entrada tenta escapar do destino: {member_name}")
        return destination

    @staticmethod
    def _check_archive_limits(entries: int, uncompressed_bytes: int) -> None:
        if entries > MAX_ARCHIVE_ENTRIES:
            raise ValueError(f"Arquivo com entradas demais ({entries}).")
        if uncompressed_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("Arquivo descompactado excederia o limite de 2 GiB.")
