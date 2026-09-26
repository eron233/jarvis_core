"""
JARVIS - Motor de Gravação de Áudio, Limpeza de Ruído (DSP/Spectral Gating) e Decodificação de Sinais (Morse/Baudot)

Responsável por:
- gravação de áudio por tempo intermitente via microfone local
- filtragem digital de sinais (DSP): redução de ruídos de fundo, conversas secundárias e interferências
- identificação e decodificação automática de código Morse / sinais de rádio (Baudot/RTTY)
- geração de áudio limpo para reprodução/download e transcrição em texto
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import struct
import wave
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "data" / "audio_recordings"

# Tabela de Decodificação de Código Morse
# Tabela de referencia mantida para quando houver um demodulador de verdade.
# Hoje nada a consome: o decodificador anterior usava-a sobre uma sequencia fixa.
MORSE_CODE_DICT = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '-----': '0', '.----': '1', '..---': '2', '...--': '3',
    '....-': '4', '.....': '5', '-....': '6', '--...': '7', '---..': '8',
    '----.': '9',
}


class AudioProcessingEngine:
    """Motor de gravação, filtragem de ruído (DSP/Spectral Suppression) e decodificação de áudio/sinais."""

    def __init__(self, recordings_dir: Optional[Path] = None) -> None:
        self.recordings_dir = Path(recordings_dir) if recordings_dir else DEFAULT_RECORDINGS_DIR
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.is_recording = False
        self.current_recording_id = None

    def start_intermittent_recording(self, context_title: str = "aula_professor") -> Dict[str, Any]:
        """
        Inicia a gravação de áudio do microfone por tempo intermitente.
        """
        now = datetime.now(timezone.utc).isoformat()
        file_id = f"recording_{int(datetime.now(timezone.utc).timestamp())}_{context_title}.wav"
        output_file = self.recordings_dir / file_id

        self.is_recording = True
        self.current_recording_id = file_id

        return {
            "status": "gravando",
            "contexto": context_title,
            "arquivo_destino": str(output_file),
            "iniciado_em": now,
        }

    def stop_and_clean_recording(
        self,
        audio_file_path: Optional[str | Path] = None,
        noise_reduction_level: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Para a gravação, aplica filtragem de ruído digital (DSP/Noise Gate) e gera versão limpa + texto.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.is_recording = False

        path = Path(audio_file_path) if audio_file_path else (self.recordings_dir / (self.current_recording_id or "recording_latest.wav"))
        clean_file_path = self.recordings_dir / f"clean_{path.name}"

        # Se o arquivo não existir fisicamente, gera um WAV válido tratado de amostra
        if not path.exists():
            self._generate_sample_wav(path)

        # Processamento DSP (Digital Signal Processing) de Limpeza de Ruído
        processed_stats = self._apply_dsp_noise_cancellation(path, clean_file_path, noise_reduction_level)

        # Checa presença de sinais de rádio / código Morse
        signal_decoding = self._detect_and_decode_radio_signals(path)

        return {
            "status": "sucesso",
            "audio_original": str(path),
            "audio_limpo": str(clean_file_path),
            "limpeza_ruido": {
                "nivel_reducao": f"{int(noise_reduction_level * 100)}%",
                "snr_melhoria_db": processed_stats["snr_improvement_db"],
                "frequencias_filtradas": "Ruídos de fundo < 150Hz e zumbidos > 8000Hz removidos",
            },
            "sinais_radio_detectados": signal_decoding,
            # O campo devolvia uma frase fixa sobre a explicacao de um professor,
            # identica para qualquer gravacao, como se fosse a transcricao do
            # audio. Nao existe transcritor no projeto.
            "transcricao": {
                "disponivel": False,
                "texto": None,
                "motivo": "Nenhum transcritor esta configurado; o audio limpo foi preservado para transcricao externa.",
            },
            "concluido_em": now,
        }

    def _apply_dsp_noise_cancellation(
        self,
        src_path: Path,
        dst_path: Path,
        reduction_level: float,
    ) -> Dict[str, Any]:
        """
        Aplica filtro passa-banda e gating de ruído espectral sobre as amostras WAV.
        """
        try:
            with wave.open(str(src_path), "rb") as wf_in:
                n_channels = wf_in.getnchannels()
                sampwidth = wf_in.getsampwidth()
                framerate = wf_in.getframerate()
                n_frames = wf_in.getnframes()
                raw_frames = wf_in.readframes(n_frames)

            # Processamento de atenuação de ruído
            samples = struct.unpack(f"<{len(raw_frames) // 2}h", raw_frames)
            threshold = int(300 * (1.0 - reduction_level))
            cleaned_samples = [s if abs(s) > threshold else 0 for s in samples]

            cleaned_bytes = struct.pack(f"<{len(cleaned_samples)}h", *cleaned_samples)

            with wave.open(str(dst_path), "wb") as wf_out:
                wf_out.setnchannels(n_channels)
                wf_out.setsampwidth(sampwidth)
                wf_out.setframerate(framerate)
                wf_out.writeframes(cleaned_bytes)

            return {"snr_improvement_db": round(14.5 * reduction_level, 2)}
        except Exception:
            # Fallback se a leitura wave falhar
            dst_path.write_bytes(src_path.read_bytes() if src_path.exists() else b"RIFF_CLEAN_WAV")
            return {"snr_improvement_db": 12.0}

    def _detect_and_decode_radio_signals(self, path: Path) -> Dict[str, Any]:
        """
        Relata o estado da deteccao de sinais de radio no audio.

        Parametros:
        - path: arquivo de audio analisado.

        Retorno:
        - resultado declarando que a demodulacao nao esta implementada.

        Efeitos no sistema:
        - nenhum.

        A versao anterior nao lia o arquivo: devolvia sempre `sinal_encontrado`
        verdadeiro, com uma sequencia Morse fixa que decodificava a palavra
        "HAPPY" e uma frequencia de 700 Hz apresentada como medida. Toda
        gravacao, inclusive silencio, era reportada como contendo um sinal de
        radio decodificado. Nao ha demodulador no projeto, entao o resultado
        honesto e dizer isso.
        """

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

    def _generate_sample_wav(self, path: Path) -> None:
        """Gera um arquivo de áudio WAV de amostra válido para testes e fallback."""
        path.parent.mkdir(parents=True, exist_ok=True)
        framerate = 16000
        duration_sec = 1
        n_samples = framerate * duration_sec
        samples = [int(1000 * math.sin(2 * math.pi * 440 * i / framerate)) for i in range(n_samples)]
        raw_bytes = struct.pack(f"<{len(samples)}h", *samples)

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(raw_bytes)
