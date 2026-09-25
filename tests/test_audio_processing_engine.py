"""
Testes unitários cobrindo gravação intermitente, limpeza de ruídos DSP e decodificação de sinais Morse.
"""

from pathlib import Path
import tempfile
import unittest

from runtime.audio_processing_engine import AudioProcessingEngine
from runtime.internal_agent_runtime import InternalAgentRuntime


class AudioProcessingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _write_wav(self, path: Path, samples: list[int], framerate: int = 8000) -> None:
        import struct
        import wave

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    def test_gravacao_de_microfone_e_declarada_indisponivel(self) -> None:
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        rec = engine.start_intermittent_recording(context_title="../aula")
        self.assertEqual(rec["status"], "indisponivel")
        self.assertNotIn("/", rec["contexto"])

        sem_arquivo = engine.stop_and_clean_recording()
        self.assertEqual(sem_arquivo["status"], "erro")

    def test_noise_gate_e_decodificacao_morse_real(self) -> None:
        import math

        framerate, unit = 8000, 480
        samples: list[int] = []

        def tone(n: int) -> None:
            samples.extend(int(8000 * math.sin(2 * math.pi * 700 * i / framerate)) for i in range(n))

        for letter in ("...", "---", "..."):
            for symbol in letter:
                tone(unit if symbol == "." else 3 * unit)
                samples.extend([0] * unit)
            samples.extend([0] * 2 * unit)
        samples.extend(int(50 * math.sin(i)) for i in range(framerate // 2))  # ruido baixo

        wav_path = self.tmp_path / "sos.wav"
        self._write_wav(wav_path, samples, framerate)

        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        result = engine.stop_and_clean_recording(wav_path)

        self.assertEqual(result["status"], "sucesso")
        self.assertTrue(Path(result["audio_limpo"]).exists())
        self.assertEqual(result["sinais_radio_detectados"]["texto_decodificado"], "SOS")
        self.assertGreater(result["limpeza_ruido"]["amostras_zeradas_pct"], 0)
        self.assertIsNone(result["transcricao_texto"])

    def test_tom_continuo_nao_vira_morse_falso(self) -> None:
        import math

        wav_path = self.tmp_path / "tom.wav"
        self._write_wav(wav_path, [int(1000 * math.sin(2 * math.pi * 440 * i / 8000)) for i in range(8000)])
        result = AudioProcessingEngine(recordings_dir=self.tmp_path).stop_and_clean_recording(wav_path)
        self.assertFalse(result["sinais_radio_detectados"]["sinal_encontrado"])

    def test_runtime_integration_of_audio_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "audio_processing_engine"))


if __name__ == "__main__":
    unittest.main()
