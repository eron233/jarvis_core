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
        Sintetiza texto em audio de fala usando o sintetizador do sistema.

        Parametros:
        - text: texto a ser falado.
        - voice_name: voz pedida; registrada no retorno, ainda nao selecionavel.

        Retorno:
        - resultado declarando se houve sintese real ou apenas um arquivo vazio.

        Efeitos no sistema:
        - grava um arquivo WAV em `audio_dir`.

        Quando nenhum sintetizador esta disponivel, o metodo gravava um WAV com
        cabecalho valido e zero amostras — silencio — e devolvia
        `status: "sucesso"`. Quem tocasse o arquivo nao ouviria nada e nao teria
        como saber que a sintese falhou.
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

        audio_sintetizado = synth_method != "simulado_local" and output_file.exists()

        if not output_file.exists():
            # Arquivo WAV valido porem sem amostras, para que o caminho de saida
            # exista mesmo sem sintetizador. Nao contem fala.
            output_file.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

        return {
            "status": "sucesso" if audio_sintetizado else "indisponivel",
            "audio_sintetizado": audio_sintetizado,
            "texto_sintetizado": text,
            "metodo_sintese": synth_method if audio_sintetizado else None,
            "voz_solicitada": voice_name,
            "voz_aplicada": False,
            "arquivo_audio": str(output_file),
            "gerado_em": now,
            "motivo": (
                None
                if audio_sintetizado
                else (
                    "Nenhum sintetizador de fala respondeu neste sistema. O arquivo "
                    "gravado e um WAV valido sem amostras e nao contem fala."
                )
            ),
        }

    def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcreve um arquivo de áudio para texto.
        """
        path = Path(audio_path)
        if not path.exists():
            return {"status": "erro", "motivo": f"Arquivo de áudio {audio_path} não encontrado."}

        # A versao anterior devolvia sempre o texto "Jarvis status do sistema"
        # com confianca 0.98, para qualquer audio, citando um transcritor que
        # nao existe. Qualquer fluxo de voz ligado a isto executaria sempre o
        # mesmo comando, e com aparencia de alta confianca.
        return {
            "status": "indisponivel",
            "arquivo_audio": str(path),
            "transcricao": None,
            "confianca": None,
            "metodo": None,
            "motivo": (
                "Nenhum transcritor de fala esta configurado neste ambiente. "
                "O arquivo foi preservado para transcricao externa."
            ),
        }
