"""
JARVIS - Processamento de arquivos WAV: noise gate e deteccao de codigo Morse

Responsavel por:
- aplicar um noise gate simples em WAV PCM 16-bit e medir o efeito real (RMS antes/depois)
- detectar e decodificar codigo Morse por envelope de amplitude (tom continuo on/off)
- informar com clareza o que NAO existe: captura de microfone e transcricao de fala
  dependem de backends que nao fazem parte deste projeto
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
    """Processa WAVs existentes; nao grava microfone nem transcreve fala."""

    def __init__(self, recordings_dir: Optional[Path] = None) -> None:
        self.recordings_dir = Path(recordings_dir) if recordings_dir else DEFAULT_RECORDINGS_DIR
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.is_recording = False
        self.current_recording_id: Optional[str] = None

    def start_intermittent_recording(self, context_title: str = "aula_professor") -> Dict[str, Any]:
        """Captura de microfone nao esta disponivel: informa em vez de fingir que grava."""

        return {
            "status": "indisponivel",
            "contexto": re.sub(r"[^A-Za-z0-9_-]", "_", context_title)[:40],
            "motivo": (
                "Captura de microfone nao implementada neste servidor. Grave o audio no aparelho "
                "e envie o arquivo WAV para processamento."
            ),
            "diretorio_de_entrada": str(self.recordings_dir),
        }

    def stop_and_clean_recording(
        self,
        audio_file_path: Optional[str | Path] = None,
        noise_reduction_level: float = 0.8,
    ) -> Dict[str, Any]:
        """Aplica noise gate e deteccao de Morse sobre um WAV existente."""

        now = datetime.now(timezone.utc).isoformat()
        self.is_recording = False
        if audio_file_path is None:
            candidates = sorted(
                (p for p in self.recordings_dir.glob("*.wav") if not p.name.startswith("clean_")),
                key=lambda p: p.stat().st_mtime,
            )
            if not candidates:
                return {"status": "erro", "motivo": "Nenhum arquivo WAV disponivel para processar.", "concluido_em": now}
            path = candidates[-1]
        else:
            path = Path(audio_file_path)
        if not path.is_file():
            return {"status": "erro", "motivo": f"Arquivo nao encontrado: {path.name}", "concluido_em": now}

        try:
            samples, framerate, n_channels = self._read_pcm16_mono(path)
        except ValueError as exc:
            return {"status": "erro", "motivo": str(exc), "concluido_em": now}

        level = min(max(float(noise_reduction_level), 0.0), 1.0)
        clean_file_path = self.recordings_dir / f"clean_{path.name}"
        gate_stats = self._apply_noise_gate(samples, framerate, clean_file_path, level)

        return {
            "status": "sucesso",
            "audio_original": str(path),
            "audio_limpo": str(clean_file_path),
            "canais_originais": n_channels,
            "limpeza_ruido": gate_stats,
            "sinais_radio_detectados": self._detect_and_decode_morse(samples, framerate),
            "transcricao_texto": None,
            "transcricao_status": "indisponivel: nenhum motor de reconhecimento de fala instalado",
            "concluido_em": now,
        }

    @staticmethod
    def _read_pcm16_mono(path: Path) -> tuple[List[int], int, int]:
        try:
            with wave.open(str(path), "rb") as wf_in:
                n_channels = wf_in.getnchannels()
                sampwidth = wf_in.getsampwidth()
                framerate = wf_in.getframerate()
                raw_frames = wf_in.readframes(wf_in.getnframes())
        except (wave.Error, EOFError) as exc:
            raise ValueError(f"WAV invalido: {exc}") from exc
        if sampwidth != 2:
            raise ValueError("Somente WAV PCM 16-bit e suportado.")
        count = len(raw_frames) // 2
        interleaved = struct.unpack(f"<{count}h", raw_frames[: count * 2])
        return list(interleaved[::n_channels]), framerate, n_channels

    @staticmethod
    def _rms(samples: List[int]) -> float:
        return math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0.0

    def _apply_noise_gate(self, samples: List[int], framerate: int, dst_path: Path, level: float) -> Dict[str, Any]:
        """Zera amostras abaixo de um limiar relativo ao pico; mede o efeito real."""

        peak = max((abs(s) for s in samples), default=0)
        threshold = int(peak * 0.05 * level)
        cleaned = [s if abs(s) > threshold else 0 for s in samples]
        with wave.open(str(dst_path), "wb") as wf_out:
            wf_out.setnchannels(1)
            wf_out.setsampwidth(2)
            wf_out.setframerate(framerate)
            wf_out.writeframes(struct.pack(f"<{len(cleaned)}h", *cleaned))
        zeroed = sum(1 for before, after in zip(samples, cleaned) if before != after)
        return {
            "metodo": "noise_gate_por_amplitude",
            "limiar_amostra": threshold,
            "amostras_zeradas_pct": round(100.0 * zeroed / len(samples), 2) if samples else 0.0,
            "rms_antes": round(self._rms(samples), 1),
            "rms_depois": round(self._rms(cleaned), 1),
        }

    def _detect_and_decode_morse(self, samples: List[int], framerate: int) -> Dict[str, Any]:
        """Detecta pulsos on/off no envelope e decodifica Morse quando o padrao e plausivel."""

        window = max(1, framerate // 100)  # 10 ms
        envelope = [
            sum(abs(s) for s in samples[i:i + window]) / window
            for i in range(0, len(samples) - window + 1, window)
        ]
        not_found = {"sinal_encontrado": False, "tipo_sinal": None, "codigo_morse_raw": "", "texto_decodificado": ""}
        if not envelope or max(envelope) < 200:
            return not_found

        threshold = max(envelope) * 0.5
        runs: List[tuple[bool, int]] = []
        for value in envelope:
            on = value >= threshold
            if runs and runs[-1][0] == on:
                runs[-1] = (on, runs[-1][1] + 1)
            else:
                runs.append((on, 1))
        while runs and not runs[0][0]:
            runs.pop(0)
        while runs and not runs[-1][0]:
            runs.pop()
        on_lengths = sorted(length for on, length in runs if on)
        if len(on_lengths) < 3:
            return not_found

        unit = on_lengths[max(0, len(on_lengths) // 4 - 1)]
        dots = [n for n in on_lengths if n < 2 * unit]
        dashes = [n for n in on_lengths if n >= 2 * unit]
        if dashes and not (2.0 <= (sorted(dashes)[len(dashes) // 2] / max(unit, 1)) <= 4.5):
            return not_found

        symbols = []
        for on, length in runs:
            if on:
                symbols.append("." if length < 2 * unit else "-")
            elif length >= 5 * unit:
                symbols.append(" / ")
            elif length >= 2 * unit:
                symbols.append(" ")
        raw = "".join(symbols).strip()
        words = [w.split() for w in raw.split(" / ")]
        decoded_letters = [MORSE_CODE_DICT.get(code, "?") for word in words for code in word]
        if not decoded_letters or decoded_letters.count("?") / len(decoded_letters) > 0.2:
            return not_found
        text = " ".join("".join(MORSE_CODE_DICT.get(code, "?") for code in word) for word in words)
        return {
            "sinal_encontrado": True,
            "tipo_sinal": "codigo_morse",
            "unidade_ms": unit * 10,
            "codigo_morse_raw": raw,
            "texto_decodificado": text,
        }
