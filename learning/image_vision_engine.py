"""
JARVIS - Motor de Visão, Análise de Imagem e Pré-Contexto Visual

Responsável por:
- processar qualquer arquivo de imagem, print ou captura de tela
- extrair texto de imagens (OCR) e metadados estruturados (dimensões, formato, cores)
- gerar um pré-contexto visual para injeção na memória semântica e instrução do runtime
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional


class ImageVisionEngine:
    """Motor de análise de imagens, OCR e geração de pré-contexto visual."""

    def __init__(self) -> None:
        pass

    def analyze_image_and_build_context(
        self,
        image_path: str | Path,
        user_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analisa uma imagem/print, extrai textos/metadados e gera um pré-contexto descritivo.
        """
        now = datetime.now(timezone.utc).isoformat()
        path = Path(image_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Imagem {image_path} não encontrada no sistema."}

        extension = path.suffix.lower().replace(".", "")
        file_size_bytes = path.stat().st_size

        # Extração de dimensões reais lendo o cabeçalho binário da imagem (ou via Pillow, se disponível)
        largura_px, altura_px = self._extract_image_dimensions(path)

        # Extração de texto (OCR) — honesta: só afirma ter extraído texto se houver engine de OCR real
        ocr_result = self._perform_ocr_extraction(path)

        # Geração do Pré-Contexto Descritivo
        dims_txt = f"{largura_px}x{altura_px}px" if largura_px and altura_px else "dimensões não identificadas"
        if ocr_result["ocr_disponivel"]:
            texto_txt = ocr_result["texto"] if ocr_result["texto"] else "nenhum texto detectado"
        else:
            texto_txt = "OCR real não disponível nesta instalação (nenhuma engine de OCR configurada)"

        visual_summary = (
            f"Imagem '{path.name}' (formato {extension.upper()}, {file_size_bytes} bytes, {dims_txt}). "
            f"Texto extraído: '{texto_txt}'. "
        )
        if user_hint:
            visual_summary += f"Dica do usuário: {user_hint}."

        return {
            "status": "sucesso",
            "nome_arquivo": path.name,
            "caminho": str(path),
            "formato": extension,
            "tamanho_bytes": file_size_bytes,
            "largura_px": largura_px,
            "altura_px": altura_px,
            "ocr_disponivel": ocr_result["ocr_disponivel"],
            "texto_extraido_ocr": ocr_result["texto"],
            "pre_contexto_visual": visual_summary,
            "analisado_em": now,
        }

    def _extract_image_dimensions(self, path: Path) -> tuple[Optional[int], Optional[int]]:
        """
        Extrai largura e altura reais da imagem.

        Usa Pillow quando disponível (detecção em runtime via try/except import, sem
        adicioná-lo como dependência obrigatória); caso contrário, faz o parsing manual
        do cabeçalho binário para PNG, JPEG, GIF e BMP.
        """
        try:
            from PIL import Image  # type: ignore

            with Image.open(path) as img:
                return img.size[0], img.size[1]
        except Exception:
            pass

        try:
            raw = path.read_bytes()
        except Exception:
            return None, None

        return self._parse_dimensions_from_header(raw)

    @staticmethod
    def _parse_dimensions_from_header(raw: bytes) -> tuple[Optional[int], Optional[int]]:
        """Faz o parsing manual do cabeçalho binário de PNG/JPEG/GIF/BMP para extrair largura/altura."""
        # PNG: assinatura de 8 bytes, seguida do chunk IHDR (largura em [16:20], altura em [20:24], big-endian)
        if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
            largura = int.from_bytes(raw[16:20], "big")
            altura = int.from_bytes(raw[20:24], "big")
            return largura, altura

        # GIF: header "GIF87a"/"GIF89a", largura em [6:8], altura em [8:10], little-endian
        if raw.startswith((b"GIF87a", b"GIF89a")) and len(raw) >= 10:
            largura = int.from_bytes(raw[6:8], "little")
            altura = int.from_bytes(raw[8:10], "little")
            return largura, altura

        # BMP: header "BM", largura em [18:22], altura em [22:26], little-endian (assinado)
        if raw.startswith(b"BM") and len(raw) >= 26:
            largura = int.from_bytes(raw[18:22], "little", signed=True)
            altura = int.from_bytes(raw[22:26], "little", signed=True)
            return abs(largura), abs(altura)

        # JPEG: percorre os marcadores procurando um segmento SOF0..SOF3 (dimensões reais do frame)
        if raw.startswith(b"\xff\xd8"):
            i = 2
            n = len(raw)
            while i + 4 <= n:
                if raw[i] != 0xFF:
                    i += 1
                    continue
                marker = raw[i + 1]
                # Marcadores sem payload (não seguidos de comprimento)
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                if i + 4 > n:
                    break
                seg_len = int.from_bytes(raw[i + 2:i + 4], "big")
                is_sof = marker in (0xC0, 0xC1, 0xC2, 0xC3)
                if is_sof and i + 9 <= n:
                    altura = int.from_bytes(raw[i + 5:i + 7], "big")
                    largura = int.from_bytes(raw[i + 7:i + 9], "big")
                    return largura, altura
                i += 2 + seg_len

        return None, None

    def _perform_ocr_extraction(self, path: Path) -> Dict[str, Any]:
        """
        Realiza OCR real quando uma engine estiver disponível (Pillow + pytesseract).

        Sem uma engine de OCR instalada, é honesto: retorna texto vazio e sinaliza
        ocr_disponivel=False, em vez de fingir que bytes binários lidos do arquivo
        são "texto extraído por OCR".
        """
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            with Image.open(path) as img:
                texto = pytesseract.image_to_string(img).strip()
            return {"ocr_disponivel": True, "texto": texto}
        except Exception:
            return {"ocr_disponivel": False, "texto": ""}
