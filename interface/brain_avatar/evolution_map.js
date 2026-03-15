/*
JARVIS - Mapa Evolutivo Cognitivo

Responsavel por:
- carregar historico evolutivo pela API
- compor cerebro estrutural, plasticidade e consciencia em um so modelo
- desenhar a evolucao historica da inteligencia do Jarvis
*/

import { ActivityController } from "./activity_controller.js";
import { BrainRenderer } from "./brain_renderer.js";
import { buildConsciousnessHighlights } from "./consciousness_map.js";
import { applyPlasticity } from "./neural_plasticity_engine.js";
import { buildProceduralOverlay } from "./neural_procedural_engine.js";
import { buildTrailParticles } from "./synapse_particles.js";

function defaultFetchJson(path) {
  return fetch(path).then((response) => response.json());
}

function formatSummary(payload) {
  const summary = payload.resumo || {};
  const mostActiveRegion = (summary.regiao_mais_ativa || {}).label || "nenhuma";
  return [
    `Nivel: ${payload.nivel_ptbr || payload.nivel || "historica"}`,
    `Eventos considerados: ${summary.total_eventos || 0}`,
    `Conexoes criadas: ${summary.conexoes_criadas || 0}`,
    `Conexoes reforcadas: ${summary.conexoes_reforcadas || 0}`,
    `Impacto cognitivo total: ${summary.impacto_cognitivo_total || 0}`,
    `Regiao com maior crescimento: ${mostActiveRegion}`,
  ].join("\n");
}

function formatAnalysis(payload) {
  const topRegions = (payload.regioes_mais_utilizadas || []).map((item) => `${item.label} (${item.growth_score})`);
  const lowRegions = (payload.regioes_subutilizadas || []).map((item) => `${item.label} (${item.growth_score})`);
  const strongestTrails = (payload.conexoes_mais_fortes || []).map(
    (item) => `${item.source_label} -> ${item.target_label} (${item.intensidade})`,
  );
  return [
    `Regioes mais utilizadas: ${topRegions.join(", ") || "nenhuma"}`,
    `Regioes subutilizadas: ${lowRegions.join(", ") || "nenhuma"}`,
    `Trilhas mais fortes: ${strongestTrails.join(", ") || "nenhuma"}`,
  ].join("\n");
}

export function createEvolutionMap({
  canvas,
  summaryTarget,
  analysisTarget,
  statusTarget,
  fetchJson = defaultFetchJson,
} = {}) {
  const renderer = new BrainRenderer(canvas);
  const controller = new ActivityController();

  async function load(level = "historica", mode = "visualizacao") {
    if (!canvas) {
      return null;
    }

    if (statusTarget) {
      statusTarget.textContent = `Carregando mapa evolutivo (${level})...`;
    }

    const evolutionPayload = await fetchJson(`/api/cognicao/evolucao?nivel=${encodeURIComponent(level)}`);
    const analysisPayload = await fetchJson(`/api/cognicao/evolucao/analise?nivel=${encodeURIComponent(level)}`);
    const plasticityScene = applyPlasticity(evolutionPayload);
    const highlightedRegions = buildConsciousnessHighlights(analysisPayload, plasticityScene.regions);
    const regionsById = new Map(highlightedRegions.map((region) => [region.region_id, region]));
    const particles = buildTrailParticles(plasticityScene.trails, regionsById);
    const proceduralOverlay = buildProceduralOverlay(evolutionPayload);

    controller.setState({
      level,
      mode,
      evolution: evolutionPayload,
      analysis: analysisPayload,
      proceduralOverlay,
    });

    renderer.render({
      level,
      mode,
      payload: evolutionPayload,
      analysis: analysisPayload,
      regions: highlightedRegions,
      trails: plasticityScene.trails,
      particles,
      proceduralOverlay,
    });

    if (summaryTarget) {
      summaryTarget.textContent = formatSummary(evolutionPayload);
    }
    if (analysisTarget) {
      analysisTarget.textContent = formatAnalysis(analysisPayload);
    }
    if (statusTarget) {
      statusTarget.textContent = `Mapa evolutivo ativo em ${evolutionPayload.nivel_ptbr}.`;
    }

    return {
      evolutionPayload,
      analysisPayload,
      proceduralOverlay,
    };
  }

  return {
    showEvolution(level = "historica") {
      return load(level, "visualizacao");
    },
    analyzeEvolution(level = "historica") {
      return load(level, "analise_historica");
    },
    refresh() {
      const state = controller.snapshot();
      return load(state.level || "historica", state.mode || "visualizacao");
    },
    getState() {
      return controller.snapshot();
    },
  };
}
