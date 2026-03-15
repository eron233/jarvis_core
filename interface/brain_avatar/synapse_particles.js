/*
JARVIS - Particulas de sinapse

Responsavel por:
- gerar pontos de destaque ao longo das trilhas de aprendizado
- enfatizar conexoes novas e reforcadas sem custo elevado
*/

export function buildTrailParticles(trails, regionsById) {
  const particles = [];
  trails.forEach((trail, trailIndex) => {
    const source = regionsById.get(trail.source);
    const target = regionsById.get(trail.target);
    if (!source || !target || trail.intensidade <= 0) {
      return;
    }

    const particleCount = Math.max(1, Math.min(7, Math.round(trail.intensidade / 18)));
    for (let index = 0; index < particleCount; index += 1) {
      const progress = (index + 1) / (particleCount + 1);
      particles.push({
        id: `particle-${trailIndex}-${index}`,
        x: source.x + (target.x - source.x) * progress,
        y: source.y + (target.y - source.y) * progress,
        alpha: Math.min(0.92, 0.35 + trail.intensidade / 100),
        size: Math.min(4.5, 1.2 + trail.espessura * 0.3),
        color: trail.cor,
      });
    }
  });
  return particles;
}
