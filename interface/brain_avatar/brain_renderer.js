/*
JARVIS - Renderizador do cerebro cognitivo

Responsavel por:
- desenhar o mapa evolutivo em um canvas unico
- aplicar brilho, trilhas e rotulos das regioes cognitivas
- manter a renderizacao barata para hardware fraco
*/

import { buildBackdrop, resolveRegionColor, resolveTrailColor } from "./neural_field_shader.js";
import { buildNeuronField } from "./neural_network.js";

export class BrainRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.context = canvas ? canvas.getContext("2d") : null;
  }

  render(scene) {
    if (!this.canvas || !this.context || !scene) {
      return;
    }

    this.#resizeCanvas();
    const { width, height } = this.canvas;
    buildBackdrop(this.context, width, height);

    const neuronField = buildNeuronField(scene.regions || []);
    const regionsById = new Map((scene.regions || []).map((region) => [region.region_id, region]));

    this.#drawTrails(scene.trails || [], regionsById, width, height);
    this.#drawNeurons(neuronField.neurons, regionsById, width, height);
    this.#drawParticles(scene.particles || [], width, height);
    this.#drawRegions(scene.regions || [], width, height);
    this.#drawFooter(scene, neuronField, width, height);
  }

  #resizeCanvas() {
    const deviceRatio = window.devicePixelRatio || 1;
    const displayWidth = this.canvas.clientWidth || 880;
    const displayHeight = this.canvas.clientHeight || 420;
    const nextWidth = Math.round(displayWidth * deviceRatio);
    const nextHeight = Math.round(displayHeight * deviceRatio);
    if (this.canvas.width !== nextWidth || this.canvas.height !== nextHeight) {
      this.canvas.width = nextWidth;
      this.canvas.height = nextHeight;
    }
  }

  #drawTrails(trails, regionsById, width, height) {
    trails.forEach((trail) => {
      const source = regionsById.get(trail.source);
      const target = regionsById.get(trail.target);
      if (!source || !target) {
        return;
      }

      this.context.save();
      this.context.strokeStyle = resolveTrailColor(trail);
      this.context.globalAlpha = trail.opacity || 0.35;
      this.context.lineWidth = Math.max(1, trail.espessura || 1);
      this.context.beginPath();
      this.context.moveTo(source.x * width, source.y * height);
      this.context.quadraticCurveTo(
        ((source.x + target.x) * 0.5) * width,
        (Math.min(source.y, target.y) - 0.12) * height,
        target.x * width,
        target.y * height,
      );
      this.context.stroke();
      this.context.restore();
    });
  }

  #drawNeurons(neurons, regionsById, width, height) {
    neurons.forEach((neuron) => {
      const region = regionsById.get(neuron.regionId);
      this.context.save();
      this.context.fillStyle = resolveRegionColor(region || { region_id: "mapa_evolutivo" });
      this.context.globalAlpha = neuron.alpha;
      this.context.beginPath();
      this.context.arc(neuron.x * width, neuron.y * height, neuron.size, 0, Math.PI * 2);
      this.context.fill();
      this.context.restore();
    });
  }

  #drawParticles(particles, width, height) {
    particles.forEach((particle) => {
      this.context.save();
      this.context.fillStyle = particle.color || "#d4af37";
      this.context.globalAlpha = particle.alpha || 0.7;
      this.context.beginPath();
      this.context.arc(particle.x * width, particle.y * height, particle.size || 2.5, 0, Math.PI * 2);
      this.context.fill();
      this.context.restore();
    });
  }

  #drawRegions(regions, width, height) {
    regions.forEach((region) => {
      const color = resolveRegionColor(region);
      const x = region.x * width;
      const y = region.y * height;

      this.context.save();
      this.context.globalAlpha = Math.min(0.45, region.glow_intensity * 0.55);
      this.context.fillStyle = color;
      this.context.beginPath();
      this.context.arc(x, y, region.haloRadius || 32, 0, Math.PI * 2);
      this.context.fill();
      this.context.restore();

      this.context.save();
      this.context.strokeStyle = color;
      this.context.globalAlpha = 0.95;
      this.context.lineWidth = region.strokeWidth || 2;
      this.context.beginPath();
      this.context.arc(x, y, 10 + region.glow_intensity * 8, 0, Math.PI * 2);
      this.context.stroke();
      this.context.restore();

      this.context.save();
      this.context.fillStyle = "#f6f8fb";
      this.context.font = "600 12px 'Trebuchet MS', sans-serif";
      this.context.textAlign = "center";
      this.context.fillText(region.label, x, y + 42);
      this.context.restore();
    });
  }

  #drawFooter(scene, neuronField, width, height) {
    this.context.save();
    this.context.fillStyle = "rgba(246, 248, 251, 0.86)";
    this.context.font = "12px 'Courier New', monospace";
    this.context.textAlign = "left";
    this.context.fillText(
      `Modo: ${scene.mode || "visualizacao"} | Nivel: ${scene.level || "historica"} | Neuronios simulados: ${neuronField.logicalNeuronCount}`,
      18,
      height - 24,
    );
    this.context.restore();
  }
}
