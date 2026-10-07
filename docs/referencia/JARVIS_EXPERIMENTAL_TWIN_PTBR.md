# JARVIS Experimental Twin — Arquitetura de Segurança e Melhoria Contínua

**Status:** projeto arquitetural em `dev`  
**Data:** 2026-10-07

## 1. Mudança de conceito

O componente atual `security/security_twin.py` é útil como snapshot sanitizado e mecanismo defensivo, mas não representa ainda um gêmeo experimental executável completo.

A arquitetura alvo passa a possuir um **JARVIS Experimental Twin** como guarda-chuva. O atual Security Twin torna-se uma especialização dentro dele.

```text
                 JARVIS VALIDADO
                       |
                 baseline congelado
                       |
             JARVIS EXPERIMENTAL TWIN
       +---------------+----------------+
       |               |                |
   Segurança        Melhoria        Compatibilidade
       |               |                |
       +------- Qualidade/Desempenho ----+
                       |
                 evidência objetiva
                       |
              candidato aprovado?
                  /          \
               não            sim
               |              |
          descartar/log    dev -> testes
                               |
                            validado
```

## 2. O Twin não "acha"; ele demonstra

Nenhum achado recebe os rótulos "vulnerabilidade", "melhoria", "regressão corrigida" ou "zero-day" apenas porque um LLM o sugeriu.

### Para segurança, evidência mínima
- input/test case reproduzível;
- comportamento observado;
- stack/crash/log ou violação de propriedade;
- versão/commit;
- ambiente;
- redução/minimização do caso quando possível;
- teste de regressão;
- classificação separada da descoberta.

### Para melhoria, evidência mínima
- baseline;
- candidato;
- mesma carga/corpus;
- métricas antes/depois;
- número de repetições quando houver ruído;
- regressões;
- custo de recursos;
- decisão explícita.

## 3. Trilhos experimentais

### A. Segurança
Objetivos:
- vulnerabilidades reais no nosso código;
- falhas de validação;
- crash/DoS local;
- bypass de invariantes;
- dependências vulneráveis;
- exposição de segredos;
- dataflow perigoso;
- condições inesperadas em APIs.

Candidatos:
- Bandit / Ruff para gates rápidos;
- Joern para dataflow/CPG profundo;
- Hypothesis para property tests;
- Schemathesis para FastAPI/OpenAPI;
- ClusterFuzzLite para fuzzing contínuo em componentes adequados;
- AFL++ para código nativo quando aplicável;
- OSV-Scanner e, sob demanda, Syft + Grype;
- Promptfoo para superfícies agentivas/prompt injection e políticas de IA.

### B. Qualidade e confiabilidade
Objetivos:
- respostas corretas;
- uso correto de ferramentas;
- grounding;
- redução de alucinação;
- structured outputs;
- capacidade pt-BR;
- regressões em tarefas históricas.

Ferramentas:
- pytest/suite própria;
- datasets dourados do JARVIS;
- Promptfoo;
- lm-evaluation-harness quando o modelo for definido;
- testes metamórficos/property-based quando aplicável.

### C. Desempenho e recursos
Objetivos:
- latência;
- throughput;
- RAM/VRAM;
- CPU/GPU;
- custo térmico/energia quando mensurável;
- cache hit;
- tempo de boot;
- custo de tool calls.

Ferramentas:
- py-spy para profiling externo leve;
- Scalene sob demanda;
- métricas nativas do runtime;
- Optuna para busca de configuração, sempre limitada por orçamento.

### D. Capacidade e integração
Objetivos:
- comparar componente atual vs nova tecnologia;
- medir ganhos reais da integração;
- detectar duplicação;
- testar fallback/degradação graciosa;
- comprovar Windows/offline/pt-BR.

Exemplos:
- busca atual vs SearXNG+Crawl4AI;
- parser atual vs Docling/Marker;
- OCR atual vs PP-OCRv6;
- graphify atual vs codebase-memory;
- contexto de desenvolvimento com/sem Graft.

### E. Modelo e adapters — FUTURO
Somente após escolha do modelo-base:
- quantizações;
- prompts;
- sampling;
- context strategy;
- LoRA/PEFT;
- SFT/DPO/GRPO quando houver justificativa;
- distillation;
- roteamento entre adapters/modelos.

Ferramentas candidatas:
- PEFT;
- TRL;
- Unsloth;
- lm-eval;
- Promptfoo.

## 4. Unidade de trabalho: Experiment Manifest

Todo experimento deve nascer com um manifest equivalente a:

