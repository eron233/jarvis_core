"""
JARVIS - Motor de Visao e OCR

Responsavel por:
- inspecionar metadados reais de imagens
- executar OCR real via VisionStack quando configurado
- obter descricao visual geral opcional
- encaminhar documentos complexos ao parser visual sob demanda
- nunca confundir strings binarias com OCR
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from learning.vision_stack import VisionStack, VisionStackConfig


class ImageVisionEngine:
    """Facade de visao do JARVIS com degradacao graciosa e resultados auditaveis."""

    def __init__(
        self,
        config: Optional[VisionStackConfig] = None,
        vision_stack: Optional[VisionStack] = None,
    ) -> None:
        self.vision_stack = vision_stack or VisionStack(config=config)

    def analyze_image_and_build_context(
        self,
        image_path: str | Path,
        user_hint: Optional[str] = None,
        include_general_vision: bool = True,
    ) -> Dict[str, Any]:
        """Analisa metadados, OCR e visao geral sem fabricar percepcao."""

        now = datetime.now(timezone.utc).isoformat()
        path = Path(image_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Imagem {image_path} não encontrada no sistema."}
        if not path.is_file():
            return {"status": "erro", "motivo": f"O caminho {image_path} não é um arquivo."}

        metadata = self._inspect_image(path)
        ocr = self.vision_stack.extract_text(path)

        visual = {
            "status": "nao_solicitado",
            "descricao": None,
            "metodo": None,
            "motivo": None,
        }
        if include_general_vision:
            visual = self.vision_stack.describe_image(path)

        text = ocr.get("texto") if ocr.get("status") == "sucesso" else None
        description = (
            visual.get("descricao")
            if visual.get("status") == "sucesso"
            else None
        )

        context_parts = [
            f"Arquivo visual '{path.name}'",
            f"{path.stat().st_size} bytes",
        ]
        if metadata.get("formato_detectado"):
            context_parts.append(f"formato {metadata['formato_detectado']}")
        elif path.suffix:
            context_parts.append(f"extensão {path.suffix.lower().lstrip('.').upper()}")

        if metadata.get("largura") and metadata.get("altura"):
            context_parts.append(
                f"{metadata['largura']}x{metadata['altura']} pixels"
            )

        if text:
            context_parts.append(f"OCR real detectou: {text}")
        else:
            context_parts.append(
                f"OCR: {ocr.get('status', 'indisponivel')}"
            )

        if description:
            context_parts.append(f"Descrição visual: {description}")
        elif include_general_vision:
            context_parts.append(
                f"Visão geral: {visual.get('status', 'indisponivel')}"
            )

        if user_hint:
            context_parts.append(f"Dica do usuário: {user_hint}")

        return {
            "status": "sucesso",
            "nome_arquivo": path.name,
            "caminho": str(path),
            "formato": (
                str(metadata.get("formato_detectado") or path.suffix.lower().lstrip("."))
                .lower()
            ),
            "tamanho_bytes": path.stat().st_size,
            "largura": metadata.get("largura"),
            "altura": metadata.get("altura"),
            "modo_cor": metadata.get("modo_cor"),
            "metadados_imagem": metadata,
            "texto_extraido_ocr": text,
            "ocr": ocr,
            "visao_geral": visual,
            "pre_contexto_visual": ". ".join(context_parts) + ".",
            "analisado_em": now,
        }

    def ask_image(self, image_path: str | Path, question: str) -> Dict[str, Any]:
        """Faz uma pergunta visual somente em backend real configurado."""

        path = Path(image_path)
        if not path.exists():
            return {"status": "erro", "resposta": None, "motivo": f"Imagem {image_path} não encontrada."}
        if not str(question).strip():
            return {"status": "erro", "resposta": None, "motivo": "A pergunta visual não pode ficar vazia."}
        result = self.vision_stack.ask_image(path, str(question).strip())
        result["arquivo"] = str(path)
        result["pergunta"] = str(question).strip()
        return result

    def parse_complex_document(self, image_path: str | Path) -> Dict[str, Any]:
        """Aciona PaddleOCR-VL somente quando documento complexo for solicitado."""

        path = Path(image_path)
        if not path.exists():
            return {
                "status": "erro",
                "markdown": None,
                "estruturado": [],
                "motivo": f"Arquivo {image_path} não encontrado.",
            }
        result = self.vision_stack.parse_document_visual(path)
        result["arquivo"] = str(path)
        return result

    def describe_capabilities(self) -> Dict[str, Any]:
        """Informa exatamente quais backends estão ativos."""

        return self.vision_stack.status()

    @staticmethod
    def _inspect_image(path: Path) -> Dict[str, Any]:
        """Le metadados usando Pillow quando disponivel, sem inferir dados ausentes."""

        metadata = {
            "formato_detectado": None,
            "largura": None,
            "altura": None,
            "modo_cor": None,
            "frames": None,
            "pillow_disponivel": importlib.util.find_spec("PIL") is not None,
            "imagem_valida_confirmada": False,
            "erro_metadados": None,
        }
        if not metadata["pillow_disponivel"]:
            return metadata

        try:
            from PIL import Image

            with Image.open(path) as image:
                metadata.update(
                    {
                        "formato_detectado": image.format,
                        "largura": int(image.width),
                        "altura": int(image.height),
                        "modo_cor": image.mode,
                        "frames": int(getattr(image, "n_frames", 1)),
                        "imagem_valida_confirmada": True,
                    }
                )
        except Exception as exc:
            metadata["erro_metadados"] = f"{exc.__class__.__name__}: {exc}"
        return metadata
