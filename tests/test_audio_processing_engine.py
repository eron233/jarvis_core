"""
Testes unitarios para captura/limpeza de audio e integracao com o runtime.
"""

from pathlib import Path
import tempfile
import unittest
import wave

from runtime.audio_processing_engine import AudioProcessingEngine
from runtime.internal_agent_runtime import InternalAgentRuntime


class FakeRecorder:
    def __init__(self) -> None:
        self.available = True
        self.active = False
        self.path = None

    def start(self, output_path: Path):
        self.active = True
        self.path = Path(output_path)
        return {
            "status": "gravando",
            "sample_rate": 16000,
            "channels": 1,
            "arquivo_destino": str(self.path),
        }

    def stop(self):
        self.active = False
        with wave.open(str(self.path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes((b"\x00\x01") * 1600)
        return {
            "status": "sucesso",
            "arquivo_audio": str(self.path),
            "bytes_pcm": 3200,
            "aviso_dispositivo": None,
        }


class FakeVoiceEngine:
    def enhance_audio(self, audio_path, output_path):
        source = Path(audio_path)
        destination = Path(output_path)
        destination.write_bytes(source.read_bytes())
        return {
            "status": "sucesso",
            "arquivo_audio": str(destination),
            "metodo": "fake-enhancer",
        }

    def transcribe_audio(self, audio_path):
        return {
            "status": "sucesso",
            "arquivo_audio": audio_path,
            "transcricao": "teste de voz real",
            "confianca": 0.8,
            "metodo": "fake-stt",
            "modelo": "test",
        }


class AudioProcessingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_real_recorder_contract_and_audio_pipeline(self) -> None:
        engine = AudioProcessingEngine(
            recordings_dir=self.tmp_path,
            voice_engine=FakeVoiceEngine(),
            recorder=FakeRecorder(),
        )

        rec = engine.start_intermittent_recording(context_title="aula_teste")
        self.assertEqual(rec["status"], "gravando")
        self.assertTrue(engine.is_recording)

        clean = engine.stop_and_clean_recording(noise_reduction_level=0.8)
        self.assertEqual(clean["status"], "sucesso")
        self.assertFalse(engine.is_recording)
        self.assertTrue(Path(clean["audio_limpo"]).exists())
        self.assertEqual(clean["limpeza_ruido"]["metodo"], "fake-enhancer")
        self.assertTrue(clean["transcricao"]["disponivel"])
        self.assertEqual(clean["transcricao"]["texto"], "teste de voz real")
        self.assertIn("sinais_radio_detectados", clean)

    def test_missing_capture_is_error_not_fake_sample(self) -> None:
        engine = AudioProcessingEngine(
            recordings_dir=self.tmp_path,
            recorder=FakeRecorder(),
        )
        result = engine.stop_and_clean_recording()
        self.assertEqual(result["status"], "erro")
        self.assertIn("Nenhuma gravacao real", result["motivo"])

    def test_runtime_integration_of_audio_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "audio_processing_engine"))
        self.assertIs(runtime.audio_processing_engine.voice_engine, runtime.voice_engine)


if __name__ == "__main__":
    unittest.main()
