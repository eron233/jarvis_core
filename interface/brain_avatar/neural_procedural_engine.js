/*
JARVIS - Camada procedural do avatar cerebral

Responsavel por:
- transformar estado operacional em resumo procedural do cerebro
- expor metadados uteis para a visualizacao
*/

export function buildProceduralOverlay(evolutionPayload) {
  const cognitiveState = evolutionPayload.estado_cognitivo || {};
  return {
    semanticEntries: cognitiveState.entradas_semanticas || 0,
    proceduresAvailable: cognitiveState.procedimentos_disponiveis || 0,
    activeGoals: cognitiveState.objetivos_ativos || 0,
    activeWorkers: cognitiveState.workers_ativos || [],
  };
}
