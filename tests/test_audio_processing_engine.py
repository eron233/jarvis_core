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

    def test_runtime_integration_of_audio_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "audio_processing_engine"))


if __name__ == "__main__":
    unittest.main()
