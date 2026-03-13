# Sistema Cognitivo JARVIS

O JARVIS e um sistema cognitivo modular em construcao, projetado para coordenar planejamento, memoria, objetivos, controle de execucao, API de acesso e workers especializados. O repositorio ja opera em um estado funcional inicial com bootstrap do runtime, fila persistente, memoria semantica, loop continuo de sistema, camada real de objetivos e API FastAPI integrada ao nucleo.

Idioma padrao do sistema: `pt-BR`

## Visao Geral da Arquitetura

O scaffold atual esta organizado em um conjunto enxuto de camadas cooperativas:

- `constitutional_core/`: identidade e principios de governanca do sistema
- `executive_planner/`: fila, priorizacao, validacao, auditoria e construcao de planos
- `intent_layer/`: metas estrategicas, objetivos ativos, restricoes e preferencias operacionais
- `memory_system/`: memoria episodica, semantica e procedural
- `workers/`: workers especializados para tarefas de runtime, financas, estudio e estudo
- `runtime/`: bootstrap do runtime e logica de autonomia
- `main.py`: entrypoint do processo continuo inicial do sistema
- `interface/api/`: API minima de acesso ao sistema
- `infrastructure/`: placeholders de deploy, persistencia e monitoramento
- `interface/`: placeholders de API, CLI e dashboard
- `tests/`: local da suite de testes e cobertura de regressao

## Entrypoints

Bootstrap interno do runtime:

- `runtime/internal_agent_runtime.py`

Processo continuo inicial do sistema:

- `main.py`

## Explicacao dos Modulos

### Nucleo Constitucional

Define a identidade do sistema e os principios que restringem planejamento e execucao.

### Planejador Executivo

Fornece a cadeia inicial de planejamento: entrada de tarefas, priorizacao, validacao, auditoria e montagem de plano.

### Camada de Intencao

Armazena metas estrategicas, objetivos ativos, restricoes e preferencias operacionais que orientam as decisoes do planejador. A camada agora conta com `GoalManager` para leitura, atualizacao, progresso, prioridades e relatarios em pt-BR.

### Sistema de Memoria

Separa as responsabilidades de memoria entre lembrancas episodicas, fatos semanticos e rotinas procedurais.

### Estrutura de Workers

Hospeda adaptadores especializados que podem aceitar tarefas orientadas por dominio.

### Motor de Runtime

Inicializa o estado ativo do sistema e aplica controle de autonomia com supervisao.

### Processo Continuo do Sistema

Coordena o bootstrap do runtime, recupera fila e memoria semantica persistidas, executa ciclos sucessivos do planner, registra logs por ciclo e realiza encerramento gracioso com persistencia final de estado.

### API de Controle

Exponibiliza acesso externo ao runtime por meio de endpoints seguros para status, execucao de ciclo, fila, objetivos, memoria e relatorio operacional.

## Execucao Inicial

Exemplo de subida local com um ciclo controlado:

```powershell
python main.py --max-cycles 1 --stop-when-idle
```

Exemplo de subida local da API:

```powershell
set JARVIS_API_TOKEN=seu_token_seguro
python -m uvicorn interface.api.app:app --host 0.0.0.0 --port 8000
```

## Fluxo de Desenvolvimento

1. Crie ou atualize modulos de arquitetura dentro do subsistema correspondente.
2. Adicione ou expanda testes em `tests/` conforme a integracao do runtime evoluir.
3. Atualize `ARCHITECTURE.md`, `system_capabilities_index.md` e os relatorios obrigatorios ao concluir um bloco.
4. Registre marcos arquiteturais visiveis ao usuario em `CHANGELOG.md`.
5. Gere um checkpoint git ao final de cada ciclo de implementacao.
6. Revise `git status` antes de cada commit para garantir que apenas arquivos intencionais sejam rastreados.
