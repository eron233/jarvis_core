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

    def test_intermittent_recording_and_dsp_cleaning(self) -> None:
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)

        rec = engine.start_intermittent_recording(context_title="aula_teste")
        self.assertEqual(rec["status"], "gravando")
        self.assertTrue(engine.is_recording)

        clean = engine.stop_and_clean_recording(noise_reduction_level=0.8)
        self.assertEqual(clean["status"], "sucesso")
        self.assertFalse(engine.is_recording)
        self.assertTrue(Path(clean["audio_limpo"]).exists())
        self.assertIn("sinais_radio_detectados", clean)

    def test_morse_round_trip_decodes_real_text(self) -> None:
        """Gera um WAV de Morse real para 'SOS' e verifica que a decodificação bate."""
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        wav_path = self.tmp_path / "morse_sos.wav"
        engine.generate_morse_wav("SOS", wav_path)

        result = engine._detect_and_decode_radio_signals(wav_path)

        self.assertTrue(result["sinal_encontrado"])
        self.assertEqual(result["texto_decodificado"].replace(" ", ""), "SOS")

    def test_morse_round_trip_jarvis(self) -> None:
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        wav_path = self.tmp_path / "morse_jarvis.wav"
        engine.generate_morse_wav("JARVIS", wav_path)

        result = engine._detect_and_decode_radio_signals(wav_path)

        self.assertTrue(result["sinal_encontrado"])
        self.assertEqual(result["texto_decodificado"].replace(" ", ""), "JARVIS")

    def test_silence_audio_has_no_signal_found(self) -> None:
        """Áudio de silêncio puro não deve inventar nenhum sinal Morse."""
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        silence_path = self.tmp_path / "silencio.wav"

        framerate = 8000
        n_samples = framerate  # 1 segundo de silêncio total
        import struct
        import wave as wave_module

        with wave_module.open(str(silence_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))

        result = engine._detect_and_decode_radio_signals(silence_path)
        self.assertFalse(result["sinal_encontrado"])
        self.assertEqual(result["texto_decodificado"], "")

    def test_transcricao_is_honest_placeholder(self) -> None:
        """O campo de transcrição de fala não deve alegar precisão falsa (sem STT real)."""
        engine = AudioProcessingEngine(recordings_dir=self.tmp_path)
        engine.start_intermittent_recording(context_title="aula_teste")
        clean = engine.stop_and_clean_recording(noise_reduction_level=0.5)
        self.assertIn("PLACEHOLDER", clean["transcricao_texto"])

    def test_runtime_integration_of_audio_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "audio_processing_engine"))


if __name__ == "__main__":
    unittest.main()
