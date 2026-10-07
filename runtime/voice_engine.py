"""
JARVIS - Motor de Voz Local

Responsavel por:
- sintetizar fala local com backend avancado opcional e fallback do sistema
- transcrever audio local com faster-whisper + Silero VAD integrado
- detectar wake word via openWakeWord quando configurado
- expor enhancement opcional via DeepFilterNet
- nunca reportar sucesso quando um backend nao executou de verdade
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Optional

from runtime.voice_stack import VoiceStack, VoiceStackConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE_AUDIO_DIR = PROJECT_ROOT / "data" / "voice_audio"
_EMPTY_WAV = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    b"\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00"
    b"\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class LocalVoiceEngine:
    """Facade local de voz do JARVIS com degradacao graciosa."""

    def __init__(
        self,
        audio_dir: Optional[Path] = None,
        config: Optional[VoiceStackConfig] = None,
        voice_stack: Optional[VoiceStack] = None,
    ) -> None:
        self.audio_dir = Path(audio_dir) if audio_dir else DEFAULT_VOICE_AUDIO_DIR
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.voice_stack = voice_stack or VoiceStack(config=config)

    def speak(self, text: str, voice_name: str = "pt-BR-Jarvis") -> Dict[str, Any]:
        """Sintetiza texto; Kokoro local tem prioridade quando configurado."""

        now = datetime.now(timezone.utc).isoformat()
        file_id = f"speech_{int(datetime.now(timezone.utc).timestamp() * 1000)}.wav"
        output_file = self.audio_dir / file_id

        selected_voice = None
        if voice_name and voice_name != "pt-BR-Jarvis":
            selected_voice = voice_name

        advanced = self.voice_stack.synthesize(
            text=str(text),
            output_path=output_file,
            voice=selected_voice,
        )
        if advanced.get("status") == "sucesso" and output_file.exists():
            return {
                "status": "sucesso",
                "audio_sintetizado": True,
                "texto_sintetizado": str(text),
                "metodo_sintese": advanced.get("metodo"),
                "voz_solicitada": voice_name,
                "voz_aplicada": True,
                "voz_efetiva": advanced.get("voz"),
                "arquivo_audio": str(output_file),
                "sample_rate": advanced.get("sample_rate"),
                "gerado_em": now,
                "fallback_usado": False,
                "motivo": None,
            }

        native_result = self._speak_with_native_system(str(text), output_file)
        if native_result["audio_sintetizado"]:
            return {
                "status": "sucesso",
                "audio_sintetizado": True,
                "texto_sintetizado": str(text),
                "metodo_sintese": native_result["metodo"],
                "voz_solicitada": voice_name,
                "voz_aplicada": False,
                "voz_efetiva": None,
                "arquivo_audio": str(output_file),
                "gerado_em": now,
                "fallback_usado": True,
                "backend_avancado": advanced,
                "motivo": None,
            }

        if not output_file.exists():
            output_file.write_bytes(_EMPTY_WAV)

        return {
            "status": "indisponivel",
            "audio_sintetizado": False,
            "texto_sintetizado": str(text),
            "metodo_sintese": None,
            "voz_solicitada": voice_name,
            "voz_aplicada": False,
            "voz_efetiva": None,
            "arquivo_audio": str(output_file),
            "gerado_em": now,
            "fallback_usado": True,
            "backend_avancado": advanced,
            "motivo": (
                "Nenhum backend de TTS executou com sucesso. O arquivo criado e "
                "apenas um WAV vazio de compatibilidade e nao contem fala."
            ),
        }

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """Transcreve audio real; sem backend configurado, declara indisponibilidade."""

        path = Path(audio_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Arquivo de áudio {audio_path} não encontrado."}

        result = self.voice_stack.transcribe(path)
        payload = {
            "status": result.get("status", "indisponivel"),
            "arquivo_audio": result.get("arquivo_audio", str(path)),
            "transcricao": result.get("transcricao"),
            "confianca": result.get("probabilidade_media_estimada"),
            "confianca_tipo": (
                "estimativa_derivada_de_avg_logprob"
                if result.get("probabilidade_media_estimada") is not None
                else None
            ),
            "metodo": result.get("metodo"),
            "modelo": result.get("modelo"),
            "idioma": result.get("idioma"),
            "probabilidade_idioma": result.get("probabilidade_idioma"),
            "segmentos": result.get("segmentos", []),
            "motivo": result.get("motivo"),
        }
        if "enhancement" in result:
            payload["enhancement"] = result["enhancement"]
        return payload

    def detect_wake_word(self, audio_path: str) -> Dict[str, Any]:
        """Detecta a palavra de ativacao somente quando um modelo real estiver configurado."""

        path = Path(audio_path)
        if not path.exists():
            return {
                "status": "erro",
                "detectado": False,
                "motivo": f"Arquivo de áudio {audio_path} não encontrado.",
            }
        result = self.voice_stack.detect_wake_word(path)
        result["arquivo_audio"] = str(path)
        return result

    def enhance_audio(self, audio_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Aplica DeepFilterNet quando configurado."""

        source = Path(audio_path)
        if not source.exists():
            return {
                "status": "erro",
                "motivo": f"Arquivo de áudio {audio_path} não encontrado.",
            }
        destination = (
            Path(output_path)
            if output_path
            else self.audio_dir / f"enhanced_{source.stem}.wav"
        )
        return self.voice_stack.enhance_audio(source, destination)

    def describe_capabilities(self) -> Dict[str, Any]:
        """Retorna quais backends estao efetivamente configurados."""

        return self.voice_stack.status()

    @staticmethod
    def _speak_with_native_system(text: str, output_file: Path) -> Dict[str, Any]:
        """Fallback nativo, usado somente quando o backend local avancado falha."""

        try:
            if sys.platform == "win32":
                clean_text = text.replace("'", "''")
                clean_path = str(output_file).replace("'", "''")
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$synth.SetOutputToWaveFile('{clean_path}'); "
                    f"$synth.Speak('{clean_text}'); "
                    "$synth.Dispose()"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    timeout=20,
                )
                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 44:
                    return {"audio_sintetizado": True, "metodo": "windows_sapi"}

            elif sys.platform == "darwin":
                result = subprocess.run(
                    [
                        "say",
                        "-o",
                        str(output_file),
                        "--data-format=LEI16@22050",
                        text,
                    ],
                    capture_output=True,
                    timeout=20,
                )
                if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 44:
                    return {"audio_sintetizado": True, "metodo": "macos_say"}
        except Exception:
            pass

        return {"audio_sintetizado": False, "metodo": None}
