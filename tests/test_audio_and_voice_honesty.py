"""Testes de que audio e voz nao inventam resultados que nao produziram."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.audio_processing_engine import AudioProcessingEngine
from runtime.voice_engine import LocalVoiceEngine


class AudioProcessingHonestyTests(unittest.TestCase):
    """O motor de audio limpa o som de verdade, mas nao transcreve nem demodula."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.engine = AudioProcessingEngine(recordings_dir=self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def limpar(self) -> dict:
        """Grava e limpa um audio de amostra."""

        self.engine.start_intermittent_recording(context_title="aula_teste")
        return self.engine.stop_and_clean_recording(noise_reduction_level=0.8)

    def test_nao_devolve_transcricao_inventada(self) -> None:
        """
        O campo trazia sempre a mesma frase sobre a explicacao de um professor,
        identica para qualquer gravacao, apresentada como transcricao do audio.
        """

        resultado = self.limpar()

        self.assertFalse(resultado["transcricao"]["disponivel"])
        self.assertIsNone(resultado["transcricao"]["texto"])
        self.assertIn("transcritor", resultado["transcricao"]["motivo"])

    def test_nao_afirma_ter_encontrado_sinal_de_radio(self) -> None:
        """
        O decodificador nao lia o arquivo: devolvia sempre sinal encontrado,
        com Morse fixo decodificando "HAPPY" e 700 Hz como se fossem medidos.
        """

        sinais = self.limpar()["sinais_radio_detectados"]

        self.assertFalse(sinais["sinal_encontrado"])
        self.assertFalse(sinais["analise_disponivel"])
        self.assertIsNone(sinais["texto_decodificado"])
        self.assertIsNone(sinais["frequencia_sinal_hz"])

    def test_declara_que_a_ausencia_nao_prova_ausencia(self) -> None:
        """Nao procurar nao e o mesmo que nao haver; o motivo precisa dizer isso."""

        sinais = self.limpar()["sinais_radio_detectados"]

        self.assertIn("nao significa ausencia", sinais["motivo"])

    def test_limpeza_de_ruido_continua_real(self) -> None:
        """O processamento DSP e genuino e nao pode ser perdido na correcao."""

        resultado = self.limpar()

        self.assertEqual(resultado["status"], "sucesso")
        self.assertTrue(Path(resultado["audio_limpo"]).exists())
        self.assertIn("snr_melhoria_db", resultado["limpeza_ruido"])


class VoiceTranscriptionHonestyTests(unittest.TestCase):
    """A transcricao de voz nao pode devolver um comando fixo com alta confianca."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.engine = LocalVoiceEngine(audio_dir=self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nao_devolve_comando_fixo_como_transcricao(self) -> None:
        """
        Antes, qualquer audio virava o texto "Jarvis status do sistema" com
        confianca 0.98. Um fluxo de voz ligado a isto executaria sempre o mesmo
        comando, e com aparencia de alta certeza.
        """

        audio = self.engine.speak("teste")["arquivo_audio"]

        resultado = self.engine.transcribe_audio(audio)

        self.assertEqual(resultado["status"], "indisponivel")
        self.assertIsNone(resultado["transcricao"])
        self.assertIsNone(resultado["confianca"])

    def test_arquivo_inexistente_continua_reportando_erro(self) -> None:
        """O caminho de erro anterior precisa continuar valendo."""

        resultado = self.engine.transcribe_audio(str(self.tmp / "nao_existe.wav"))

        self.assertEqual(resultado["status"], "erro")


if __name__ == "__main__":
    unittest.main()
