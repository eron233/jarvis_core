"""
JARVIS - Processamento de Audio

Responsavel por:
- capturar microfone local quando sounddevice estiver disponivel
- aplicar enhancement real via VoiceStack/DeepFilterNet quando configurado
- manter um noise-gate DSP simples como fallback mensuravel
- enviar o audio resultante para o STT real
- declarar explicitamente capacidades de sinal/radio ainda indisponiveis
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import math
from pathlib import Path
import struct
from threading import Lock
import wave
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "data" / "audio_recordings"


class MicrophoneRecorder:
    """Captura PCM 16-bit real via sounddevice sem bloquear o runtime."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, blocksize: int = 1280) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self._stream: Any = None
        self._frames: List[bytes] = []
        self._lock = Lock()
        self._output_path: Optional[Path] = None
        self._error: Optional[str] = None

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("sounddevice") is not None

    @property
    def active(self) -> bool:
        return self._stream is not None

    def start(self, output_path: Path) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "motivo": "sounddevice nao esta instalado; captura de microfone nao foi iniciada.",
            }
        if self.active:
            return {"status": "erro", "motivo": "Ja existe uma captura de microfone ativa."}

        try:
            import sounddevice as sd

            self._frames = []
            self._output_path = Path(output_path)
            self._error = None

            def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    self._error = str(status)
                with self._lock:
                    self._frames.append(indata.copy().tobytes())

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.blocksize,
                callback=callback,
            )
            self._stream.start()
            return {
                "status": "gravando",
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "arquivo_destino": str(self._output_path),
            }
        except Exception as exc:
            self._stream = None
            return {
                "status": "erro",
                "motivo": f"Falha real ao abrir microfone: {exc.__class__.__name__}: {exc}",
            }

    def stop(self) -> Dict[str, Any]:
        if self._stream is None or self._output_path is None:
            return {"status": "erro", "motivo": "Nenhuma captura real esta ativa."}

        try:
            self._stream.stop()
            self._stream.close()
        except Exception as exc:
            self._stream = None
            return {
                "status": "erro",
                "motivo": f"Falha ao encerrar microfone: {exc.__class__.__name__}: {exc}",
            }
        finally:
            self._stream = None

        with self._lock:
            frames = list(self._frames)
        if not frames:
            return {
                "status": "erro",
                "motivo": "O microfone abriu, mas nenhuma amostra foi capturada.",
            }

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(self._output_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(b"".join(frames))

        return {
            "status": "sucesso",
            "arquivo_audio": str(self._output_path),
            "bytes_pcm": sum(len(frame) for frame in frames),
            "aviso_dispositivo": self._error,
        }


class AudioProcessingEngine:
    """Captura, limpa e encaminha audio para os backends reais de voz."""

    def __init__(
        self,
        recordings_dir: Optional[Path] = None,
        voice_engine: Any = None,
        recorder: Optional[MicrophoneRecorder] = None,
    ) -> None:
        self.recordings_dir = Path(recordings_dir) if recordings_dir else DEFAULT_RECORDINGS_DIR
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.voice_engine = voice_engine
        self.recorder = recorder or MicrophoneRecorder()
        self.is_recording = False
        self.current_recording_id: Optional[str] = None

    def start_intermittent_recording(self, context_title: str = "aula_professor") -> Dict[str, Any]:
        """Inicia uma captura real do microfone quando o backend esta disponivel."""

        now = datetime.now(timezone.utc).isoformat()
        safe_context = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in str(context_title)
        )[:80]
        file_id = f"recording_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{safe_context}.wav"
        output_file = self.recordings_dir / file_id

        result = self.recorder.start(output_file)
        if result.get("status") == "gravando":
            self.is_recording = True
            self.current_recording_id = file_id
            result.update({"contexto": context_title, "iniciado_em": now})
            return result

        self.is_recording = False
        self.current_recording_id = None
        result.update({"contexto": context_title, "iniciado_em": now})
        return result

    def stop_and_clean_recording(
        self,
        audio_file_path: Optional[str | Path] = None,
        noise_reduction_level: float = 0.8,
    ) -> Dict[str, Any]:
        """Finaliza captura ou processa um arquivo existente, sem fabricar audio."""

        now = datetime.now(timezone.utc).isoformat()
        capture_result: Optional[Dict[str, Any]] = None

        if audio_file_path is None and self.is_recording:
            capture_result = self.recorder.stop()
            self.is_recording = False
            if capture_result.get("status") != "sucesso":
                return {
                    "status": "erro",
                    "captura": capture_result,
                    "concluido_em": now,
                }
            path = Path(capture_result["arquivo_audio"])
        elif audio_file_path is not None:
            path = Path(audio_file_path)
            self.is_recording = False
        elif self.current_recording_id:
            path = self.recordings_dir / self.current_recording_id
            self.is_recording = False
        else:
            return {
                "status": "erro",
                "motivo": "Nenhuma gravacao real ou arquivo de audio foi fornecido.",
                "concluido_em": now,
            }

        if not path.exists():
            return {
                "status": "erro",
                "motivo": f"Arquivo de audio nao encontrado: {path}",
                "concluido_em": now,
            }

        clean_file_path = self.recordings_dir / f"clean_{path.name}"
        enhancement_result = None

        if self.voice_engine is not None:
            try:
                enhancement_result = self.voice_engine.enhance_audio(
                    str(path),
                    str(clean_file_path),
                )
            except Exception as exc:
                enhancement_result = {
                    "status": "erro",
                    "motivo": f"Falha ao chamar enhancement: {exc.__class__.__name__}: {exc}",
                }

        if enhancement_result and enhancement_result.get("status") == "sucesso":
            processed_stats = {
                "metodo": enhancement_result.get("metodo", "DeepFilterNet"),
                "snr_improvement_db": None,
                "rms_change_db": None,
                "medicao_snr_disponivel": False,
            }
        else:
            processed_stats = self._apply_dsp_noise_gate(
                path,
                clean_file_path,
                noise_reduction_level,
            )

        signal_decoding = self._detect_and_decode_radio_signals(path)

        transcription = {
            "status": "indisponivel",
            "transcricao": None,
            "motivo": "Nenhum motor de voz foi conectado ao processamento de audio.",
        }
        if self.voice_engine is not None:
            try:
                transcription = self.voice_engine.transcribe_audio(str(clean_file_path))
            except Exception as exc:
                transcription = {
                    "status": "erro",
                    "transcricao": None,
                    "motivo": f"Falha real ao chamar STT: {exc.__class__.__name__}: {exc}",
                }

        return {
            "status": "sucesso",
            "captura": capture_result,
            "audio_original": str(path),
            "audio_limpo": str(clean_file_path),
            "limpeza_ruido": {
                **processed_stats,
                "nivel_solicitado": max(0.0, min(1.0, float(noise_reduction_level))),
                "enhancement_backend": enhancement_result,
            },
            "sinais_radio_detectados": signal_decoding,
            "transcricao": {
                "disponivel": transcription.get("status") == "sucesso",
                "texto": transcription.get("transcricao"),
                "status": transcription.get("status"),
                "metodo": transcription.get("metodo"),
                "modelo": transcription.get("modelo"),
                "confianca": transcription.get("confianca"),
                "motivo": transcription.get("motivo"),
            },
            "concluido_em": now,
        }

    def _apply_dsp_noise_gate(
        self,
        src_path: Path,
        dst_path: Path,
        reduction_level: float,
    ) -> Dict[str, Any]:
        """Aplica noise gate simples e mede apenas o que pode ser medido sem referencia limpa."""

        reduction = max(0.0, min(1.0, float(reduction_level)))
        try:
            with wave.open(str(src_path), "rb") as wf_in:
                n_channels = wf_in.getnchannels()
                sampwidth = wf_in.getsampwidth()
                framerate = wf_in.getframerate()
                n_frames = wf_in.getnframes()
                raw_frames = wf_in.readframes(n_frames)

            if sampwidth != 2:
                dst_path.write_bytes(src_path.read_bytes())
                return {
                    "metodo": "copy_unsupported_pcm_width",
                    "snr_improvement_db": None,
                    "rms_change_db": None,
                    "medicao_snr_disponivel": False,
                    "motivo": "Noise gate suporta PCM 16-bit; arquivo foi preservado sem alegar limpeza.",
                }

            samples = struct.unpack(f"<{len(raw_frames) // 2}h", raw_frames)
            threshold = int(500 * reduction)
            cleaned_samples = [sample if abs(sample) >= threshold else 0 for sample in samples]
            cleaned_bytes = struct.pack(f"<{len(cleaned_samples)}h", *cleaned_samples)

            with wave.open(str(dst_path), "wb") as wf_out:
                wf_out.setnchannels(n_channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                wf_out.writeframes(cleaned_bytes)

            before_rms = self._rms(samples)
            after_rms = self._rms(cleaned_samples)
            rms_change_db = None
            if before_rms > 0 and after_rms > 0:
                rms_change_db = round(20.0 * math.log10(after_rms / before_rms), 4)
            elif before_rms > 0 and after_rms == 0:
                rms_change_db = float("-inf")

            return {
                "metodo": "measured_amplitude_noise_gate",
                "snr_improvement_db": None,
                "rms_change_db": rms_change_db,
                "medicao_snr_disponivel": False,
                "motivo": (
                    "SNR nao pode ser calculado honestamente sem referencia de fala limpa; "
                    "rms_change_db mede somente a mudanca de energia do sinal."
                ),
            }
        except Exception as exc:
            dst_path.write_bytes(src_path.read_bytes())
            return {
                "metodo": "copy_on_processing_error",
                "snr_improvement_db": None,
                "rms_change_db": None,
                "medicao_snr_disponivel": False,
                "motivo": f"Noise gate falhou e o audio foi preservado: {exc.__class__.__name__}: {exc}",
            }

    @staticmethod
    def _rms(samples: List[int] | tuple[int, ...]) -> float:
        if not samples:
            return 0.0
        return math.sqrt(sum(float(sample) ** 2 for sample in samples) / len(samples))

    def _detect_and_decode_radio_signals(self, path: Path) -> Dict[str, Any]:
        """Nao afirma demodulacao enquanto nao existir um backend real."""

        return {
            "sinal_encontrado": False,
            "analise_disponivel": False,
            "tipo_sinal": None,
            "frequencia_sinal_hz": None,
            "codigo_morse_raw": None,
            "texto_decodificado": None,
            "motivo": (
                "A deteccao de sinais de radio nao esta implementada. Nenhum sinal foi "
                "procurado neste audio; a ausencia aqui nao significa ausencia de sinal."
            ),
        }

    def describe_capabilities(self) -> Dict[str, Any]:
        return {
            "microfone": {
                "backend": "sounddevice",
                "package_available": self.recorder.available,
                "active": self.recorder.active,
            },
            "voice_engine_connected": self.voice_engine is not None,
            "fallback_dsp": "measured_amplitude_noise_gate",
            "radio_signal_decoder": "indisponivel",
        }
