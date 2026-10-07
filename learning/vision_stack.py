"""
JARVIS - Stack Modular de Visao

Backends opcionais:
- PP-OCRv6 para OCR leve/multilingue
- PaddleOCR-VL para documentos complexos
- Moondream para entendimento visual geral (caption/query/detect), via cliente local

A pilha e lazy, local-first e nao inventa resultados quando um backend nao existe.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _optional_path(env: Mapping[str, str], name: str, root: Path) -> Optional[Path]:
    raw = (env.get(name) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class VisionStackConfig:
    enabled: bool = False
    locale: str = "pt-BR"

    ocr_backend: str = "paddleocr-v6"
    ocr_device: str = "cpu"
    ocr_engine: str = "paddle_static"
    ocr_detection_model: str = "PP-OCRv6_small_det"
    ocr_recognition_model: str = "PP-OCRv6_small_rec"
    ocr_detection_model_dir: Optional[Path] = None
    ocr_recognition_model_dir: Optional[Path] = None
    ocr_allow_model_download: bool = False
    ocr_min_score: float = 0.35

    document_vl_enabled: bool = False
    document_vl_device: str = "cpu"
    document_vl_engine: str = "transformers"
    document_vl_allow_model_download: bool = False

    general_vision_enabled: bool = False
    general_vision_endpoint: Optional[str] = None
    general_vision_model: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "VisionStackConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)
        return cls(
            enabled=_env_bool(env.get("JARVIS_VISION_ADVANCED_ENABLED"), False),
            locale=(env.get("JARVIS_VISION_LOCALE") or "pt-BR").strip(),
            ocr_backend=(env.get("JARVIS_OCR_BACKEND") or "paddleocr-v6").strip(),
            ocr_device=(env.get("JARVIS_OCR_DEVICE") or "cpu").strip(),
            ocr_engine=(env.get("JARVIS_OCR_ENGINE") or "paddle_static").strip(),
            ocr_detection_model=(env.get("JARVIS_OCR_DETECTION_MODEL") or "PP-OCRv6_small_det").strip(),
            ocr_recognition_model=(env.get("JARVIS_OCR_RECOGNITION_MODEL") or "PP-OCRv6_small_rec").strip(),
            ocr_detection_model_dir=_optional_path(env, "JARVIS_OCR_DETECTION_MODEL_DIR", root),
            ocr_recognition_model_dir=_optional_path(env, "JARVIS_OCR_RECOGNITION_MODEL_DIR", root),
            ocr_allow_model_download=_env_bool(env.get("JARVIS_OCR_ALLOW_MODEL_DOWNLOAD"), False),
            ocr_min_score=max(0.0, min(1.0, float(env.get("JARVIS_OCR_MIN_SCORE", "0.35")))),
            document_vl_enabled=_env_bool(env.get("JARVIS_DOCUMENT_VL_ENABLED"), False),
            document_vl_device=(env.get("JARVIS_DOCUMENT_VL_DEVICE") or "cpu").strip(),
            document_vl_engine=(env.get("JARVIS_DOCUMENT_VL_ENGINE") or "transformers").strip(),
            document_vl_allow_model_download=_env_bool(
                env.get("JARVIS_DOCUMENT_VL_ALLOW_MODEL_DOWNLOAD"),
                False,
            ),
            general_vision_enabled=_env_bool(env.get("JARVIS_GENERAL_VISION_ENABLED"), False),
            general_vision_endpoint=(env.get("JARVIS_GENERAL_VISION_ENDPOINT") or "").strip() or None,
            general_vision_model=(env.get("JARVIS_GENERAL_VISION_MODEL") or "").strip() or None,
        )


class PaddleOCRv6Backend:
    """OCR real com PP-OCRv6, carregado sob demanda."""

    def __init__(self, config: VisionStackConfig) -> None:
        self.config = config
        self._pipeline: Any = None
        self._load_error: Optional[str] = None

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("paddleocr") is not None

    @property
    def local_models_configured(self) -> bool:
        return bool(
            self.config.ocr_detection_model_dir
            and self.config.ocr_recognition_model_dir
            and self.config.ocr_detection_model_dir.exists()
            and self.config.ocr_recognition_model_dir.exists()
        )

    @property
    def available(self) -> bool:
        if not self.config.enabled or self.config.ocr_backend != "paddleocr-v6":
            return False
        if not self.package_available:
            return False
        return self.config.ocr_allow_model_download or self.local_models_configured

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _load(self) -> bool:
        if self._pipeline is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = (
                "PP-OCRv6 requer paddleocr instalado e modelos locais configurados, "
                "ou JARVIS_OCR_ALLOW_MODEL_DOWNLOAD=true."
            )
            return False
        try:
            from paddleocr import PaddleOCR

            kwargs: Dict[str, Any] = {
                "device": self.config.ocr_device,
                "engine": self.config.ocr_engine,
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
                "text_detection_model_name": self.config.ocr_detection_model,
                "text_recognition_model_name": self.config.ocr_recognition_model,
            }
            if self.config.ocr_detection_model_dir:
                kwargs["text_detection_model_dir"] = str(self.config.ocr_detection_model_dir)
            if self.config.ocr_recognition_model_dir:
                kwargs["text_recognition_model_dir"] = str(self.config.ocr_recognition_model_dir)

            self._pipeline = PaddleOCR(**kwargs)
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    @staticmethod
    def _unwrap_result(result: Any) -> Dict[str, Any]:
        if hasattr(result, "json"):
            payload = result.json
            if callable(payload):
                payload = payload()
        elif isinstance(result, dict):
            payload = result
        else:
            payload = {}

        if isinstance(payload, dict) and isinstance(payload.get("res"), dict):
            payload = payload["res"]
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _serializable_box(box: Any) -> Any:
        if hasattr(box, "tolist"):
            return box.tolist()
        if isinstance(box, (list, tuple)):
            return [
                PaddleOCRv6Backend._serializable_box(item)
                for item in box
            ]
        try:
            return int(box)
        except Exception:
            try:
                return float(box)
            except Exception:
                return box

    def extract_text(self, image_path: Path) -> Dict[str, Any]:
        if not self._load():
            return {
                "status": "indisponivel",
                "texto": None,
                "linhas": [],
                "motivo": self._load_error,
            }

        try:
            output = self._pipeline.predict(str(image_path))
            lines: List[Dict[str, Any]] = []
            for result in output:
                payload = self._unwrap_result(result)
                texts_raw = payload.get("rec_texts")
                scores_raw = payload.get("rec_scores")
                boxes_raw = payload.get("rec_boxes")
                if boxes_raw is None:
                    boxes_raw = payload.get("rec_polys")

                texts = list(texts_raw) if texts_raw is not None else []
                if hasattr(scores_raw, "tolist"):
                    scores_raw = scores_raw.tolist()
                if hasattr(boxes_raw, "tolist"):
                    boxes_raw = boxes_raw.tolist()

                scores = list(scores_raw) if scores_raw is not None else []
                boxes = list(boxes_raw) if boxes_raw is not None else []
                for index, text in enumerate(texts):
                    clean = str(text).strip()
                    score = float(scores[index]) if index < len(scores) else None
                    if not clean:
                        continue
                    if score is not None and score < self.config.ocr_min_score:
                        continue
                    lines.append(
                        {
                            "texto": clean,
                            "confianca": score,
                            "caixa": self._serializable_box(boxes[index])
                            if index < len(boxes)
                            else None,
                        }
                    )

            combined = "\n".join(item["texto"] for item in lines).strip()
            confidences = [
                item["confianca"]
                for item in lines
                if item["confianca"] is not None
            ]
            mean_confidence = (
                round(sum(confidences) / len(confidences), 6)
                if confidences
                else None
            )

            return {
                "status": "sucesso",
                "texto": combined or None,
                "linhas": lines,
                "quantidade_linhas": len(lines),
                "confianca_media": mean_confidence,
                "metodo": "PP-OCRv6",
                "modelo_deteccao": self.config.ocr_detection_model,
                "modelo_reconhecimento": self.config.ocr_recognition_model,
            }
        except Exception as exc:
            return {
                "status": "erro",
                "texto": None,
                "linhas": [],
                "motivo": f"Falha real no PP-OCRv6: {exc.__class__.__name__}: {exc}",
            }


class PaddleOCRVLBackend:
    """Parser visual de documentos complexos, carregado somente quando solicitado."""

    def __init__(self, config: VisionStackConfig) -> None:
        self.config = config
        self._pipeline: Any = None
        self._load_error: Optional[str] = None

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("paddleocr") is not None

    @property
    def available(self) -> bool:
        return (
            self.config.enabled
            and self.config.document_vl_enabled
            and self.package_available
            and self.config.document_vl_allow_model_download
        )

    def _load(self) -> bool:
        if self._pipeline is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = (
                "PaddleOCR-VL esta desativado. Por seguranca o runtime nao baixa "
                "o modelo implicitamente; habilite JARVIS_DOCUMENT_VL_ALLOW_MODEL_DOWNLOAD."
            )
            return False
        try:
            from paddleocr import PaddleOCRVL

            self._pipeline = PaddleOCRVL(
                device=self.config.document_vl_device,
                engine=self.config.document_vl_engine,
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
            )
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def parse(self, image_path: Path) -> Dict[str, Any]:
        if not self._load():
            return {
                "status": "indisponivel",
                "markdown": None,
                "estruturado": [],
                "motivo": self._load_error,
            }
        try:
            output = self._pipeline.predict(str(image_path))
            structured: List[Dict[str, Any]] = []
            markdown_parts: List[str] = []
            for result in output:
                payload = result.json if hasattr(result, "json") else {}
                if callable(payload):
                    payload = payload()
                if isinstance(payload, dict):
                    structured.append(payload)
                markdown = getattr(result, "markdown", None)
                if callable(markdown):
                    markdown = markdown()
                if isinstance(markdown, dict):
                    texts = markdown.get("markdown_texts")
                    if isinstance(texts, list):
                        markdown_parts.extend(str(item) for item in texts if item)
                    elif texts:
                        markdown_parts.append(str(texts))
                elif markdown:
                    markdown_parts.append(str(markdown))

            return {
                "status": "sucesso",
                "markdown": "\n\n".join(markdown_parts).strip() or None,
                "estruturado": structured,
                "paginas": len(structured),
                "metodo": "PaddleOCR-VL",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "markdown": None,
                "estruturado": [],
                "motivo": f"Falha real no PaddleOCR-VL: {exc.__class__.__name__}: {exc}",
            }


class MoondreamVisionBackend:
    """Entendimento visual geral via Moondream local/Station."""

    def __init__(self, config: VisionStackConfig) -> None:
        self.config = config
        self._client: Any = None
        self._load_error: Optional[str] = None

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("moondream") is not None

    @property
    def available(self) -> bool:
        return (
            self.config.enabled
            and self.config.general_vision_enabled
            and self.package_available
            and bool(self.config.general_vision_endpoint)
        )

    def _load(self) -> bool:
        if self._client is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = (
                "Moondream visual geral requer pacote moondream e endpoint local "
                "em JARVIS_GENERAL_VISION_ENDPOINT."
            )
            return False
        try:
            import moondream as md

            kwargs: Dict[str, Any] = {"endpoint": self.config.general_vision_endpoint}
            if self.config.general_vision_model:
                kwargs["model"] = self.config.general_vision_model
            self._client = md.vl(**kwargs)
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def query(self, image_path: Path, question: str) -> Dict[str, Any]:
        if not self._load():
            return {"status": "indisponivel", "resposta": None, "motivo": self._load_error}
        try:
            from PIL import Image

            with Image.open(image_path) as image:
                result = self._client.query(image, question)
            return {
                "status": "sucesso",
                "resposta": result.get("answer"),
                "metodo": "moondream-local",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "resposta": None,
                "motivo": f"Falha real na visao geral: {exc.__class__.__name__}: {exc}",
            }

    def caption(self, image_path: Path) -> Dict[str, Any]:
        if not self._load():
            return {"status": "indisponivel", "descricao": None, "motivo": self._load_error}
        try:
            from PIL import Image

            with Image.open(image_path) as image:
                result = self._client.caption(image, length="normal")
            return {
                "status": "sucesso",
                "descricao": result.get("caption"),
                "metodo": "moondream-local",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "descricao": None,
                "motivo": f"Falha real na legenda visual: {exc.__class__.__name__}: {exc}",
            }


class VisionStack:
    """Facade de visao do JARVIS."""

    def __init__(self, config: Optional[VisionStackConfig] = None) -> None:
        self.config = config or VisionStackConfig.from_env()
        self.ocr = PaddleOCRv6Backend(self.config)
        self.document = PaddleOCRVLBackend(self.config)
        self.general = MoondreamVisionBackend(self.config)

    def extract_text(self, path: Path) -> Dict[str, Any]:
        return self.ocr.extract_text(path)

    def parse_document_visual(self, path: Path) -> Dict[str, Any]:
        return self.document.parse(path)

    def describe_image(self, path: Path) -> Dict[str, Any]:
        return self.general.caption(path)

    def ask_image(self, path: Path, question: str) -> Dict[str, Any]:
        return self.general.query(path, question)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "locale": self.config.locale,
            "ocr": {
                "backend": self.config.ocr_backend,
                "package_available": self.ocr.package_available,
                "available": self.ocr.available,
                "device": self.config.ocr_device,
                "detection_model": self.config.ocr_detection_model,
                "recognition_model": self.config.ocr_recognition_model,
                "allow_model_download": self.config.ocr_allow_model_download,
            },
            "document_vl": {
                "enabled": self.config.document_vl_enabled,
                "available": self.document.available,
                "device": self.config.document_vl_device,
                "allow_model_download": self.config.document_vl_allow_model_download,
            },
            "general_vision": {
                "enabled": self.config.general_vision_enabled,
                "available": self.general.available,
                "endpoint_configured": bool(self.config.general_vision_endpoint),
                "model": self.config.general_vision_model,
            },
            "fallback": "explicit_unavailability",
        }
