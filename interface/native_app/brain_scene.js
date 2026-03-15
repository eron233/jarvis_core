(function () {
  "use strict";

  const NEURON_COUNT = 1560;
  const SYNAPSE_COUNT = 14800;
  const LOCAL_RATIO = 0.8;
  const SHELL_POINT_COUNT = 2600;
  const GROOVE_CURVE_COUNT = 20;
  const LIGHT = normalize({ x: -0.34, y: 0.18, z: 1.0 });
  const SYNAPSE_COLOR = [103, 242, 255];
  const BRAIN_SEED = 23051989;
  const REGION_ORDER = ["memory", "planning", "execution", "security", "evolution"];
  const REGION_CONFIG = [
    {
      id: "memory",
      label: "Memoria",
      color: [79, 140, 255],
      centers: [
        { x: -0.34, y: 0.02, z: -0.26, radius: 0.45, weight: 1.0 },
        { x: 0.34, y: 0.02, z: -0.26, radius: 0.45, weight: 1.0 },
        { x: 0.0, y: -0.08, z: -0.08, radius: 0.34, weight: 0.55 }
      ],
      wave: [3.8, -2.6, 2.2]
    },
    {
      id: "planning",
      label: "Planejamento",
      color: [255, 215, 74],
      centers: [
        { x: -0.3, y: 0.34, z: 0.44, radius: 0.44, weight: 1.0 },
        { x: 0.3, y: 0.34, z: 0.44, radius: 0.44, weight: 1.0 },
        { x: 0.0, y: 0.22, z: 0.18, radius: 0.4, weight: 0.45 }
      ],
      wave: [2.6, 3.2, -2.1]
    },
    {
      id: "execution",
      label: "Execucao",
      color: [84, 222, 115],
      centers: [
        { x: -0.2, y: 0.02, z: 0.08, radius: 0.3, weight: 1.0 },
        { x: 0.2, y: 0.02, z: 0.08, radius: 0.3, weight: 1.0 },
        { x: 0.0, y: 0.0, z: 0.12, radius: 0.34, weight: 0.7 }
      ],
      wave: [-3.1, 2.2, 2.8]
    },
    {
      id: "security",
      label: "Seguranca",
      color: [255, 93, 93],
      centers: [
        { x: -0.12, y: -0.16, z: 0.06, radius: 0.28, weight: 0.9 },
        { x: 0.12, y: -0.16, z: 0.06, radius: 0.28, weight: 0.9 },
        { x: 0.0, y: -0.06, z: -0.02, radius: 0.24, weight: 0.85 }
      ],
      wave: [2.9, -3.6, 1.5]
    },
    {
      id: "evolution",
      label: "Evolucao",
      color: [168, 108, 255],
      centers: [
        { x: -0.24, y: 0.42, z: -0.12, radius: 0.5, weight: 0.88 },
        { x: 0.24, y: 0.42, z: -0.12, radius: 0.5, weight: 0.88 },
        { x: 0.0, y: 0.16, z: 0.02, radius: 0.58, weight: 0.62 }
      ],
      wave: [-2.4, 2.9, 3.5]
    }
  ];
  const STATE_CONFIG = {
    idle: {
      label: "Idle",
      pulseTarget: 14,
      longBias: 0.16,
      pulseSpeed: [0.12, 0.22],
      neuronBoost: 0.05,
      emphasis: { memory: 0.28, planning: 0.22, execution: 0.18, security: 0.12, evolution: 0.2 },
      tint: [103, 242, 255]
    },
    thinking: {
      label: "Thinking",
      pulseTarget: 32,
      longBias: 0.26,
      pulseSpeed: [0.18, 0.34],
      neuronBoost: 0.1,
      emphasis: { memory: 1.0, planning: 1.12, execution: 0.32, security: 0.18, evolution: 0.42 },
      tint: [144, 214, 255]
    },
    execution: {
      label: "Execution",
      pulseTarget: 44,
      longBias: 0.12,
      pulseSpeed: [0.28, 0.5],
      neuronBoost: 0.2,
      emphasis: { memory: 0.28, planning: 0.46, execution: 1.38, security: 0.24, evolution: 0.3 },
      tint: [84, 222, 115]
    },
    alert: {
      label: "Alert",
      pulseTarget: 48,
      longBias: 0.18,
      pulseSpeed: [0.24, 0.48],
      neuronBoost: 0.22,
      emphasis: { memory: 0.16, planning: 0.22, execution: 0.22, security: 1.45, evolution: 0.2 },
      tint: [255, 93, 93]
    },
    learning: {
      label: "Learning",
      pulseTarget: 40,
      longBias: 0.38,
      pulseSpeed: [0.2, 0.4],
      neuronBoost: 0.18,
      emphasis: { memory: 0.58, planning: 0.44, execution: 0.24, security: 0.12, evolution: 1.42 },
      tint: [168, 108, 255]
    }
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function lerp(a, b, t) {
    return a + ((b - a) * t);
  }

  function smoothstep(edge0, edge1, value) {
    const t = clamp((value - edge0) / ((edge1 - edge0) || 1), 0, 1);
    return t * t * (3 - (2 * t));
  }

  function dot(a, b) {
    return (a.x * b.x) + (a.y * b.y) + (a.z * b.z);
  }

  function lengthOf(vector) {
    return Math.sqrt(dot(vector, vector));
  }

  function normalize(vector) {
    const size = lengthOf(vector) || 1;
    return { x: vector.x / size, y: vector.y / size, z: vector.z / size };
  }

  function colorToRgba(color, alpha) {
    return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
  }

  function mixColors(colors, weights) {
    let red = 0;
    let green = 0;
    let blue = 0;
    let total = 0;
    colors.forEach((color, index) => {
      const weight = weights[index] || 0;
      red += color[0] * weight;
      green += color[1] * weight;
      blue += color[2] * weight;
      total += weight;
    });
    if (!total) {
      return [118, 202, 255];
    }
    return [
      Math.round(red / total),
      Math.round(green / total),
      Math.round(blue / total)
    ];
  }

  function blendColor(base, accent, factor) {
    return [
      Math.round(lerp(base[0], accent[0], factor)),
      Math.round(lerp(base[1], accent[1], factor)),
      Math.round(lerp(base[2], accent[2], factor))
    ];
  }

  function hashString(value) {
    let hash = 2166136261;
    const text = String(value || "");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function createRng(seed) {
    let state = (seed >>> 0) || 1;
    return function next() {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 4294967296;
    };
  }

  function rotatePoint(point, yaw, pitch) {
    const sinYaw = Math.sin(yaw);
    const cosYaw = Math.cos(yaw);
    const sinPitch = Math.sin(pitch);
    const cosPitch = Math.cos(pitch);
    const yawX = (point.x * cosYaw) - (point.z * sinYaw);
    const yawZ = (point.x * sinYaw) + (point.z * cosYaw);
    const pitchY = (point.y * cosPitch) - (yawZ * sinPitch);
    const pitchZ = (point.y * sinPitch) + (yawZ * cosPitch);
    return { x: yawX, y: pitchY, z: pitchZ };
  }

  function midpoint(a, b) {
    return { x: (a.x + b.x) * 0.5, y: (a.y + b.y) * 0.5, z: (a.z + b.z) * 0.5 };
  }

  function makeKey(a, b) {
    return a < b ? `${a}:${b}` : `${b}:${a}`;
  }

  function queryMode() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return params.get("mode") || "compact";
    } catch (_error) {
      return "compact";
    }
  }

  function hemisphereMetric(point, side) {
    const centerX = side * 0.43;
    const groove = 1 + (0.045 * Math.sin((point.y * 11.0) + (point.z * 5.8) + (side * 0.8))) + (0.03 * Math.cos((point.z * 14.0) - (point.y * 4.1)));
    const frontalBulge = 1 + (0.16 * smoothstep(-0.2, 0.98, point.z));
    const occipitalTaper = 1 - (0.08 * smoothstep(0.15, 1.0, -point.z));
    const temporalDrop = 1 - (0.1 * smoothstep(-0.15, -0.85, point.y));
    const dorsalLift = 1 + (0.08 * smoothstep(-0.8, 0.3, point.y));
    const radiusX = 0.63 * groove;
    const radiusY = 0.8 * temporalDrop * dorsalLift;
    const radiusZ = 0.95 * frontalBulge * occipitalTaper;
    const x = (point.x - centerX) / radiusX;
    const y = point.y / radiusY;
    const z = point.z / radiusZ;
    const fissureWidth = 0.052 + (0.026 * smoothstep(-0.6, 0.9, point.y)) + (0.02 * (1 - Math.abs(point.z)));
    const inFissure = Math.abs(point.x) < fissureWidth && point.y > -0.42;
    if (inFissure) {
      return 1.24;
    }
    return (x * x) + (y * y) + (z * z);
  }

  function corpusCallosumMetric(point) {
    const x = point.x / 0.18;
    const y = (point.y + 0.1) / 0.22;
    const z = point.z / 0.5;
    return (x * x) + (y * y) + (z * z);
  }

  function brainField(point) {
    return Math.min(hemisphereMetric(point, -1), hemisphereMetric(point, 1), corpusCallosumMetric(point)) - 1;
  }

  function isInsideBrain(point) {
    return brainField(point) <= 0;
  }

  function approximateNormal(point) {
    const epsilon = 0.01;
    const dx = brainField({ x: point.x + epsilon, y: point.y, z: point.z }) - brainField({ x: point.x - epsilon, y: point.y, z: point.z });
    const dy = brainField({ x: point.x, y: point.y + epsilon, z: point.z }) - brainField({ x: point.x, y: point.y - epsilon, z: point.z });
    const dz = brainField({ x: point.x, y: point.y, z: point.z + epsilon }) - brainField({ x: point.x, y: point.y, z: point.z - epsilon });
    return normalize({ x: dx, y: dy, z: dz });
  }

  function projectToSurface(side, vertical, depth) {
    let lastInside = null;
    for (let step = 0; step <= 84; step += 1) {
      const t = step / 84;
      const lateral = lerp(0.08, 0.8, t);
      const point = {
        x: side * lateral,
        y: vertical + (0.028 * Math.sin((depth * 8.0) + (vertical * 4.0) + (side * 0.65))),
        z: depth
      };
      if (isInsideBrain(point)) {
        lastInside = point;
      } else if (lastInside) {
        return { ...lastInside, normal: approximateNormal(lastInside), hemisphere: side };
      }
    }
    return lastInside ? { ...lastInside, normal: approximateNormal(lastInside), hemisphere: side } : null;
  }

  function regionBlendAt(point) {
    const weights = [];
    REGION_CONFIG.forEach((region, index) => {
      let value = 0.12;
      region.centers.forEach((center) => {
        const dx = point.x - center.x;
        const dy = point.y - center.y;
        const dz = point.z - center.z;
        const distanceSquared = (dx * dx) + (dy * dy) + (dz * dz);
        value += center.weight * Math.exp(-distanceSquared / (center.radius * center.radius));
      });
      value += 0.07 * (1 + Math.sin((point.x * region.wave[0] * Math.PI) + (point.y * region.wave[1] * Math.PI) + (point.z * region.wave[2] * Math.PI) + index));
      value += 0.05 * (1 + Math.cos(((point.x - point.z) * (2.4 + (index * 0.2))) + (point.y * 1.8)));
      weights.push(Math.max(0.04, value));
    });
    const total = weights.reduce((sum, value) => sum + value, 0) || 1;
    const normalized = weights.map((value) => value / total);
    let dominantIndex = 0;
    let dominantWeight = normalized[0];
    normalized.forEach((value, index) => {
      if (value > dominantWeight) {
        dominantWeight = value;
        dominantIndex = index;
      }
    });
    return {
      weights: normalized,
      dominant: REGION_CONFIG[dominantIndex].id,
      dominantLabel: REGION_CONFIG[dominantIndex].label,
      color: mixColors(REGION_CONFIG.map((region) => region.color), normalized)
    };
  }

  function buildIntegratedBrain() {
    const rng = createRng(BRAIN_SEED ^ hashString("jarvis_brain_rebuild"));
    const shellPoints = [];
    const grooveCurves = [];
    const neurons = [];

    while (shellPoints.length < SHELL_POINT_COUNT) {
      const point = {
        x: lerp(-1.12, 1.12, rng()),
        y: lerp(-0.92, 0.88, rng()),
        z: lerp(-1.08, 1.08, rng())
      };
      const field = brainField(point);
      if (field <= 0 && field >= -0.18) {
        shellPoints.push({ ...point, normal: approximateNormal(point), hemisphere: point.x < 0 ? -1 : 1 });
      }
    }

    for (let side = -1; side <= 1; side += 2) {
      for (let band = 0; band < GROOVE_CURVE_COUNT / 2; band += 1) {
        const samples = [];
        const vertical = lerp(-0.68, 0.64, band / ((GROOVE_CURVE_COUNT / 2) - 1 || 1));
        for (let step = 0; step <= 40; step += 1) {
          const depth = lerp(-0.92, 0.94, step / 40);
          const point = projectToSurface(side, vertical, depth);
          if (point) {
            samples.push(point);
          }
        }
        grooveCurves.push({ hemisphere: side, samples, phase: rng() * Math.PI * 2 });
      }
    }

    let attempts = 0;
    while (neurons.length < NEURON_COUNT && attempts < NEURON_COUNT * 110) {
      attempts += 1;
      const point = {
        x: lerp(-1.0, 1.0, rng()),
        y: lerp(-0.82, 0.82, rng()),
        z: lerp(-0.96, 0.96, rng())
      };
      if (!isInsideBrain(point)) {
        continue;
      }
      const blend = regionBlendAt(point);
      neurons.push({
        id: neurons.length,
        x: point.x,
        y: point.y,
        z: point.z,
        hemisphere: point.x < 0 ? -1 : 1,
        regionWeights: blend.weights,
        dominantRegion: blend.dominant,
        dominantLabel: blend.dominantLabel,
        color: blend.color,
        size: lerp(1.1, 2.6, Math.pow(rng(), 1.7)),
        flicker: lerp(0.7, 1.35, rng()),
        phase: rng() * Math.PI * 2
      });
    }

    const localTarget = Math.floor(SYNAPSE_COUNT * LOCAL_RATIO);
    const localCandidates = Array.from({ length: neurons.length }, () => []);
    const longCandidates = [];
    const longCandidateChance = 0.018;

    for (let sourceIndex = 0; sourceIndex < neurons.length; sourceIndex += 1) {
      const source = neurons[sourceIndex];
      for (let targetIndex = sourceIndex + 1; targetIndex < neurons.length; targetIndex += 1) {
        const target = neurons[targetIndex];
        const dx = source.x - target.x;
        const dy = source.y - target.y;
        const dz = source.z - target.z;
        const distanceSquared = (dx * dx) + (dy * dy) + (dz * dz);
        const sameHemisphere = source.hemisphere === target.hemisphere;
        const sameRegion = source.dominantRegion === target.dominantRegion;

        if (distanceSquared < 0.082) {
          const weight = distanceSquared * (sameRegion ? 0.88 : 1.0);
          localCandidates[sourceIndex].push({ index: targetIndex, weight });
          localCandidates[targetIndex].push({ index: sourceIndex, weight });
        } else if (distanceSquared < 1.55 && (!sameHemisphere || !sameRegion) && rng() < longCandidateChance) {
          longCandidates.push({ a: sourceIndex, b: targetIndex, score: distanceSquared * (sameHemisphere ? 1.08 : 0.78) });
        }
      }
    }

    const synapses = [];
    const localSynapseIndices = [];
    const longSynapseIndices = [];
    const edgeKeys = new Set();
    const degree = new Uint16Array(neurons.length);

    function buildAffinity(weights, kind) {
      const memory = weights[0];
      const planning = weights[1];
      const execution = weights[2];
      const security = weights[3];
      const evolution = weights[4];
      return {
        idle: (memory * 0.36) + (planning * 0.28) + (evolution * 0.26) + (kind === "long" ? 0.08 : 0),
        thinking: (memory * 1.06) + (planning * 1.12) + (evolution * 0.42) + (kind === "long" ? 0.08 : 0.16),
        execution: (execution * 1.3) + (planning * 0.34) + (kind === "local" ? 0.18 : 0.04),
        alert: (security * 1.42) + (execution * 0.24) + (kind === "long" ? 0.08 : 0.02),
        learning: (evolution * 1.3) + (memory * 0.52) + (planning * 0.42) + (kind === "long" ? 0.18 : 0.06)
      };
    }

    function addSynapse(a, b, kind) {
      const key = makeKey(a, b);
      if (edgeKeys.has(key)) {
        return false;
      }
      edgeKeys.add(key);
      degree[a] += 1;
      degree[b] += 1;

      const source = neurons[a];
      const target = neurons[b];
      const mid = midpoint(source, target);
      const averageWeights = REGION_ORDER.map((_, index) => (source.regionWeights[index] + target.regionWeights[index]) * 0.5);
      const controlLift = kind === "long" ? 0.16 : 0.05;
      const control = {
        x: mid.x * 0.94,
        y: mid.y + controlLift + (averageWeights[4] * 0.04),
        z: mid.z * 0.94
      };

      const synapse = {
        index: synapses.length,
        a,
        b,
        kind,
        control,
        averageWeights,
        affinity: buildAffinity(averageWeights, kind)
      };
      synapses.push(synapse);
      if (kind === "long") {
        longSynapseIndices.push(synapse.index);
      } else {
        localSynapseIndices.push(synapse.index);
      }
      return true;
    }

    localCandidates.forEach((candidateList, neuronIndex) => {
      candidateList.sort((left, right) => left.weight - right.weight);
      const limit = 10 + Math.floor(rng() * 5);
      for (let index = 0; index < candidateList.length && index < limit && localSynapseIndices.length < localTarget; index += 1) {
        const candidate = candidateList[index];
        if (degree[neuronIndex] >= 18 || degree[candidate.index] >= 18) {
          continue;
        }
        addSynapse(neuronIndex, candidate.index, "local");
      }
    });

    longCandidates.sort((left, right) => left.score - right.score);
    for (let index = 0; index < longCandidates.length && synapses.length < SYNAPSE_COUNT; index += 1) {
      const candidate = longCandidates[index];
      if (degree[candidate.a] >= 22 || degree[candidate.b] >= 22) {
        continue;
      }
      addSynapse(candidate.a, candidate.b, "long");
    }

    return {
      shellPoints,
      grooveCurves,
      neurons,
      synapses,
      localSynapseIndices,
      longSynapseIndices
    };
  }

  function readPrimaryFocus(payload) {
    const evolution = payload.evolution || {};
    const analysis = payload.analysis || {};
    const fromSummary = (((evolution.resumo || {}).regiao_mais_ativa || {}).label) || "";
    const fromAnalysis = (((analysis.regioes_mais_utilizadas || [])[0] || {}).label) || "";
    return fromSummary || fromAnalysis || "Rede neural integrada";
  }

  function inferBoosts(payload) {
    const boosts = { memory: 0, planning: 0, execution: 0, security: 0, evolution: 0 };
    const texts = [];
    const evolution = payload.evolution || {};
    const analysis = payload.analysis || {};
    texts.push(readPrimaryFocus(payload));
    (evolution.regioes || []).forEach((region) => texts.push(region.label || region.region_id || ""));
    (analysis.regioes_mais_utilizadas || []).forEach((region) => texts.push(region.label || region.region_id || ""));
    (analysis.regioes_subutilizadas || []).forEach((region) => texts.push(region.label || region.region_id || ""));

    texts.forEach((value) => {
      const normalized = String(value || "").toLowerCase();
      if (!normalized) {
        return;
      }
      if (normalized.includes("mem") || normalized.includes("semantic")) {
        boosts.memory += 0.3;
      }
      if (normalized.includes("planej") || normalized.includes("objetiv") || normalized.includes("tatic")) {
        boosts.planning += 0.3;
      }
      if (normalized.includes("exec") || normalized.includes("ciclo") || normalized.includes("dispatch") || normalized.includes("runtime")) {
        boosts.execution += 0.26;
      }
      if (normalized.includes("segur") || normalized.includes("vigil") || normalized.includes("risco") || normalized.includes("defes") || normalized.includes("alert")) {
        boosts.security += 0.34;
      }
      if (normalized.includes("evol") || normalized.includes("aprend") || normalized.includes("plastic")) {
        boosts.evolution += 0.32;
      }
    });
    return boosts;
  }

  function chooseBaseState(payload, boosts) {
    const totalBoost = boosts.memory + boosts.planning + boosts.execution + boosts.security + boosts.evolution;
    if (!totalBoost) {
      return "idle";
    }
    if (boosts.security >= 0.55) {
      return "alert";
    }
    if (boosts.execution >= 0.52) {
      return "execution";
    }
    if (boosts.evolution >= 0.56) {
      return "learning";
    }
    return "thinking";
  }

  function regionIdToIndex(regionId) {
    return REGION_ORDER.indexOf(regionId);
  }

  class JarvisBrainScene {
    constructor() {
      this.mode = queryMode();
      this.canvas = document.getElementById("brainCanvas");
      this.context = this.canvas ? this.canvas.getContext("2d", { alpha: false }) : null;
      this.focusPill = document.getElementById("focusPill");
      this.statePill = document.getElementById("statePill");
      this.countPill = document.getElementById("countPill");
      this.synapsePill = document.getElementById("synapsePill");
      this.statusLine = document.getElementById("statusLine");
      this.detailLine = document.getElementById("detailLine");
      this.hintLine = document.getElementById("hintLine");
      this.controlLine = document.getElementById("controlLine");

      this.deviceRatio = Math.max(1, window.devicePixelRatio || 1);
      this.scene = buildIntegratedBrain();
      this.camera = { yaw: -0.46, pitch: -0.16, zoom: 4.2, panX: 0, panY: -0.01 };
      this.payload = { evolution: {}, analysis: {} };
      this.regionBoosts = { memory: 0, planning: 0, execution: 0, security: 0, evolution: 0 };
      this.baseState = "idle";
      this.temporaryState = null;
      this.temporaryStateUntil = 0;
      this.previousCycles = 0;
      this.previousEvents = 0;
      this.pulses = [];
      this.neuronActivation = new Float32Array(this.scene.neurons.length);
      this.frameCounter = 0;
      this.lastFrameTime = performance.now();
      this.lastBurstTime = 0;
      this.dragState = null;
      this._applyModeCopy();
      this._bindEvents();
      this._resize();
      this.updateState({});
      this._frame();
    }

    updateState(payload) {
      this.payload = {
        evolution: payload && payload.evolution ? payload.evolution : {},
        analysis: payload && payload.analysis ? payload.analysis : {}
      };

      const summary = this.payload.evolution.resumo || {};
      const runtimeState = this.payload.analysis.estado_runtime || {};
      const focusLabel = readPrimaryFocus(this.payload);
      const boosts = inferBoosts(this.payload);
      const cycles = Number(runtimeState.total_ciclos_executados || 0);
      const events = Number(summary.total_eventos || 0);

      this.regionBoosts = boosts;
      this.baseState = chooseBaseState(this.payload, boosts);

      if (boosts.security >= 0.55) {
        this._triggerTemporaryState("alert", 4200);
      } else if (cycles > this.previousCycles) {
        this._triggerTemporaryState("execution", 3600);
      } else if (events > this.previousEvents) {
        this._triggerTemporaryState("learning", 4800);
      } else if (this.baseState !== "idle") {
        this._triggerTemporaryState("thinking", 2200);
      }

      this.previousCycles = cycles;
      this.previousEvents = events;
      this.focusPill.textContent = `Foco ${focusLabel}`;
      this.countPill.textContent = `${this.scene.neurons.length} neuronios`;
      this.synapsePill.textContent = `${this.scene.synapses.length} sinapses`;
      this._updateHudCopy();
    }

    resetView() {
      this.camera.yaw = -0.46;
      this.camera.pitch = -0.16;
      this.camera.zoom = this.mode === "expanded" ? 3.5 : 4.2;
      this.camera.panX = 0;
      this.camera.panY = -0.01;
    }

    _applyModeCopy() {
      if (this.mode === "expanded") {
        this.hintLine.textContent = "Arraste para rotacionar. Shift + arraste ou botao direito para mover.";
        this.controlLine.textContent = "Use a roda do mouse para zoom. Duplo clique para resetar a camera.";
        this.camera.zoom = 3.5;
      } else {
        this.hintLine.textContent = "Clique no cerebro para expandir. Na visao ampla voce navega em 3D.";
        this.controlLine.textContent = "Quando ampliado, use arraste, pan e zoom para inspecionar a rede neural.";
      }
    }

    _currentState() {
      if (this.temporaryState && performance.now() < this.temporaryStateUntil) {
        return this.temporaryState;
      }
      return this.baseState;
    }

    _triggerTemporaryState(state, durationMs) {
      this.temporaryState = state;
      this.temporaryStateUntil = performance.now() + durationMs;
    }

    _updateHudCopy() {
      const summary = this.payload.evolution.resumo || {};
      const state = this._currentState();
      const stateConfig = STATE_CONFIG[state];
      this.statePill.textContent = `Estado ${stateConfig.label}`;
      this.statusLine.textContent = this.payload.evolution.nivel_ptbr || "Rede neural 3D ativa.";
      this.detailLine.textContent = `Eventos ${summary.total_eventos || 0} | conexoes reforcadas ${summary.conexoes_reforcadas || 0} | atividade ${stateConfig.label}`;
    }

    _bindEvents() {
      if (!this.canvas) {
        return;
      }

      this.canvas.addEventListener("pointerdown", (event) => {
        this.dragState = {
          x: event.clientX,
          y: event.clientY,
          mode: event.button === 2 || event.shiftKey ? "pan" : "rotate"
        };
        this.canvas.classList.add("dragging");
        this.canvas.setPointerCapture(event.pointerId);
      });

      this.canvas.addEventListener("pointermove", (event) => {
        if (!this.dragState || this.mode !== "expanded") {
          return;
        }
        const dx = event.clientX - this.dragState.x;
        const dy = event.clientY - this.dragState.y;
        this.dragState.x = event.clientX;
        this.dragState.y = event.clientY;

        if (this.dragState.mode === "pan") {
          this.camera.panX += dx * 0.0019;
          this.camera.panY -= dy * 0.0019;
        } else {
          this.camera.yaw += dx * 0.008;
          this.camera.pitch = clamp(this.camera.pitch + (dy * 0.006), -1.02, 1.02);
        }
      });

      this.canvas.addEventListener("pointerup", (event) => {
        this.dragState = null;
        this.canvas.classList.remove("dragging");
        if (this.canvas.hasPointerCapture(event.pointerId)) {
          this.canvas.releasePointerCapture(event.pointerId);
        }
      });

      this.canvas.addEventListener("pointerleave", () => {
        this.dragState = null;
        this.canvas.classList.remove("dragging");
      });

      this.canvas.addEventListener("wheel", (event) => {
        if (this.mode !== "expanded") {
          return;
        }
        event.preventDefault();
        this.camera.zoom = clamp(this.camera.zoom + (Math.sign(event.deltaY || 0) * 0.16), 2.6, 6.2);
      }, { passive: false });

      this.canvas.addEventListener("dblclick", () => {
        if (this.mode === "expanded") {
          this.resetView();
        }
      });

      this.canvas.addEventListener("contextmenu", (event) => {
        event.preventDefault();
      });

      window.addEventListener("resize", () => this._resize());
    }

    _resize() {
      if (!this.canvas || !this.context) {
        return;
      }
      const rect = this.canvas.getBoundingClientRect();
      const width = Math.max(360, Math.round(rect.width * this.deviceRatio));
      const height = Math.max(280, Math.round(rect.height * this.deviceRatio));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
      }
    }

    _project(point) {
      const rotated = rotatePoint(point, this.camera.yaw, this.camera.pitch);
      const depth = rotated.z + this.camera.zoom;
      const perspective = 1.9 / Math.max(1.08, depth);
      return {
        x: ((rotated.x + this.camera.panX) * perspective * this.canvas.height * 0.73) + (this.canvas.width * 0.5),
        y: ((rotated.y + this.camera.panY) * perspective * this.canvas.height * 0.73 * -1) + (this.canvas.height * 0.53),
        depth,
        scale: perspective
      };
    }

    _frame() {
      requestAnimationFrame(() => this._frame());
      if (!this.context || !this.canvas) {
        return;
      }
      const now = performance.now();
      const dt = Math.min(0.05, (now - this.lastFrameTime) / 1000);
      this.lastFrameTime = now;
      this.frameCounter += 1;
      this._resize();
      this._updateDynamicActivity(dt, now);
      this._render(now / 1000);
    }

    _spawnBurstForState(state, now) {
      const regionId = state === "execution" ? "execution" : state === "alert" ? "security" : state === "learning" ? "evolution" : "planning";
      const targetIndex = regionIdToIndex(regionId);
      const burstCount = state === "execution" ? 8 : 5;
      for (let index = 0; index < burstCount; index += 1) {
        const sample = this.scene.neurons[Math.floor(Math.random() * this.scene.neurons.length)];
        if (!sample || sample.regionWeights[targetIndex] < 0.18) {
          continue;
        }
        this.neuronActivation[sample.id] = clamp(this.neuronActivation[sample.id] + 0.95, 0, 1.6);
      }
      this.lastBurstTime = now;
    }

    _chooseSynapseIndex(state, rng) {
      const stateConfig = STATE_CONFIG[state];
      const useLong = rng() < stateConfig.longBias;
      const pool = useLong && this.scene.longSynapseIndices.length ? this.scene.longSynapseIndices : this.scene.localSynapseIndices;
      let bestIndex = pool[0];
      let bestScore = -1;
      const attempts = 24;
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        const synapseIndex = pool[Math.floor(rng() * pool.length)];
        const synapse = this.scene.synapses[synapseIndex];
        const affinity = synapse.affinity[state];
        const boost =
          (synapse.averageWeights[0] * this.regionBoosts.memory) +
          (synapse.averageWeights[1] * this.regionBoosts.planning) +
          (synapse.averageWeights[2] * this.regionBoosts.execution) +
          (synapse.averageWeights[3] * this.regionBoosts.security) +
          (synapse.averageWeights[4] * this.regionBoosts.evolution);
        const score = affinity + boost + (rng() * 0.18);
        if (score > bestScore) {
          bestScore = score;
          bestIndex = synapseIndex;
        }
      }
      return bestIndex;
    }

    _updateDynamicActivity(dt, now) {
      const state = this._currentState();
      const stateConfig = STATE_CONFIG[state];
      const rng = createRng((BRAIN_SEED ^ Math.floor(now)) >>> 0);

      for (let index = 0; index < this.neuronActivation.length; index += 1) {
        this.neuronActivation[index] *= 0.9;
      }

      while (this.pulses.length < stateConfig.pulseTarget) {
        const synapseIndex = this._chooseSynapseIndex(state, rng);
        this.pulses.push({
          synapseIndex,
          progress: Math.random(),
          speed: lerp(stateConfig.pulseSpeed[0], stateConfig.pulseSpeed[1], Math.random()),
          radius: 2.2 + (Math.random() * 1.4),
          color: blendColor(SYNAPSE_COLOR, stateConfig.tint, 0.34 + (Math.random() * 0.18))
        });
      }

      while (this.pulses.length > stateConfig.pulseTarget) {
        this.pulses.pop();
      }

      this.pulses.forEach((pulse, index) => {
        const synapse = this.scene.synapses[pulse.synapseIndex];
        if (!synapse) {
          return;
        }
        pulse.progress += dt * pulse.speed;
        if (pulse.progress >= 1) {
          pulse.synapseIndex = this._chooseSynapseIndex(state, rng);
          pulse.progress = 0;
          pulse.speed = lerp(stateConfig.pulseSpeed[0], stateConfig.pulseSpeed[1], Math.random());
          pulse.color = blendColor(SYNAPSE_COLOR, stateConfig.tint, 0.36 + (Math.random() * 0.18));
        }

        const sourceBoost = 0.18 + (0.32 * (1 - pulse.progress));
        const targetBoost = 0.18 + (0.32 * pulse.progress);
        this.neuronActivation[synapse.a] = clamp(this.neuronActivation[synapse.a] + sourceBoost, 0, 1.6);
        this.neuronActivation[synapse.b] = clamp(this.neuronActivation[synapse.b] + targetBoost, 0, 1.6);

        if (index % 6 === 0) {
          const midBoost = 0.12 + (0.18 * Math.sin((now * 0.003) + index));
          this.neuronActivation[synapse.a] = clamp(this.neuronActivation[synapse.a] + midBoost, 0, 1.6);
        }
      });

      if ((state === "execution" || state === "alert" || state === "learning") && (now - this.lastBurstTime) > 280) {
        this._spawnBurstForState(state, now);
      }

      this._updateHudCopy();
    }

    _pointOnSynapse(synapse, progress) {
      const source = this.scene.neurons[synapse.a];
      const target = this.scene.neurons[synapse.b];
      if (synapse.kind === "long") {
        const u = 1 - progress;
        return {
          x: (u * u * source.x) + (2 * u * progress * synapse.control.x) + (progress * progress * target.x),
          y: (u * u * source.y) + (2 * u * progress * synapse.control.y) + (progress * progress * target.y),
          z: (u * u * source.z) + (2 * u * progress * synapse.control.z) + (progress * progress * target.z)
        };
      }
      return {
        x: lerp(source.x, target.x, progress),
        y: lerp(source.y, target.y, progress),
        z: lerp(source.z, target.z, progress)
      };
    }

    _render(timeSeconds) {
      const context = this.context;
      const width = this.canvas.width;
      const height = this.canvas.height;
      const state = this._currentState();
      const stateConfig = STATE_CONFIG[state];

      const background = context.createLinearGradient(0, 0, 0, height);
      background.addColorStop(0, "#03070b");
      background.addColorStop(1, "#010305");
      context.fillStyle = background;
      context.fillRect(0, 0, width, height);

      const stateHalo = context.createRadialGradient(width * 0.5, height * 0.48, width * 0.08, width * 0.5, height * 0.5, width * 0.46);
      stateHalo.addColorStop(0, colorToRgba(blendColor([30, 60, 84], stateConfig.tint, 0.26), 0.2));
      stateHalo.addColorStop(1, "rgba(0, 0, 0, 0)");
      context.fillStyle = stateHalo;
      context.fillRect(0, 0, width, height);

      const projectedShell = this.scene.shellPoints.map((point) => {
        const rotatedNormal = normalize(rotatePoint(point.normal, this.camera.yaw, this.camera.pitch));
        const projected = this._project(point);
        return { ...projected, normalLight: clamp(dot(rotatedNormal, LIGHT), -1, 1), hemisphere: point.hemisphere };
      });
      projectedShell.sort((left, right) => left.depth - right.depth);
      projectedShell.forEach((point, index) => {
        const alpha = clamp(0.05 + ((point.normalLight + 1) * 0.08), 0.03, 0.18);
        const size = clamp((point.scale * 7.8) + (index % 2), 1.0, 4.4);
        const color = point.hemisphere < 0 ? [104, 156, 196] : [186, 176, 148];
        context.fillStyle = colorToRgba(color, alpha);
        context.beginPath();
        context.arc(point.x, point.y, size, 0, Math.PI * 2);
        context.fill();
      });

      this.scene.grooveCurves.forEach((curve, curveIndex) => {
        const points = curve.samples.map((sample) => this._project(sample));
        if (points.length < 2) {
          return;
        }
        context.save();
        context.strokeStyle = colorToRgba([115, 150, 170], 0.09 + (0.02 * Math.sin(timeSeconds + curve.phase)));
        context.lineWidth = 1 + (0.24 * Math.sin((timeSeconds * 0.6) + curveIndex));
        context.beginPath();
        context.moveTo(points[0].x, points[0].y);
        for (let index = 1; index < points.length; index += 1) {
          context.lineTo(points[index].x, points[index].y);
        }
        context.stroke();
        context.restore();
      });

      const projectedNeurons = this.scene.neurons.map((neuron) => ({ ...neuron, ...this._project(neuron) }));
      const projectedById = new Map(projectedNeurons.map((neuron) => [neuron.id, neuron]));
      const localIndices = this.scene.localSynapseIndices;
      const longIndices = this.scene.longSynapseIndices;
      const localWindow = Math.min(localIndices.length, this.mode === "expanded" ? 6800 : 5200);
      const localStart = localIndices.length ? ((this.frameCounter * 167) % localIndices.length) : 0;
      const activePulseEdges = new Set(this.pulses.map((pulse) => pulse.synapseIndex));
      context.lineCap = "round";

      for (let offset = 0; offset < localWindow; offset += 1) {
        const synapseIndex = localIndices[(localStart + offset) % localIndices.length];
        const synapse = this.scene.synapses[synapseIndex];
        const source = projectedById.get(synapse.a);
        const target = projectedById.get(synapse.b);
        const depth = (source.depth + target.depth) * 0.5;
        const alpha = 0.018 + (synapse.affinity[state] * 0.018) + (activePulseEdges.has(synapseIndex) ? 0.08 : 0);
        context.strokeStyle = colorToRgba(SYNAPSE_COLOR, clamp(alpha * (1.12 / depth), 0.01, 0.16));
        context.lineWidth = 0.32 + (synapse.affinity[state] * 0.22);
        context.beginPath();
        context.moveTo(source.x, source.y);
        context.lineTo(target.x, target.y);
        context.stroke();
      }

      longIndices.forEach((synapseIndex) => {
        const synapse = this.scene.synapses[synapseIndex];
        const source = projectedById.get(synapse.a);
        const target = projectedById.get(synapse.b);
        const control = this._project(synapse.control);
        const depth = (source.depth + target.depth + control.depth) / 3;
        const alpha = 0.03 + (synapse.affinity[state] * 0.026) + (activePulseEdges.has(synapseIndex) ? 0.1 : 0);
        context.strokeStyle = colorToRgba(SYNAPSE_COLOR, clamp(alpha * (1.18 / depth), 0.015, 0.22));
        context.lineWidth = 0.54 + (synapse.affinity[state] * 0.3);
        context.beginPath();
        context.moveTo(source.x, source.y);
        context.quadraticCurveTo(control.x, control.y, target.x, target.y);
        context.stroke();
      });

      this.pulses.forEach((pulse) => {
        const synapse = this.scene.synapses[pulse.synapseIndex];
        const worldPoint = this._pointOnSynapse(synapse, pulse.progress);
        const projected = this._project(worldPoint);
        const glowSize = (pulse.radius + (pulse.progress * 1.6)) * this.deviceRatio * projected.scale * 3.2;
        const gradient = context.createRadialGradient(projected.x, projected.y, 0, projected.x, projected.y, glowSize);
        gradient.addColorStop(0, colorToRgba(pulse.color, 0.92));
        gradient.addColorStop(1, colorToRgba(pulse.color, 0));
        context.fillStyle = gradient;
        context.beginPath();
        context.arc(projected.x, projected.y, glowSize, 0, Math.PI * 2);
        context.fill();
      });

      const depthSortedNeurons = projectedNeurons.slice().sort((left, right) => left.depth - right.depth);
      depthSortedNeurons.forEach((neuron) => {
        const activation = this.neuronActivation[neuron.id] || 0;
        const regionIndex = regionIdToIndex(neuron.dominantRegion);
        const regionBoost = this.regionBoosts[neuron.dominantRegion] || 0;
        const pulse = 0.5 + (0.5 * Math.sin((timeSeconds * neuron.flicker * 2.2) + neuron.phase));
        const accent = REGION_CONFIG[regionIndex].color;
        const color = blendColor(neuron.color, accent, clamp((0.18 + (activation * 0.2) + (regionBoost * 0.12)), 0, 0.52));
        const baseSize = clamp((neuron.size * neuron.scale * 3.0), 0.9, 5.8);
        const glowSize = baseSize * (1.6 + (pulse * 0.45) + (activation * 0.55));
        const glowAlpha = clamp(0.03 + (stateConfig.neuronBoost * 0.2) + (activation * 0.12), 0.03, 0.3);
        const bodyAlpha = clamp(0.34 + (activation * 0.32) + (regionBoost * 0.12), 0.3, 0.95);

        const gradient = context.createRadialGradient(neuron.x, neuron.y, 0, neuron.x, neuron.y, glowSize);
        gradient.addColorStop(0, colorToRgba(color, glowAlpha));
        gradient.addColorStop(1, colorToRgba(color, 0));
        context.fillStyle = gradient;
        context.beginPath();
        context.arc(neuron.x, neuron.y, glowSize, 0, Math.PI * 2);
        context.fill();

        context.fillStyle = colorToRgba(color, bodyAlpha);
        context.beginPath();
        context.arc(neuron.x, neuron.y, baseSize, 0, Math.PI * 2);
        context.fill();
      });

      context.save();
      context.strokeStyle = "rgba(145, 172, 195, 0.16)";
      context.setLineDash([6, 8]);
      context.beginPath();
      context.moveTo(width * 0.5, height * 0.16);
      context.lineTo(width * 0.5, height * 0.84);
      context.stroke();
      context.restore();
    }
  }

  const scene = new JarvisBrainScene();
  window.jarvisNativeBrainScene = {
    updateState(payload) {
      scene.updateState(payload || {});
    },
    resetView() {
      scene.resetView();
    }
  };
}());
