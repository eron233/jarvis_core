# Indice de Capacidades do Sistema

Projeto: Sistema Cognitivo JARVIS
Versao da arquitetura: 0.1.0
Entrypoint do runtime: `jarvis_core/runtime/internal_agent_runtime.py`
Entrypoint do processo continuo: `jarvis_core/main.py`
Idioma padrao: `pt-BR`

## Objetivo

Este indice oferece uma visao unica das capacidades atualmente implementadas no JARVIS, onde elas estao, como persistem estado e quais testes validam seu comportamento.

## Capacidades Centrais

| Capacidade | Estado | Arquivos principais | Persistencia | Cobertura de testes |
| --- | --- | --- | --- | --- |
| Identidade e principios constitucionais | Implementada | `constitutional_core/identity.json`, `constitutional_core/principles.json` | Arquivos JSON de configuracao | Indireta |
| Ciclo deterministico do planejador executivo | Implementada | `executive_planner/planner.py`, `executive_planner/prioritizer.py`, `executive_planner/validator.py`, `executive_planner/audit.py` | Log de auditoria em memoria | `tests/test_planner.py` |
| Fila persistente de tarefas | Implementada | `executive_planner/queue.py` | `executive_planner/task_queue_store.json` | `tests/test_task_queue_persistence.py` |
| Bootstrap do runtime e recuperacao apos reinicio | Implementada | `runtime/internal_agent_runtime.py`, `runtime/autonomy.py` | Fila e memoria semantica recarregadas no bootstrap | `tests/test_runtime_bootstrap.py`, `tests/test_task_queue_persistence.py`, `tests/test_main_loop.py` |
| Loop continuo do sistema | Implementada | `main.py`, `runtime/internal_agent_runtime.py` | Persistencia final de fila e memoria semantica no encerramento | `tests/test_main_loop.py` |
| Camada real de objetivos | Implementada | `intent_layer/goal_manager.py`, `intent_layer/goals.json` | `intent_layer/goals.json` | `tests/test_goal_manager.py` |
| API real do sistema | Implementada | `interface/api/app.py`, `runtime/internal_agent_runtime.py` | Reaproveita fila, memoria e objetivos persistidos do nucleo | `tests/test_api.py` |
| Painel mobile-first | Implementada | `interface/dashboard/index.html`, `interface/api/app.py` | Reaproveita a API e o mesmo token inicial | `tests/test_dashboard.py` |
| Autenticacao por dispositivo confiavel | Implementada | `interface/api/app.py`, `runtime/internal_agent_runtime.py`, `interface/dashboard/access_gate.html` | Variaveis de ambiente + sessao do painel + auditoria em memoria | `tests/test_api.py`, `tests/test_dashboard.py` |
| Relatorios operacionais completos | Implementada | `runtime/internal_agent_runtime.py`, `interface/api/app.py`, `interface/dashboard/index.html` | Reaproveita fila, memoria, auditoria e objetivos do nucleo | `tests/test_operational_reports.py` |
| Memoria episodica | Implementada | `memory_system/episodic_memory.py` | Somente em memoria | Indireta via testes de runtime |
| Memoria semantica com busca e snapshots | Implementada | `memory_system/semantic_memory.py` | `memory_system/semantic_memory_store.json` | `tests/test_semantic_memory.py`, `tests/test_runtime_bootstrap.py` |
| Memoria procedural | Implementada | `memory_system/procedural_memory.py` | Somente em memoria | Indireta via testes de runtime |
| Estrutura de despacho para workers | Implementada (minima) | `workers/worker_runtime.py`, `workers/worker_finance.py`, `workers/worker_studio.py`, `workers/worker_study.py` | Stateless | `tests/test_runtime_bootstrap.py` |
| Armazenamento de metas da camada de intencao | Estruturada | `intent_layer/goals.json` | Arquivo JSON | Nenhuma |
| Diretorios de infraestrutura e interface | Estruturados | `infrastructure/*`, `interface/*` | Nenhuma | Nenhuma |

## Capacidades do Planejador Executivo

- carregar tarefas enfileiradas por meio de `TaskQueue`
- priorizar tarefas de forma deterministica com base em `impact` e `urgency`
- validar tarefas antes da execucao
- selecionar uma tarefa executavel por ciclo
- reenfileirar trabalho adiado ou bloqueado
- despachar a execucao por meio do runtime
- registrar eventos de auditoria para `plan`, `prioritize`, `validate`, `schedule`, `execute` e `review`, com rotulos em pt-BR na camada visivel

Arquivos relacionados:

- `executive_planner/planner.py`
- `executive_planner/queue.py`
- `executive_planner/prioritizer.py`
- `executive_planner/validator.py`
- `executive_planner/audit.py`

## Capacidades do Runtime

- inicializar planner, memorias, workers e estado da fila
- recuperar tarefas persistidas da fila apos reinicio
- recarregar a memoria semantica no startup
- aplicar controle de autonomia antes da execucao
- despachar tarefas para workers por dominio
- armazenar resultados de tarefas concluidas na memoria semantica
- expor consulta de memoria semantica para uso posterior

Arquivos relacionados:

- `runtime/internal_agent_runtime.py`
- `runtime/autonomy.py`

## Capacidades do Processo Continuo

- subir o sistema por meio de um entrypoint unico
- executar o planner em loop controlado
- registrar logs por ciclo com `cycle_id`
- encerrar de forma graciosa por fila vazia, limite de ciclos ou sinal
- persistir fila e memoria semantica ao final do processo

Arquivo relacionado:

- `main.py`

## Capacidades da Camada de Objetivos

- registrar metas estrategicas e objetivos ativos
- calcular progresso por objetivo
- vincular tarefas a `parent_goal_id`
- propagar prioridade de objetivo para a tarefa
- atualizar estado do objetivo apos execucao no runtime
- gerar relatorios em pt-BR

