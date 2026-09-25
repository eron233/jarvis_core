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

        out_name = archive_name if archive_name.endswith(ext) else f"{archive_name}{ext}"
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
                    zipf.extractall(target_dir)
                    extracted_files = zipf.namelist()
            elif tarfile.is_tarfile(src_path):
                with tarfile.open(src_path, "r:*") as tarf:
                    tarf.extractall(target_dir)
                    extracted_files = tarf.getnames()
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
