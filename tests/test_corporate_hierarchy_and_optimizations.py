import unittest
import tempfile
import shutil
import time
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.corporate_agent_hierarchy import CorporateAgentHierarchyEngine
from memory_system.semantic_cache_engine import SemanticCacheEngine
from security.git_branch_patcher import GitBranchPatcherEngine


class TestCorporateHierarchyAndOptimizations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()

        # Configurar diretórios temporários para os testes
        self.corporate_hierarchy = CorporateAgentHierarchyEngine(data_dir=Path(self.temp_dir) / "corp")
        self.semantic_cache = SemanticCacheEngine(storage_path=Path(self.temp_dir) / "cache.json")
        self.git_patcher = GitBranchPatcherEngine(
            project_root=Path(self.temp_dir),
            data_dir=Path(self.temp_dir) / "git_patches",
        )

        self.runtime.corporate_hierarchy_engine = self.corporate_hierarchy
        self.runtime.semantic_cache_engine = self.semantic_cache
        self.runtime.git_branch_patcher_engine = self.git_patcher

        self.app = create_app(
            runtime=self.runtime,
            api_token="test-token",
            trusted_device_id="test-device-id",
        )
        self.client = TestClient(self.app)

    def _get_headers(self):
        return {
            "X-Jarvis-Token": "test-token",
            "X-Jarvis-Device-Id": "test-device-id",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_corporate_agent_hierarchy(self):
        # 1. Dispatch de tarefa leve -> Seleciona Modelo Leve
        res_light = self.corporate_hierarchy.dispatch_corporate_task(
            department="Segurança",
            task_title="Auditoria de Rotas",
            task_payload={},
            task_complexity="simples",
        )
        self.assertEqual(res_light["roteamento_modelo"]["tier"], "leve")
        self.assertEqual(res_light["estado_final_subagente"], "hibernating")

        # 2. Dispatch de tarefa crítica -> Seleciona Modelo Pesado
        res_heavy = self.corporate_hierarchy.dispatch_corporate_task(
            department="Segurança",
            task_title="Caça Zero-Day Complexa",
            task_payload={},
            task_complexity="critica",
        )
        self.assertEqual(res_heavy["roteamento_modelo"]["tier"], "pesado")
        self.assertEqual(res_heavy["estado_final_subagente"], "hibernating")

    def test_dispatch_sem_executor_e_honesto(self):
        # Sem handler registrado: o dispatch planeja o roteamento mas não finge executar.
        res = self.corporate_hierarchy.dispatch_corporate_task(
            department="Engenharia",
            task_title="Tarefa Sem Executor",
            task_payload={},
            task_complexity="simples",
        )
        self.assertFalse(res["executado"])
        self.assertFalse(res["modelo_conectado"])
        self.assertEqual(res["resultado_execucao"]["status"], "nao_executado")

    def test_dispatch_com_executor_real(self):
        chamado = {}

        def handler(titulo, payload):
            chamado["titulo"] = titulo
            return {"status": "ok", "eco": payload.get("valor")}

        self.corporate_hierarchy.register_department_handler(
            "Engenharia_de_Software_e_Arquitetura", handler
        )
        res = self.corporate_hierarchy.dispatch_corporate_task(
            department="Engenharia",
            task_title="Refatorar módulo",
            task_payload={"valor": 42},
            task_complexity="critica",
        )
        self.assertTrue(res["executado"])
        self.assertEqual(res["resultado_execucao"]["status"], "ok")
        self.assertEqual(res["resultado_execucao"]["eco"], 42)
        self.assertEqual(chamado["titulo"], "Refatorar módulo")

    def test_git_patcher_gera_diff_real(self):
        # Novo comportamento: diff unificado real e honestidade sobre branch fora de repo git.
        original = "security/vulnerability_hunter.py"
        (Path(self.temp_dir) / "security").mkdir(parents=True, exist_ok=True)
        (Path(self.temp_dir) / original).write_text("def antigo():\n    return 1\n", encoding="utf-8")
        res = self.git_patcher.apply_patch_in_isolated_branch(
            vulnerability_id="ZDAY-XYZ",
            target_filepath=original,
            patch_content="def novo():\n    return 2\n",
        )
        self.assertIn("diff_unificado", res)
        self.assertIn("novo", res["diff_unificado"])
        self.assertTrue(res["testes_passaram"])  # sintaxe válida
        # temp_dir não é repo git → honesto: nenhuma branch criada
        self.assertFalse(res["branch_criada"])
        self.assertEqual(res["modo"], "dry_run")

    def test_semantic_cache_engine(self):
        query = "Como funciona a arquitetura do JARVIS?"
        response_payload = {"resposta": "JARVIS é um sistema executivo determinístico e defensivo."}

        # Cache Miss
        self.assertIsNone(self.semantic_cache.get(query, domain="system"))

        # Put Cache
        self.semantic_cache.put(query, response_payload, domain="system", tokens_saved_estimate=300)

        # Cache Hit (Exato)
        hit_res = self.semantic_cache.get("Como funciona a arquitetura do JARVIS?", domain="system")
        self.assertIsNotNone(hit_res)
        self.assertEqual(hit_res["resposta"], response_payload["resposta"])

        stats = self.semantic_cache.get_stats()
        self.assertEqual(stats["total_hits_acumulados"], 1)
        self.assertEqual(stats["estimativa_tokens_economizados"], 300)

    def test_git_branch_patcher_engine(self):
        patch_res = self.git_patcher.apply_patch_in_isolated_branch(
            vulnerability_id="ZDAY-001",
            target_filepath="security/vulnerability_hunter.py",
            patch_content="def fix(): pass",
        )
        self.assertTrue(patch_res["testes_passaram"])
        self.assertEqual(patch_res["nome_branch_isolada"], "jarvis/fix-zday-001")

    def test_api_corporate_endpoints(self):
        # API Dispatch
        response = self.client.post(
            "/api/corporativo/despachar?departamento=Engenharia&titulo_tarefa=Refatoracao_AST&complexidade=critica",
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("relatorio_dispatch", data)
        self.assertEqual(data["relatorio_dispatch"]["roteamento_modelo"]["tier"], "pesado")

        # API Status
        status_res = self.client.get("/api/corporativo/status", headers=self._get_headers())
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        self.assertEqual(status_data["subagentes_em_hibernacao"], 5)


if __name__ == "__main__":
    unittest.main()
