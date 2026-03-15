/*
JARVIS - Shader leve do campo neural

Responsavel por:
- centralizar as cores do cerebro cognitivo
- montar o fundo atmosférico do canvas
- fornecer utilitarios visuais para regioes e trilhas
*/

const REGION_BASE_COLORS = {
  cerebro_estrutural: "#2f5d50",
  rede_neural_procedural: "#c9a227",
  campos_neurais_dinamicos: "#3a7ca5",
  plasticidade_sinaptica: "#f5f5f5",
  mapa_de_consciencia: "#44bba4",
  mapa_evolutivo: "#d4af37",
};

export function resolveRegionColor(region) {
  return REGION_BASE_COLORS[region.region_id] || "#8d99ae";
}

export function resolveTrailColor(trail) {
  if (trail.cor) {
    return trail.cor;
  }
  return trail.intensidade > 0 ? "#d4af37" : "#3e4a61";
}

export function buildBackdrop(context, width, height) {
  const gradient = context.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#07111d");
  gradient.addColorStop(0.55, "#11243a");
  gradient.addColorStop(1, "#071c2e");
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);

  const halo = context.createRadialGradient(width * 0.5, height * 0.4, 12, width * 0.5, height * 0.4, width * 0.46);
  halo.addColorStop(0, "rgba(212, 175, 55, 0.15)");
  halo.addColorStop(0.55, "rgba(76, 201, 240, 0.06)");
  halo.addColorStop(1, "rgba(7, 17, 29, 0)");
  context.fillStyle = halo;
  context.fillRect(0, 0, width, height);
}
