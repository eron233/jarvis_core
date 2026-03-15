/*
JARVIS - Controlador de atividade do cerebro visual

Responsavel por:
- manter o modo ativo de visualizacao
- centralizar estado compartilhado do brain avatar
*/

export class ActivityController {
  constructor() {
    this.level = "historica";
    this.mode = "visualizacao";
    this.evolution = null;
    this.analysis = null;
    this.proceduralOverlay = null;
  }

  setState(nextState) {
    this.level = nextState.level || this.level;
    this.mode = nextState.mode || this.mode;
    this.evolution = nextState.evolution || this.evolution;
    this.analysis = nextState.analysis || this.analysis;
    this.proceduralOverlay = nextState.proceduralOverlay || this.proceduralOverlay;
  }

  snapshot() {
    return {
      level: this.level,
      mode: this.mode,
      evolution: this.evolution,
      analysis: this.analysis,
      proceduralOverlay: this.proceduralOverlay,
    };
  }
}
