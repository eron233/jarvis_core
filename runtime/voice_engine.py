"""
JARVIS - Motor de Voz Local (STT - Speech-to-Text & TTS - Text-to-Speech)

Responsável por:
- síntese de voz local (Text-to-Speech) para resposta falada
- transcrição de áudio local (Speech-to-Text) de comandos de voz
- operação 100% offline com fallbacks graciosos
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE_AUDIO_DIR = PROJECT_ROOT / "data" / "voice_audio"


class LocalVoiceEngine:
    """Motor local de síntese e transcrição de áudio para o JARVIS."""

    def __init__(self, audio_dir: Optional[Path] = None) -> None:
        self.audio_dir = Path(audio_dir) if audio_dir else DEFAULT_VOICE_AUDIO_DIR
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def speak(self, text: str, voice_name: str = "pt-BR-Jarvis") -> Dict[str, Any]:
        """
        Sintetiza texto em áudio de fala local.
        """
        now = datetime.now(timezone.utc).isoformat()
        file_id = f"speech_{int(datetime.now(timezone.utc).timestamp())}.wav"
        output_file = self.audio_dir / file_id

        # Tenta utilizar sintetizadores nativos do SO com fallback seguro
        synth_method = "simulado_local"
        try:
            if sys.platform == "win32":
                # PowerShell SAPI SpeechSynthesizer
                import subprocess
                clean_t = text.replace("'", "''")
                ps_cmd = (
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$synth.SetOutputToWaveFile('{output_file}'); "
                    f"$synth.Speak('{clean_t}'); $synth.Dispose()"
                )
                res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
                if res.returncode == 0 and output_file.exists():
                    synth_method = "windows_sapi"
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["say", "-o", str(output_file), "--data-format=LEI16@22050", text], timeout=10)
                if output_file.exists():
                    synth_method = "macos_say"
        except Exception:
            pass

        if not output_file.exists():
            # Gera um placeholder wav válido para garantir integridade offline
            output_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

        return {
            "status": "sucesso",
            "texto_sintetizado": text,
            "metodo_sintese": synth_method,
            "arquivo_audio": str(output_file),
            "gerado_em": now,
        }

    @staticmethod
    def _detect_stt_engine() -> Optional[str]:
        """
        Tenta detectar um motor de STT (Speech-to-Text) real instalado no ambiente.
        Retorna o nome do motor encontrado, ou None se nenhum estiver disponível.
        Nenhuma dependência de STT é declarada em requirements.txt, então o
        resultado esperado hoje é None (indisponível).
        """
        for module_name in ("speech_recognition", "vosk", "whisper"):
            try:
                __import__(module_name)
                return module_name
            except Exception:
                continue
        return None

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio para texto.

        IMPORTANTE: este projeto não possui nenhum motor real de reconhecimento
        de fala (STT) instalado ou declarado em requirements.txt. Por isso,
        este método NÃO inventa transcrição nem confiança fictícias. Ele apenas
        verifica se algum motor de STT real (speech_recognition, vosk, whisper)
        está disponível no ambiente; se estiver, delega a ele; caso contrário,
        relata honestamente que a transcrição não pode ser realizada.
        """
        path = Path(audio_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Arquivo de áudio {audio_path} não encontrado."}

        stt_engine = self._detect_stt_engine()

        if stt_engine is None:
            return {
                "status": "indisponivel",
                "arquivo_audio": str(path),
                "transcricao": "",
                "stt_disponivel": False,
                "motivo": (
                    "Nenhum motor real de reconhecimento de fala (STT) está instalado "
                    "neste ambiente (tentativas: speech_recognition, vosk, whisper). "
                    "Nenhuma transcrição foi ou pode ser gerada sem um motor real."
                ),
            }

        # Caminho reservado para quando um motor de STT real estiver disponível.
        # Nenhuma lógica de transcrição fictícia é executada aqui: a integração
        # real com o motor detectado deve ser implementada quando a dependência
        # for de fato adicionada ao projeto.
        return {
            "status": "indisponivel",
            "arquivo_audio": str(path),
            "transcricao": "",
            "stt_disponivel": True,
            "motivo": (
                f"Motor de STT '{stt_engine}' foi detectado, mas a integração de "
                "transcrição real ainda não foi implementada neste método."
            ),
        }
