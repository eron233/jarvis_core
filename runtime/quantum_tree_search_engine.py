"""
JARVIS - Motor de Busca em Árvore Paralela Estilo Quântico e Interrogação Socrática dos 11 Pilares

Responsável por:
- explorar centenas de hipóteses e caminhos de solução em paralelo (Árvore de Decisão)
- realizar poda precoce (Early Pruning) de caminhos inviáveis
- colapsar e selecionar a solução ótima via Fronteira de Pareto (Diferencial, Open Source, Cripto/ROI, Facilidade)
- submeter a solução aprovada ao questionamento socrático obrigatório das 11 perguntas fundamentais
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUANTUM_TREE_DIR = PROJECT_ROOT / "data" / "quantum_tree_search"

# As 11 Perguntas Fundamentais de Validação Socrática
SOCRATIC_QUESTIONS_11 = [
    "Isso de fato está correto?",
    "O que sustenta isso?",
    "O que pode desestruturar essa ideia?",
    "Quais as possibilidades para fechar as lacunas que isso tem?",
    "Quais lacunas isso abre?",
    "Como posso melhorar isso?",
    "Quais técnicas são necessárias para a melhoria?",
    "Aonde está o gargalo principal e como posso resolver isso?",
    "Quais combinações de fatores, técnicas ou habilidades posso fazer para encontrar uma solução melhor do que o mercado ou todo o mundo já oferece?",
    "É viável? Consigo reproduzir isso de forma 100% open source?",
    "Com o dinheiro que tenho (provavelmente cripto), consigo melhorar isso de alguma forma exponencial, gastando o mínimo?",
]


class QuantumTreeSearchEngine:
    """Motor de busca em árvore paralela e questionamento socrático das 11 perguntas."""

    def __init__(self, data_dir: Optional[Path] = None, max_workers: int = 8) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_QUANTUM_TREE_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers

    def explore_hypotheses_tree(
        self,
        domain_goal: str,
        initial_hypotheses: List[Dict[str, Any]],
        available_crypto_budget_brl: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Explora dezenas/centenas de hipóteses em paralelo, realiza poda precoce e submete
        a melhor solução às 11 perguntas socráticas.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Avaliação Paralela e Poda Precoce (Early Pruning)
        evaluated_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._evaluate_hypothesis_node, hyp, available_crypto_budget_brl)
                for hyp in initial_hypotheses
            ]
            for future in futures:
                try:
                    res = future.result()
                    if res["poda_precoce_status"] == "mantida":
                        evaluated_nodes.append(res)
                except Exception:
                    pass

        if not evaluated_nodes:
            # Fallback se todas sofrerem poda
            evaluated_nodes = [self._evaluate_hypothesis_node(initial_hypotheses[0], available_crypto_budget_brl)]

        # 2. Colapso da Árvore: Seleção da Solução Ótima na Fronteira de Pareto
        best_hypothesis = max(
            evaluated_nodes,
            key=lambda node: (
                node["score_pareto"]["diferencial_mercado"] * 0.35 +
                node["score_pareto"]["open_source_viabilidade"] * 0.25 +
                node["score_pareto"]["eficiencia_cripto_roi"] * 0.25 +
                node["score_pareto"]["facilidade_execucao"] * 0.15
            )
        )

        # 3. Protocolo de Interrogação Socrática das 11 Perguntas sobre a Solução Ótima
        socratic_validation = self._apply_socratic_11_questions(best_hypothesis, domain_goal, available_crypto_budget_brl)

        search_result = {
            "objetivo_explorado": domain_goal,
            "executado_em": now,
            "total_hipoteses_avaliadas": len(initial_hypotheses),
            "total_hipoteses_mantidas_pos_poda": len(evaluated_nodes),
            "solucao_otima_colapsada": best_hypothesis,
            "validacao_socratica_11_pilares": socratic_validation,
            "aprovado_para_execucao": socratic_validation["pleno_fechamento_de_lacunas"],
        }

        self._save_search_record(search_result)
        return search_result

    def _evaluate_hypothesis_node(self, hyp: Dict[str, Any], budget_brl: float) -> Dict[str, Any]:
        """Avalia um nó da árvore calculando seu score de Pareto e status de poda."""
        name = hyp.get("nome", "Hipótese")
        is_open_source = bool(hyp.get("open_source", True))
        estimated_cost = float(hyp.get("custo_estimado_brl", 0.0))
        market_differentiator = float(hyp.get("diferencial_inovacao_0_10", 8.0))

        # Poda precoce: descarta se for proprietária ou exceder o orçamento Cripto disponível
        pruned = False
        pruning_reason = None
        if not is_open_source and estimated_cost > budget_brl:
            pruned = True
            pruning_reason = "Poda Precoce: Código proprietário com custo superior ao orçamento Cripto."

        pareto_score = {
            "diferencial_mercado": market_differentiator,
            "open_source_viabilidade": 10.0 if is_open_source else 4.0,
            "eficiencia_cripto_roi": 10.0 if estimated_cost <= budget_brl else 3.0,
            "facilidade_execucao": float(hyp.get("facilidade_0_10", 7.0)),
        }

        return {
            "nome_hipotese": name,
            "detalhes": hyp,
            "score_pareto": pareto_score,
            "poda_precoce_status": "podada" if pruned else "mantida",
            "motivo_poda": pruning_reason,
        }

    def _apply_socratic_11_questions(
        self,
        node: Dict[str, Any],
        goal: str,
        budget_brl: float,
    ) -> Dict[str, Any]:
        """Submete a solução ótima ao questionamento dos 11 pilares.

        Cada resposta é DERIVADA dos atributos reais da hipótese (scores de Pareto, custo,
        orçamento, código aberto, diferencial e facilidade). O veredito de fechamento de
        lacunas e a qualidade são calculados a partir de limiares — não são sempre positivos.
        """
        hyp_name = node["nome_hipotese"]
        scores = node["score_pareto"]
        detalhes = node.get("detalhes", {})

        diferencial = float(scores["diferencial_mercado"])
        open_source_viab = float(scores["open_source_viabilidade"])
        cripto_roi = float(scores["eficiencia_cripto_roi"])
        facilidade = float(scores["facilidade_execucao"])
        is_open_source = bool(detalhes.get("open_source", True))
        custo = float(detalhes.get("custo_estimado_brl", 0.0))
        dentro_orcamento = custo <= budget_brl

        # Identifica pontos fortes e lacunas reais (score < 6.0 é uma lacuna).
        pilares = {
            "diferencial de mercado": diferencial,
            "viabilidade open-source": open_source_viab,
            "eficiência de custo/ROI": cripto_roi,
            "facilidade de execução": facilidade,
        }
        lacunas = [nome for nome, val in pilares.items() if val < 6.0]
        fortes = [nome for nome, val in pilares.items() if val >= 8.0]

        def _sn(cond: bool) -> str:
            return "Sim" if cond else "Não"

        answers = [
            f"1. Está correto? {_sn(diferencial >= 5.0)} — diferencial avaliado em {diferencial:.1f}/10 "
            f"frente ao objetivo '{goal}'.",
            f"2. O que sustenta? Pontos fortes: {', '.join(fortes) if fortes else 'nenhum pilar acima de 8.0'}.",
            f"3. O que pode desestruturar? {'Custo acima do orçamento (R$ %.2f > R$ %.2f).' % (custo, budget_brl) if not dentro_orcamento else 'Dependência de terceiros e variação de contexto.'}",
            f"4. Como fechar as lacunas? {'Nenhuma lacuna crítica; manter monitoramento.' if not lacunas else 'Atacar: ' + ', '.join(lacunas) + '.'}",
            f"5. Quais lacunas abre? {', '.join(lacunas) if lacunas else 'Nenhuma lacuna abaixo de 6.0 identificada.'}",
            f"6. Como melhorar? {'Elevar ' + lacunas[0] + '.' if lacunas else 'Refinar o pilar de menor score: ' + min(pilares, key=pilares.get) + '.'}",
            f"7. Técnicas necessárias? {'Adoção/substituição por alternativa open-source.' if not is_open_source else 'Manter stack aberta e modular.'}",
            f"8. Gargalo principal? Pilar de menor score: {min(pilares, key=pilares.get)} ({min(pilares.values()):.1f}/10).",
            f"9. Combinação de fatores? Média ponderada dos pilares = {self._weighted_score(scores):.2f}/10.",
            f"10. É 100% open-source? {_sn(is_open_source)}.",
            f"11. Cabe no orçamento (R$ {budget_brl:.2f})? {_sn(dentro_orcamento)} — custo estimado R$ {custo:.2f}.",
        ]

        weighted = self._weighted_score(scores)
        # Veredito honesto: exige média boa, orçamento respeitado e nenhuma lacuna crítica.
        pleno_fechamento = weighted >= 7.0 and dentro_orcamento and not lacunas
        if weighted >= 8.5 and not lacunas:
            qualidade = "superior_ao_mercado"
        elif weighted >= 7.0:
            qualidade = "competitiva"
        elif weighted >= 5.0:
            qualidade = "viavel_com_ressalvas"
        else:
            qualidade = "insuficiente"

        return {
            "hipotese_validada": hyp_name,
            "perguntas_e_respostas_11_pilares": answers,
            "score_ponderado": round(weighted, 2),
            "lacunas_identificadas": lacunas,
            "pilares_fortes": fortes,
            "pleno_fechamento_de_lacunas": pleno_fechamento,
            "qualidade_solucao": qualidade,
        }

    @staticmethod
    def _weighted_score(scores: Dict[str, float]) -> float:
        """Média ponderada dos pilares de Pareto (mesmos pesos usados na seleção)."""
        return (
            float(scores["diferencial_mercado"]) * 0.35
            + float(scores["open_source_viabilidade"]) * 0.25
            + float(scores["eficiencia_cripto_roi"]) * 0.25
            + float(scores["facilidade_execucao"]) * 0.15
        )

    def _save_search_record(self, record: Dict[str, Any]) -> None:
        """Salva a exploração da árvore em disco."""
        file_id = f"quantum_search_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
