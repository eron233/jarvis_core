"""
JARVIS - Stack de Voz Modular

Camada opcional e local-first para:
- STT com faster-whisper + Silero VAD integrado
- TTS leve em pt-BR com Kokoro ONNX
- wake word com openWakeWord
- enhancement opcional com DeepFilterNet

Todos os backends sao lazy e falham de forma explicita. O runtime principal
continua funcional sem as dependencias opcionais.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class VoiceStackConfig:
    """Configuracao da pilha de voz local."""

    enabled: bool = False
    locale: str = "pt-BR"
    stt_backend: str = "faster-whisper"
    stt_model: str = "small"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_cpu_threads: int = 0
    stt_beam_size: int = 5
    stt_language: str = "pt"
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 500
    allow_model_download: bool = False

    tts_backend: str = "kokoro-onnx"
    tts_voice: str = "pm_alex"
    kokoro_model_path: Optional[Path] = None
    kokoro_voices_path: Optional[Path] = None
    tts_speed: float = 1.0

    wake_word_enabled: bool = False
    wake_word_model_path: Optional[Path] = None
    wake_word_threshold: float = 0.5
    wake_word_vad_threshold: float = 0.5

    enhancement_enabled: bool = False
    deepfilter_model: Optional[str] = None
    deepfilter_command: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "VoiceStackConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)

        def optional_path(name: str) -> Optional[Path]:
            raw = (env.get(name) or "").strip()
            if not raw:
                return None
            path = Path(raw)
            return path if path.is_absolute() else root / path

        return cls(
            enabled=_env_bool(env.get("JARVIS_VOICE_ADVANCED_ENABLED"), False),
            locale=(env.get("JARVIS_VOICE_LOCALE") or "pt-BR").strip(),
            stt_backend=(env.get("JARVIS_STT_BACKEND") or "faster-whisper").strip(),
            stt_model=(env.get("JARVIS_STT_MODEL") or "small").strip(),
            stt_device=(env.get("JARVIS_STT_DEVICE") or "cpu").strip(),
            stt_compute_type=(env.get("JARVIS_STT_COMPUTE_TYPE") or "int8").strip(),
            stt_cpu_threads=max(0, int(env.get("JARVIS_STT_CPU_THREADS", "0"))),
            stt_beam_size=max(1, int(env.get("JARVIS_STT_BEAM_SIZE", "5"))),
            stt_language=(env.get("JARVIS_STT_LANGUAGE") or "pt").strip(),
            stt_vad_filter=_env_bool(env.get("JARVIS_STT_VAD_FILTER"), True),
            stt_vad_min_silence_ms=max(
                0, int(env.get("JARVIS_STT_VAD_MIN_SILENCE_MS", "500"))
            ),
            allow_model_download=_env_bool(
                env.get("JARVIS_VOICE_ALLOW_MODEL_DOWNLOAD"), False
            ),
            tts_backend=(env.get("JARVIS_TTS_BACKEND") or "kokoro-onnx").strip(),
            tts_voice=(env.get("JARVIS_TTS_VOICE") or "pm_alex").strip(),
            kokoro_model_path=optional_path("JARVIS_KOKORO_MODEL_PATH"),
            kokoro_voices_path=optional_path("JARVIS_KOKORO_VOICES_PATH"),
            tts_speed=max(0.25, min(4.0, float(env.get("JARVIS_TTS_SPEED", "1.0")))),
            wake_word_enabled=_env_bool(env.get("JARVIS_WAKE_WORD_ENABLED"), False),
            wake_word_model_path=optional_path("JARVIS_WAKE_WORD_MODEL_PATH"),
            wake_word_threshold=max(
                0.0, min(1.0, float(env.get("JARVIS_WAKE_WORD_THRESHOLD", "0.5")))
            ),
            wake_word_vad_threshold=max(
                0.0, min(1.0, float(env.get("JARVIS_WAKE_WORD_VAD_THRESHOLD", "0.5")))
            ),
            enhancement_enabled=_env_bool(
                env.get("JARVIS_AUDIO_ENHANCEMENT_ENABLED"), False
            ),
            deepfilter_model=(env.get("JARVIS_DEEPFILTER_MODEL") or "").strip() or None,
            deepfilter_command=(env.get("JARVIS_DEEPFILTER_COMMAND") or "").strip() or None,
        )


class FasterWhisperSTT:
    """Transcricao local com CTranslate2 e Silero VAD integrado."""

    def __init__(self, config: VoiceStackConfig) -> None:
        self.config = config
        self._model: Any = None
        self._load_error: Optional[str] = None

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            from faster_whisper import WhisperModel

            kwargs: Dict[str, Any] = {
                "device": self.config.stt_device,
                "compute_type": self.config.stt_compute_type,
                "local_files_only": not self.config.allow_model_download,
            }
            if self.config.stt_cpu_threads > 0:
                kwargs["cpu_threads"] = self.config.stt_cpu_threads

            self._model = WhisperModel(self.config.stt_model, **kwargs)
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    @property
    def available(self) -> bool:
        return self.config.enabled and self.config.stt_backend == "faster-whisper" and (
            importlib.util.find_spec("faster_whisper") is not None
        )

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "motivo": "faster-whisper nao esta instalado ou a voz avancada esta desativada.",
            }
        if not self._load():
            return {"status": "indisponivel", "motivo": self._load_error}

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=self.config.stt_language or None,
                beam_size=self.config.stt_beam_size,
                vad_filter=self.config.stt_vad_filter,
                vad_parameters={
                    "min_silence_duration_ms": self.config.stt_vad_min_silence_ms,
                }
                if self.config.stt_vad_filter
                else None,
                condition_on_previous_text=False,
            )
            segments = list(segments_iter)
            text = " ".join(
                str(segment.text).strip()
                for segment in segments
                if str(segment.text).strip()
            ).strip()
            if not text:
                return {
                    "status": "sem_fala",
                    "transcricao": None,
                    "metodo": "faster-whisper+silero-vad"
                    if self.config.stt_vad_filter
                    else "faster-whisper",
                    "idioma": getattr(info, "language", self.config.stt_language),
                    "probabilidade_idioma": getattr(info, "language_probability", None),
                    "segmentos": [],
                }

            segment_payload = []
            log_probs = []
            for segment in segments:
                avg_logprob = getattr(segment, "avg_logprob", None)
                if avg_logprob is not None:
                    log_probs.append(float(avg_logprob))
                segment_payload.append(
                    {
                        "inicio_s": float(segment.start),
                        "fim_s": float(segment.end),
                        "texto": str(segment.text).strip(),
                        "avg_logprob": None if avg_logprob is None else float(avg_logprob),
                    }
                )

            probability_estimate = None
            if log_probs:
                probability_estimate = round(
                    max(0.0, min(1.0, math.exp(sum(log_probs) / len(log_probs)))),
                    4,
                )

            return {
                "status": "sucesso",
                "transcricao": text,
                "metodo": "faster-whisper+silero-vad"
                if self.config.stt_vad_filter
                else "faster-whisper",
                "modelo": self.config.stt_model,
                "idioma": getattr(info, "language", self.config.stt_language),
                "probabilidade_idioma": getattr(info, "language_probability", None),
                "probabilidade_media_estimada": probability_estimate,
                "segmentos": segment_payload,
            }
        except Exception as exc:
            return {
                "status": "erro",
                "motivo": f"Falha real na transcricao: {exc.__class__.__name__}: {exc}",
            }


class KokoroOnnxTTS:
    """Sintese pt-BR leve usando Kokoro ONNX, sem download silencioso."""

    def __init__(self, config: VoiceStackConfig) -> None:
        self.config = config
        self._engine: Any = None
        self._g2p: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return (
            self.config.enabled
            and self.config.tts_backend == "kokoro-onnx"
            and importlib.util.find_spec("kokoro_onnx") is not None
            and importlib.util.find_spec("soundfile") is not None
            and importlib.util.find_spec("misaki") is not None
            and self.config.kokoro_model_path is not None
            and self.config.kokoro_voices_path is not None
            and self.config.kokoro_model_path.exists()
            and self.config.kokoro_voices_path.exists()
        )

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _load(self) -> bool:
        if self._engine is not None and self._g2p is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = (
                "Kokoro ONNX requer pacote instalado e JARVIS_KOKORO_MODEL_PATH/"
                "JARVIS_KOKORO_VOICES_PATH apontando para arquivos locais."
            )
            return False
        try:
            from kokoro_onnx import Kokoro
            from misaki.espeak import EspeakG2P

            self._engine = Kokoro(
                str(self.config.kokoro_model_path),
                str(self.config.kokoro_voices_path),
            )
            self._g2p = EspeakG2P(language="pt-br")
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def synthesize(self, text: str, output_path: Path, voice: Optional[str] = None) -> Dict[str, Any]:
        if not self._load():
            return {"status": "indisponivel", "motivo": self._load_error}
        try:
            import soundfile as sf

            phonemes, _ = self._g2p(text)
            selected_voice = voice or self.config.tts_voice
            samples, sample_rate = self._engine.create(
                phonemes,
                selected_voice,
                speed=self.config.tts_speed,
                is_phonemes=True,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), samples, sample_rate)
            return {
                "status": "sucesso",
                "arquivo_audio": str(output_path),
                "metodo": "kokoro-onnx",
                "voz": selected_voice,
                "sample_rate": int(sample_rate),
            }
        except Exception as exc:
            return {
                "status": "erro",
                "motivo": f"Falha real na sintese Kokoro: {exc.__class__.__name__}: {exc}",
            }


class OpenWakeWordDetector:
    """Deteccao de palavra de ativacao em arquivos WAV 16 kHz mono."""

    def __init__(self, config: VoiceStackConfig) -> None:
        self.config = config
        self._model: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return (
            self.config.enabled
            and self.config.wake_word_enabled
            and importlib.util.find_spec("openwakeword") is not None
            and self.config.wake_word_model_path is not None
            and self.config.wake_word_model_path.exists()
        )

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = (
                "Wake word requer openWakeWord e um modelo local em "
                "JARVIS_WAKE_WORD_MODEL_PATH."
            )
            return False
        try:
            from openwakeword.model import Model

            self._model = Model(
                wakeword_models=[str(self.config.wake_word_model_path)],
                inference_framework="onnx",
                vad_threshold=self.config.wake_word_vad_threshold,
            )
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def detect(self, audio_path: Path) -> Dict[str, Any]:
        if not self._load():
            return {
                "status": "indisponivel",
                "detectado": False,
                "motivo": self._load_error,
            }
        try:
            predictions = self._model.predict_clip(str(audio_path))
            maxima: Dict[str, float] = {}
            for frame in predictions:
                for name, score in dict(frame).items():
                    maxima[name] = max(maxima.get(name, 0.0), float(score))
            best_name = None
            best_score = 0.0
            if maxima:
                best_name, best_score = max(maxima.items(), key=lambda item: item[1])
            return {
                "status": "sucesso",
                "detectado": best_score >= self.config.wake_word_threshold,
                "modelo": best_name,
                "score": round(best_score, 6),
                "threshold": self.config.wake_word_threshold,
                "scores": maxima,
            }
        except Exception as exc:
            return {
                "status": "erro",
                "detectado": False,
                "motivo": f"Falha real no wake word: {exc.__class__.__name__}: {exc}",
            }


class DeepFilterNetEnhancer:
    """Enhancement opcional quando DeepFilterNet estiver instalado."""

    def __init__(self, config: VoiceStackConfig) -> None:
        self.config = config
        self._model: Any = None
        self._state: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        if not self.config.enabled or not self.config.enhancement_enabled:
            return False
        python_backend = importlib.util.find_spec("df") is not None
        command = self.config.deepfilter_command
        cli_backend = bool(command and (Path(command).exists() or shutil.which(command)))
        return python_backend or cli_backend

    def _load(self) -> bool:
        if self._model is not None and self._state is not None:
            return True
        if self._load_error is not None:
            return False
        if not self.available:
            self._load_error = "DeepFilterNet nao esta instalado ou enhancement esta desativado."
            return False
        try:
            from df.enhance import init_df

            model, state, _, _ = init_df(
                self.config.deepfilter_model,
                log_file=None,
            )
            self._model = model
            self._state = state
            return True
        except ValueError:
            # Versoes antigas retornam tres valores.
            try:
                from df.enhance import init_df

                model, state, _ = init_df(self.config.deepfilter_model, log_file=None)
                self._model = model
                self._state = state
                return True
            except Exception as exc:
                self._load_error = f"{exc.__class__.__name__}: {exc}"
                return False
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def enhance(self, source: Path, destination: Path) -> Dict[str, Any]:
        command = self.config.deepfilter_command
        if command and (Path(command).exists() or shutil.which(command)):
            return self._enhance_cli(source, destination, command)

        if not self._load():
            return {"status": "indisponivel", "motivo": self._load_error}
        try:
            from df.enhance import enhance, load_audio, save_audio

            audio, _ = load_audio(str(source), sr=self._state.sr())
            enhanced = enhance(self._model, self._state, audio)
            destination.parent.mkdir(parents=True, exist_ok=True)
            save_audio(str(destination), enhanced, self._state.sr())
            return {
                "status": "sucesso",
                "arquivo_audio": str(destination),
                "metodo": "DeepFilterNet-python",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "motivo": f"Falha real no enhancement: {exc.__class__.__name__}: {exc}",
            }

    def _enhance_cli(self, source: Path, destination: Path, command: str) -> Dict[str, Any]:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as temp_dir:
                args = [command]
                if self.config.deepfilter_model:
                    args += ["-m", self.config.deepfilter_model]
                args += ["-o", temp_dir, str(source)]
                process = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if process.returncode != 0:
                    return {
                        "status": "erro",
                        "motivo": "DeepFilterNet CLI retornou erro.",
                        "stderr": process.stderr[-2000:],
                    }

                candidates = sorted(
                    Path(temp_dir).glob("*.wav"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
                if not candidates:
                    return {
                        "status": "erro",
                        "motivo": "DeepFilterNet CLI concluiu sem produzir WAV verificavel.",
                    }
                shutil.copy2(candidates[0], destination)

            return {
                "status": "sucesso",
                "arquivo_audio": str(destination),
                "metodo": "DeepFilterNet-cli",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "motivo": f"Falha real no enhancement CLI: {exc.__class__.__name__}: {exc}",
            }


class VoiceStack:
    """Facade da pilha de voz local."""

    def __init__(self, config: Optional[VoiceStackConfig] = None) -> None:
        self.config = config or VoiceStackConfig.from_env()
        self.stt = FasterWhisperSTT(self.config)
        self.tts = KokoroOnnxTTS(self.config)
        self.wake_word = OpenWakeWordDetector(self.config)
        self.enhancer = DeepFilterNetEnhancer(self.config)

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        source = audio_path
        enhancement = None
        if self.config.enhancement_enabled:
            enhanced_path = audio_path.with_name(f"enhanced_{audio_path.stem}.wav")
            enhancement = self.enhancer.enhance(audio_path, enhanced_path)
            if enhancement.get("status") == "sucesso":
                source = Path(enhancement["arquivo_audio"])

        result = self.stt.transcribe(source)
        result["arquivo_audio"] = str(source)
        if enhancement is not None:
            result["enhancement"] = enhancement
        return result

    def synthesize(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.tts.synthesize(text, output_path, voice=voice)

    def detect_wake_word(self, audio_path: Path) -> Dict[str, Any]:
        return self.wake_word.detect(audio_path)

    def enhance_audio(self, source: Path, destination: Path) -> Dict[str, Any]:
        return self.enhancer.enhance(source, destination)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "locale": self.config.locale,
            "stt": {
                "backend": self.config.stt_backend,
                "model": self.config.stt_model,
                "device": self.config.stt_device,
                "compute_type": self.config.stt_compute_type,
                "package_available": importlib.util.find_spec("faster_whisper") is not None,
                "silero_vad_integrated": True,
                "allow_model_download": self.config.allow_model_download,
            },
            "tts": {
                "backend": self.config.tts_backend,
                "voice": self.config.tts_voice,
                "package_available": importlib.util.find_spec("kokoro_onnx") is not None,
                "model_configured": bool(
                    self.config.kokoro_model_path
                    and self.config.kokoro_voices_path
                    and self.config.kokoro_model_path.exists()
                    and self.config.kokoro_voices_path.exists()
                ),
            },
            "wake_word": {
                "enabled": self.config.wake_word_enabled,
                "package_available": importlib.util.find_spec("openwakeword") is not None,
                "model_configured": bool(
                    self.config.wake_word_model_path
                    and self.config.wake_word_model_path.exists()
                ),
                "threshold": self.config.wake_word_threshold,
            },
            "enhancement": {
                "enabled": self.config.enhancement_enabled,
                "deepfilternet_python_available": importlib.util.find_spec("df") is not None,
                "deepfilternet_cli_configured": bool(self.config.deepfilter_command),
            },
            "fallback": "native_system_tts_and_explicit_unavailability",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
