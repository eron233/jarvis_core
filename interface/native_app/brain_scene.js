/*
JARVIS - Host nativo do cerebro visual oficial

Responsavel por:
- reutilizar a biblioteca oficial interface/brain_avatar no app nativo
- evitar uma engine cerebral paralela so para desktop
- receber payloads do Qt e repassar a renderizacao ao renderer compartilhado
*/

import { createEvolutionMap } from "../brain_avatar/evolution_map.js";

const DEFAULT_EVOLUTION = {
  nivel: "historica",
  nivel_ptbr: "Nivel 4 - evolucao historica completa",
  resumo: {
    total_eventos: 0,
    conexoes_criadas: 0,
    conexoes_reforcadas: 0,
    impacto_cognitivo_total: 0,
    regiao_mais_ativa: { label: "nenhuma" },
  },
  regioes: [],
  trilhas_aprendizado: [],
  estado_cognitivo: {},
};

const DEFAULT_ANALYSIS = {
  regioes_mais_utilizadas: [],
  regioes_subutilizadas: [],
  conexoes_mais_fortes: [],
};

const state = {
  evolution: { ...DEFAULT_EVOLUTION },
  analysis: { ...DEFAULT_ANALYSIS },
};

function normalizeLevel(value) {
  const level = String(value || "historica").toLowerCase();
  if (["recente", "semanal", "mensal", "historica"].includes(level)) {
    return level;
  }
  return "historica";
}

function syncHud() {
  const summary = state.evolution.resumo || {};
  const activeRegion = (summary.regiao_mais_ativa || {}).label || "nenhuma";
  const regionsCount = Array.isArray(state.evolution.regioes) ? state.evolution.regioes.length : 0;
  const trailsCount = Array.isArray(state.evolution.trilhas_aprendizado) ? state.evolution.trilhas_aprendizado.length : 0;

  const focusPill = document.getElementById("focusPill");
  const countPill = document.getElementById("countPill");
  const synapsePill = document.getElementById("synapsePill");
  const statePill = document.getElementById("statePill");
  const detailLine = document.getElementById("detailLine");

  if (focusPill) {
    focusPill.textContent = `Foco ${activeRegion}`;
  }
  if (countPill) {
    countPill.textContent = `${regionsCount} regioes`;
  }
  if (synapsePill) {
    synapsePill.textContent = `${trailsCount} trilhas`;
  }
  if (statePill) {
    statePill.textContent = `Estado ${state.evolution.nivel_ptbr || state.evolution.nivel || "historica"}`;
  }
  if (detailLine) {
    detailLine.textContent = `Eventos ${summary.total_eventos || 0} | conexoes criadas ${summary.conexoes_criadas || 0} | reforcos ${summary.conexoes_reforcadas || 0}`;
  }
}

function fetchFromInjectedState(path) {
  if (String(path).includes("/api/cognicao/evolucao/analise")) {
    return Promise.resolve(state.analysis);
  }
  return Promise.resolve(state.evolution);
}

const evolutionMap = createEvolutionMap({
  canvas: document.getElementById("brainCanvas"),
  statusTarget: document.getElementById("statusLine"),
  fetchJson: fetchFromInjectedState,
});

window.jarvisNativeBrainScene = {
  updateState(payload = {}) {
    state.evolution = payload.evolution || { ...DEFAULT_EVOLUTION };
    state.analysis = payload.analysis || { ...DEFAULT_ANALYSIS };
    syncHud();
    return evolutionMap.showEvolution(normalizeLevel(state.evolution.nivel));
  },
};

syncHud();
window.jarvisNativeBrainScene.updateState();