```json
{
  "experiment_id": "exp-...",
  "hypothesis": "descricao falsificavel",
  "baseline_commit": "...",
  "candidate_commit": "...",
  "changed_components": [],
  "dataset_or_cases": [],
  "metrics": [],
  "resource_budget": {
    "max_runtime_seconds": 0,
    "max_ram_mb": 0,
    "max_cpu_percent": 0
  },
  "isolation_tier": "process|container|vm",
  "seed": null,
  "expected_benefit": "",
  "known_risks": []
}
```

O experimento deve terminar em estado:
- `improved`;
- `neutral`;
- `regressed`;
- `inconclusive`;
- `invalid_experiment`.

Nunca em `success` sem explicar qual métrica melhorou.

## 5. Evidence Bundle

Cada execução relevante deve produzir:
- manifest original;
- versões das ferramentas;
- commit baseline/candidato;
- logs;
- stdout/stderr relevante;
- casos de falha;
- métricas brutas;
- resumo estatístico;
- relatório de regressões;
- hash dos artefatos;
- recomendação separada da evidência.

A recomendação pode estar errada; os artefatos precisam permitir que um humano confira.

## 6. Isolamento por risco

O `runtime/tool_developer_engine.py` atual usa subprocesso e timeout, porém isso **não é sandbox forte**: ele herda grande parte do ambiente do processo e não constitui fronteira suficiente para código não confiável.

Arquitetura alvo:

1. **Tier 0 — análise sem execução:** AST, lint, static analysis.
2. **Tier 1 — processo restrito:** somente para código nosso de baixo risco, ambiente allowlist e sem segredos.
3. **Tier 2 — container/WSL2:** candidato com filesystem/network limitados.
4. **Tier 3 — VM/Windows Sandbox/microVM:** código gerado, dependências desconhecidas ou experimento de segurança com risco maior.

Candidatos de infraestrutura: MXC para políticas portáveis, containers/WSL2 para rotina e VM/Windows Sandbox para isolamento forte. Wasmtime/WASI pode ser usado quando uma ferramenta puder ser empacotada como WebAssembly.

## 7. Loop contínuo sem loop destrutivo

"Contínuo" não significa busy-loop infinito.

O Twin opera como uma fila de jobs finitos:

```text
descobrir hipótese
      ↓
priorizar
      ↓
criar checkpoint
      ↓
executar com orçamento
      ↓
coletar evidência
      ↓
comparar baseline
      ↓
registrar
      ↓
próxima hipótese
```

O sistema pode pausar para:
- atualização do baseline;
- mudança de branch;
- temperatura/recursos;
- manutenção;
- falta de caso novo;
- aprovação humana;
- dependência indisponível.

Depois retoma do checkpoint, não do zero.

## 8. Autoevolução permitida

O Twin pode autonomamente:
- gerar casos de teste;
- variar parâmetros;
- criar branches/candidatos isolados;
- gerar patches candidatos;
- criar testes de regressão;
- comparar ferramentas;
- otimizar thresholds/configurações;
- minimizar reproduções;
- produzir relatórios;
- recomendar promoção.

O Twin **não** deve autonomamente:
- promover direto para `master`;
- alterar o JARVIS validado sem gate;
- usar credenciais do proprietário em código experimental;
- transformar hipótese em fato;
- classificar um crash como zero-day sem análise;
- atacar sistemas de terceiros fora de escopo autorizado.

## 9. Fluxo de promoção

```text
Experimental Twin
      |
candidato + evidence bundle
      |
     dev
      |
suite completa + regressões
      |
   validado
      |
(revisão/uso futuro)
      |
   staging
      |
produção, apenas quando autorizado
```

A branch `staging` permanece fora do fluxo ativo nesta fase, conforme decisão do projeto.

## 10. Correção necessária no estado atual

`security/vulnerability_hunter.py` contém lógica simulada que pode produzir textos como vulnerabilidade/zero-day sem execução de um fuzzer real. Isso deve ser tratado como **placeholder não confiável** até reimplementação.

A futura correção não será "trocar a frase". Será mudar o contrato:
- nenhum finding sem evidence object;
- nenhum zero-day sem reprodução;
- nenhum score de severidade sem dados;
- simulações precisam carregar `simulation: true` e nunca alimentar relatórios de achados reais.

O mesmo princípio deve ser aplicado a outros módulos simulados identificados na auditoria.

## 11. Métrica-mãe do Twin

O objetivo do Twin não é maximizar número de alterações. É maximizar:

**capacidade confiável por unidade de recurso, sem regressão constitucional.**

Uma alteração que aumenta um benchmark em 5% mas dobra RAM, quebra pt-BR ou reduz confiabilidade pode ser rejeitada.

## 12. Estado desta proposta

Arquitetura aprovada conceitualmente pelo direcionamento do projeto, mas ainda não implementada no runtime. A implementação deve ocorrer incrementalmente, um bloco por vez, em `dev`, com testes antes de `validado`.
