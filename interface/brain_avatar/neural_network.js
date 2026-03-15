/*
JARVIS - Rede Neural Procedural Visual

Responsavel por:
- transformar regioes cognitivas em neuronios simulados
- manter distribuicao deterministica no canvas
- limitar a renderizacao para manter baixo custo de CPU
*/

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function stableUnit(seed) {
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 10000) / 10000;
}

export function buildNeuronField(regions, maxLogicalNeurons = 10000) {
  const logicalNeuronCount = Math.min(
    maxLogicalNeurons,
    regions.reduce((total, region) => total + (region.logical_neurons || 0), 0),
  );
  const renderNeuronCount = Math.min(1600, Math.max(240, Math.round(logicalNeuronCount / 6 || 240)));
  const totalWeight = regions.reduce((total, region) => total + Math.max(region.render_weight || 0.2, 0.05), 0);
  const neurons = [];

  regions.forEach((region) => {
    const renderCount = Math.max(
      18,
      Math.round(renderNeuronCount * (Math.max(region.render_weight || 0.2, 0.05) / totalWeight)),
    );
    for (let index = 0; index < renderCount; index += 1) {
      const angle = stableUnit(`${region.region_id}:a:${index}`) * Math.PI * 2;
      const radiusBase = 0.032 + stableUnit(`${region.region_id}:r:${index}`) * (0.05 + region.glow_intensity * 0.08);
      const stretch = 1.45 - stableUnit(`${region.region_id}:s:${index}`) * 0.35;
      const x = clamp(region.x + Math.cos(angle) * radiusBase * stretch, 0.05, 0.95);
      const y = clamp(region.y + Math.sin(angle) * radiusBase, 0.08, 0.92);
      neurons.push({
        id: `${region.region_id}-neuron-${index}`,
        regionId: region.region_id,
        x,
        y,
        alpha: clamp(0.18 + region.glow_intensity * 0.8, 0.2, 0.95),
        size: clamp(0.8 + region.glow_intensity * 2.4 + stableUnit(`${region.region_id}:z:${index}`), 0.8, 4.5),
      });
    }
  });

  return {
    logicalNeuronCount,
    renderNeuronCount: neurons.length,
    neurons,
  };
}