Arquivos relacionados:

- `intent_layer/goal_manager.py`
- `intent_layer/goals.json`

## Capacidades da API

- expor healthcheck publico
- proteger endpoints com token minimo
- consultar estado do sistema
- executar um ciclo do planner sob demanda
- listar e adicionar tarefas
- consultar objetivos e memoria recente
- emitir relatorio operacional reutilizavel

Arquivos relacionados:

- `interface/api/app.py`
- `API_PTBR.md`

## Capacidades do Painel

- servir um painel HTML pela propria API
- funcionar em layout mobile-first
- aceitar comando textual simples
- mostrar estado, objetivos, tarefas e memoria recente
- reutilizar os mesmos endpoints operacionais da API

Arquivos relacionados:

- `interface/dashboard/index.html`
- `interface/api/app.py`

## Capacidades de Autenticacao Inicial

- validar token secreto em endpoints protegidos
- validar dispositivo confiavel principal por header
- negar acesso por token invalido, device ausente ou device nao autorizado
- registrar acessos autorizados e negados em auditoria
- proteger o painel com sessao de dispositivo confiavel

Arquivos relacionados:

- `interface/api/app.py`
- `interface/dashboard/access_gate.html`
- `runtime/internal_agent_runtime.py`

## Capacidades de Relatorio

- relatorio geral do sistema
- relatorio detalhado da fila
- relatorio operacional de objetivos
- relatorio operacional da memoria
- relatorio consolidado de auditoria
- healthcheck rico com verificacao de configuracao e acoplamento
- exibicao dos relatorios no painel mobile-first

Arquivos relacionados:

- `runtime/internal_agent_runtime.py`
- `interface/api/app.py`
- `interface/dashboard/index.html`

## Capacidades de Memoria

### Memoria Episodica

- registra eventos de bootstrap e despacho
- suporta consulta de eventos recentes

Arquivo:

- `memory_system/episodic_memory.py`

### Memoria Semantica

- armazena entradas estruturadas de memoria
- suporta pontuacao por sobreposicao de palavras-chave e tags
- suporta filtragem por dominio
- suporta save/load por snapshot JSON
- suporta helpers de compatibilidade para `upsert` e `get`

Arquivos:

- `memory_system/semantic_memory.py`
- `memory_system/semantic_memory_store.json`

### Memoria Procedural

- armazena procedimentos nomeados reutilizaveis
- atualmente registra as etapas do ciclo do planner

Arquivo:

- `memory_system/procedural_memory.py`

## Capacidades dos Workers

- `worker_runtime`: aceita tarefas do dominio de runtime
- `worker_finance`: aceita tarefas do dominio de financas
- `worker_studio`: aceita tarefas do dominio de estudio
- `worker_study`: aceita tarefas do dominio de estudo

O comportamento atual dos workers e propositalmente minimo e deterministico: cada worker retorna um payload padronizado de aceitacao e ainda nao integra ferramentas externas.

## Artefatos de Persistencia

- `executive_planner/task_queue_store.json`
  Finalidade: snapshot persistido da fila para recuperacao apos reinicio
- `memory_system/semantic_memory_store.json`
  Finalidade: snapshot persistido da memoria semantica

## Cobertura de Validacao

- `tests/test_planner.py`
  Cobre execucao do ciclo do planner, tratamento de tarefa invalida, tratamento de tarefa bloqueada e comportamento de fila vazia
- `tests/test_main_loop.py`
  Cobre bootstrap do processo continuo, loop minimo com fila vazia e recuperacao segura de reinicio
- `tests/test_goal_manager.py`
  Cobre estrutura de metas estrategicas e objetivos ativos, vinculo tarefa-objetivo e atualizacao de progresso apos execucao
- `tests/test_api.py`
  Cobre inicializacao da API, healthcheck, autenticacao minima e operacao dos endpoints principais
- `tests/test_dashboard.py`
  Cobre o redirecionamento raiz e a entrega do painel HTML mobile-first
- `tests/test_api.py`
  Tambem cobre token invalido, device invalido, ausencia de headers e acesso autorizado com device confiavel
- `tests/test_operational_reports.py`
  Cobre healthcheck rico, endpoints de relatorio e campos principais dos relatorios operacionais
- `tests/test_runtime_bootstrap.py`
  Cobre estado do bootstrap do runtime, execucao de ciclo do planner via runtime e integracao com consulta de memoria semantica
- `tests/test_semantic_memory.py`
  Cobre criacao de entrada semantica, busca por relevancia, filtragem por dominio e roundtrip de persistencia
- `tests/test_task_queue_persistence.py`
  Cobre roundtrip de persistencia da fila, recuperacao apos reinicio e consistencia de estado apos reload

## Lacunas Atuais

- o nucleo constitucional ainda e apenas configuracional e nao um motor executavel separado de validacao
- as implementacoes de workers continuam sendo stubs minimos de aceitacao
- a camada de objetivos ja existe, mas ainda nao gera tarefas derivadas automaticamente
- as camadas de infraestrutura e interface ainda sao placeholders de diretorio
- ainda nao existe interface mobile-first para uso cotidiano em celular
- a autenticacao atual e propositalmente simples e focada em um unico dispositivo confiavel, sem usuario root separado
- o painel ainda nao possui historico conversacional nem criacao guiada de tarefas
- os relatorios ainda nao incluem monitoramento de infraestrutura externa nem metricas de processo do servidor
- a memoria semantica ainda usa recuperacao deterministica por palavras-chave e nao embeddings nem busca vetorial

## Referencias de Origem

- `README.md`
- `ARCHITECTURE.md`
- `hardening_report.md`
- `../system_manifest.json`
