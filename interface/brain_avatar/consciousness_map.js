/*
JARVIS - Mapa de consciencia visual

Responsavel por:
- destacar regioes mais utilizadas e subutilizadas
- oferecer uma camada de autoconhecimento ao avatar cerebral
*/

export function buildConsciousnessHighlights(analysisPayload, regions) {
  const hotRegions = new Set((analysisPayload.regioes_mais_utilizadas || []).map((item) => item.region_id));
  const coldRegions = new Set((analysisPayload.regioes_subutilizadas || []).map((item) => item.region_id));

  return regions.map((region) => ({
    ...region,
    introspectionState: hotRegions.has(region.region_id)
      ? "hot"
      : coldRegions.has(region.region_id)
        ? "cold"
        : "neutral",
  }));
}
