/*
JARVIS - Motor visual de plasticidade neural

Responsavel por:
- traduzir score cognitivo em brilho e espessura
- reforcar visualmente conexoes consolidadas
*/

export function applyPlasticity(evolutionPayload) {
  const regions = (evolutionPayload.regioes || []).map((region) => ({
    ...region,
    haloRadius: 32 + region.glow_intensity * 44,
    strokeWidth: 1 + region.glow_intensity * 2.5,
  }));

  const trails = (evolutionPayload.trilhas_aprendizado || []).map((trail) => ({
    ...trail,
    intensidade: trail.intensidade || 0,
    espessura: trail.espessura || 1,
    opacity: Math.min(0.9, 0.16 + (trail.intensidade || 0) / 80),
  }));

  return { regions, trails };
}
