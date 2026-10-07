"""Testes da pilha modular de voz do JARVIS."""

from pathlib import Path
import tempfile
import unittest
import wave

from runtime.voice_engine import LocalVoiceEngine
from runtime.voice_stack import VoiceStackConfig


class FakeVoiceStack:
    def __init__(self) -> None:
        self.last_voice = None

    def synthesize(self, text, output_path, voice=None):
        self.last_voice = voice or "pm_alex"
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes((b"\x00\x01") * 240)
        return {
            "status": "sucesso",
            "arquivo_audio": str(output_path),
            "metodo": "fake-kokoro",
            "voz": self.last_voice,
            "sample_rate": 24000,
        }

    def transcribe(self, audio_path):
        return {
            "status": "sucesso",
            "arquivo_audio": str(audio_path),
            "transcricao": "Jarvis, abra o status do sistema.",
            "probabilidade_media_estimada": 0.81,
            "metodo": "fake-faster-whisper+silero-vad",
            "modelo": "small",
            "idioma": "pt",
            "probabilidade_idioma": 0.99,
            "segmentos": [{"inicio_s": 0.0, "fim_s": 1.0, "texto": "Jarvis"}],
        }

    def detect_wake_word(self, audio_path):
        return {
            "status": "sucesso",
            "detectado": True,
            "modelo": "hey_jarvis",
            "score": 0.91,
            "threshold": 0.5,
        }

    def enhance_audio(self, source, destination):
        destination.write_bytes(source.read_bytes())
        return {
            "status": "sucesso",
            "arquivo_audio": str(destination),
            "metodo": "fake-deepfilter",
        }

    def status(self):
        return {"enabled": True, "locale": "pt-BR"}


class VoiceStackTests(unittest.TestCase):
    def test_config_defaults_to_safe_disabled_local_stack(self):
        config = VoiceStackConfig.from_env(environ={}, project_root=Path("."))
        self.assertFalse(config.enabled)
        self.assertEqual(config.locale, "pt-BR")
        self.assertEqual(config.stt_backend, "faster-whisper")
        self.assertEqual(config.stt_model, "small")
        self.assertEqual(config.stt_device, "cpu")
        self.assertEqual(config.stt_compute_type, "int8")
        self.assertTrue(config.stt_vad_filter)
        self.assertFalse(config.allow_model_download)
        self.assertEqual(config.tts_backend, "kokoro-onnx")
        self.assertEqual(config.tts_voice, "pm_alex")

    def test_config_reads_voice_environment(self):
        config = VoiceStackConfig.from_env(
            environ={
                "JARVIS_VOICE_ADVANCED_ENABLED": "true",
                "JARVIS_STT_MODEL": "base",
                "JARVIS_STT_CPU_THREADS": "4",
                "JARVIS_TTS_VOICE": "pf_dora",
                "JARVIS_WAKE_WORD_ENABLED": "true",
                "JARVIS_WAKE_WORD_THRESHOLD": "0.7",
            },
            project_root=Path("."),
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.stt_model, "base")
        self.assertEqual(config.stt_cpu_threads, 4)
        self.assertEqual(config.tts_voice, "pf_dora")
        self.assertTrue(config.wake_word_enabled)
        self.assertEqual(config.wake_word_threshold, 0.7)

    def test_voice_engine_uses_real_provider_contract_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = LocalVoiceEngine(
                audio_dir=Path(temp_dir),
                voice_stack=FakeVoiceStack(),
            )
            result = engine.speak("Olá, Eron.")

            self.assertEqual(result["status"], "sucesso")
            self.assertTrue(result["audio_sintetizado"])
            self.assertTrue(result["voz_aplicada"])
            self.assertEqual(result["voz_efetiva"], "pm_alex")
            self.assertEqual(result["metodo_sintese"], "fake-kokoro")
            self.assertGreater(Path(result["arquivo_audio"]).stat().st_size, 44)

    def test_transcription_exposes_derived_confidence_as_estimate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "speech.wav"
            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes((b"\x00\x01") * 160)

            engine = LocalVoiceEngine(
                audio_dir=Path(temp_dir),
                voice_stack=FakeVoiceStack(),
            )
            result = engine.transcribe_audio(str(path))

            self.assertEqual(result["status"], "sucesso")
            self.assertEqual(result["transcricao"], "Jarvis, abra o status do sistema.")
            self.assertEqual(result["confianca"], 0.81)
            self.assertEqual(result["confianca_tipo"], "estimativa_derivada_de_avg_logprob")
            self.assertEqual(result["idioma"], "pt")

    def test_wake_word_returns_measured_score(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "wake.wav"
            path.write_bytes(b"audio")
            engine = LocalVoiceEngine(
                audio_dir=Path(temp_dir),
                voice_stack=FakeVoiceStack(),
            )

            result = engine.detect_wake_word(str(path))

            self.assertTrue(result["detectado"])
            self.assertEqual(result["score"], 0.91)
            self.assertEqual(result["threshold"], 0.5)


if __name__ == "__main__":
    unittest.main()
