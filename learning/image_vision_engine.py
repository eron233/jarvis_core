"""
JARVIS - Analise basica de imagem e pre-contexto visual

Responsavel por:
- identificar formato e dimensoes reais (PNG, JPEG, GIF, WEBP, BMP) lendo o cabecalho do arquivo
- extrair texto por OCR quando o binario `tesseract` estiver instalado
- montar um pre-contexto textual honesto (sem inventar texto quando nao ha OCR)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import struct
import subprocess
from typing import Any, Dict, Optional, Tuple


def _read_dimensions(data: bytes) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """Retorna (formato, largura, altura) lendo so o cabecalho."""

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return "gif", width, height
    if data.startswith(b"BM") and len(data) >= 26:
        width, height = struct.unpack("<ii", data[18:26])
        return "bmp", width, abs(height)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return "webp", width, height
        if chunk == b"VP8 " and len(data) >= 30:
            width, height = struct.unpack("<HH", data[26:30])
            return "webp", width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return "webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        return "webp", None, None
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return "jpeg", width, height
            segment_length = struct.unpack(">H", data[index + 2:index + 4])[0]
            index += 2 + segment_length
        return "jpeg", None, None
    return None, None, None


class ImageVisionEngine:
    """Metadados reais de imagem + OCR opcional via tesseract."""

    def __init__(self, tesseract_path: Optional[str] = None) -> None:
        self.tesseract_path = tesseract_path or shutil.which("tesseract")

    def analyze_image_and_build_context(
        self,
        image_path: str | Path,
        user_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Le metadados da imagem e, se possivel, o texto contido nela."""

        now = datetime.now(timezone.utc).isoformat()
        path = Path(image_path)
        if not path.is_file():
            return {"status": "erro", "motivo": f"Imagem {path.name} nao encontrada."}

        with path.open("rb") as handle:
            header = handle.read(64 * 1024)
        image_format, width, height = _read_dimensions(header)
        if image_format is None:
            return {"status": "erro", "motivo": "Arquivo nao reconhecido como imagem (PNG, JPEG, GIF, WEBP ou BMP)."}

        ocr_text, ocr_status = self._perform_ocr_extraction(path)
        dimensions = f"{width}x{height}" if width and height else "dimensoes desconhecidas"
        summary = f"Imagem '{path.name}' ({image_format.upper()}, {dimensions}, {path.stat().st_size} bytes)."
        if ocr_text:
            summary += f" Texto reconhecido: {ocr_text[:500]}"
        if user_hint:
            summary += f" Dica do usuario: {user_hint}."

        return {
            "status": "sucesso",
            "nome_arquivo": path.name,
            "formato": image_format,
            "largura_px": width,
            "altura_px": height,
            "tamanho_bytes": path.stat().st_size,
            "texto_extraido_ocr": ocr_text,
            "ocr_status": ocr_status,
            "pre_contexto_visual": summary,
            "analisado_em": now,
        }

    def _perform_ocr_extraction(self, path: Path) -> Tuple[str, str]:
        """Executa tesseract (se instalado) sem shell; retorna (texto, status)."""

        if not self.tesseract_path:
            return "", "indisponivel: instale o tesseract-ocr para extrair texto"
        try:
            proc = subprocess.run(
                [self.tesseract_path, str(path), "stdout", "-l", "por+eng"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "", f"erro: {exc}"
        if proc.returncode != 0:
            return "", f"erro: {proc.stderr.strip()[:200]}"
        return " ".join(proc.stdout.split()), "sucesso"
