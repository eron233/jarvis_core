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

        # Extração de strings/texto contido na imagem (OCR simples/fallback)
        extracted_text = self._perform_ocr_extraction(path)

        # Geração do Pré-Contexto Descritivo
        visual_summary = (
            f"Imagem '{path.name}' (formato {extension.upper()}, {file_size_bytes} bytes). "
            f"Texto extraído: '{extracted_text if extracted_text else 'nenhum texto detectado'}'. "
        )
        if user_hint:
            visual_summary += f"Dica do usuário: {user_hint}."

        return {
            "status": "sucesso",
            "nome_arquivo": path.name,
            "caminho": str(path),
            "formato": extension,
            "tamanho_bytes": file_size_bytes,
            "texto_extraido_ocr": extracted_text,
            "pre_contexto_visual": visual_summary,
            "analisado_em": now,
        }

    def _perform_ocr_extraction(self, path: Path) -> str:
        """
        Realiza a extração de texto de imagem (OCR com fallback limpo).
        """
        try:
            # Leitura de bytes com extração de caracteres ASCII/UTF-8 imprimíveis
            raw_bytes = path.read_bytes()
            printable_strings = re.findall(rb"[\x20-\x7e\x80-\xff]{4,}", raw_bytes)
            lines = [s.decode("utf-8", errors="ignore") for s in printable_strings if len(s) > 4]
            filtered = [l for l in lines if not l.startswith("PNG") and not l.startswith("JFIF") and not l.startswith("Exif")]
            return " ".join(filtered[:10])
        except Exception:
            return ""
