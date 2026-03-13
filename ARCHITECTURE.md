# Visao Geral da Arquitetura

Este documento descreve a arquitetura funcional atual do JARVIS e como os modulos cooperam para manter um unico nucleo operativo, auditavel e pronto para deploy simples.

## Nucleo Constitucional

Local: `constitutional_core/`

Define identidade, principios, limites operacionais e diretrizes de governanca. Essa camada continua sendo configuracional e nao foi alterada no bloco de preparacao para nuvem.

Artefatos principais:

- `constitutional_core/identity.json`
- `constitutional_core/principles.json`

## Planejador Executivo

Local: `executive_planner/`

Responsavel por executar o ciclo deterministico do planner:

- carregar tarefas da fila
- priorizar por impacto, urgencia e contexto
- validar tarefas antes da execucao
- selecionar a proxima tarefa executavel
- despachar para o runtime
- registrar auditoria de `plan`, `prioritize`, `validate`, `schedule`, `execute` e `review`

Artefatos principais:

- `executive_planner/planner.py`
- `executive_planner/queue.py`
- `executive_planner/prioritizer.py`
- `executive_planner/validator.py`
- `executive_planner/audit.py`

## Camada de Objetivos

Local: `intent_layer/`

Mantem metas estrategicas e objetivos ativos por meio de `GoalManager`, com persistencia local, progresso, prioridade e relatorios em pt-BR.

Capacidades atuais:

- separacao entre metas estrategicas e objetivos ativos
- prioridade por objetivo
- prazo opcional
- progresso por tarefas vinculadas
- persistencia de objetivos em JSON

Artefatos principais:

- `intent_layer/goal_manager.py`
- `intent_layer/goals.json`

## Sistema de Memoria

Local: `memory_system/`

Divide o conhecimento em tres formas:

- memoria episodica para eventos e historico recente
- memoria semantica para fatos e entradas pesquisaveis
- memoria procedural para sequencias reutilizaveis

No estado atual, a memoria semantica ja possui persistencia configuravel e recuperacao segura no startup.

Artefatos principais:

- `memory_system/episodic_memory.py`
- `memory_system/semantic_memory.py`
- `memory_system/procedural_memory.py`

## Workers

Local: `workers/`

Executores por dominio que recebem tarefas do runtime e devolvem respostas estruturadas e deterministicas. Ainda sao leves, mas ja participam do ciclo real do sistema.

Artefatos principais:

- `workers/worker_runtime.py`
- `workers/worker_finance.py`
- `workers/worker_studio.py`
- `workers/worker_study.py`

## Runtime

Local: `runtime/`

Camada central de operacao. Inicializa planner, memorias, workers e contexto de objetivos; expoe despacho de tarefas, relatórios operacionais e healthcheck rico.

Artefatos principais:

- `runtime/internal_agent_runtime.py`
- `runtime/autonomy.py`

## Processo Continuo

Local: `main.py`

Coordena o loop do sistema sem recriar inteligencia. Reaproveita o runtime existente, suporta `cycle_id`, fila vazia, reinicio seguro e encerramento gracioso com persistencia.

Capacidades atuais:

- bootstrap com fila, memoria e objetivos configuraveis
- recuperacao de arquivos ausentes
- recuperacao segura de JSON corrompido com backup
- logs legiveis em pt-BR durante bootstrap e shutdown

## API de Controle

Local: `interface/api/`

Camada FastAPI fina sobre o nucleo existente. A API nao substitui o runtime; apenas expõe capacidades ja implementadas.

Capacidades atuais:

- `/health` publico para deploy
- `/api/health` protegido com diagnostico rico
- status do sistema
- execucao manual de ciclos
- listagem e inclusao de tarefas
- consulta de objetivos
- consulta de memoria recente
- relatorios operacionais detalhados

## Painel Mobile-First

Local: `interface/dashboard/`

Painel HTML servido pela propria API. Mantem uma interface simples para celular, sem uma segunda stack de frontend.

Capacidades atuais:

- acesso por `/painel`
- sessao de dispositivo confiavel
- consulta de relatorios operacionais
- atualizacao de estado e memoria recente

## Autenticacao por Dispositivo Confiavel

Local principal: `interface/api/app.py`

Modelo atual de protecao:

- `JARVIS_TOKEN`
- `JARVIS_TRUSTED_DEVICE_ID`
- headers `X-Jarvis-Token` e `X-Jarvis-Device-Id`
- sessao derivada para liberar o painel
- auditoria de acessos autorizados e negados

## Relatorios Operacionais

Locais principais:

- `runtime/internal_agent_runtime.py`
- `interface/api/app.py`
- `interface/dashboard/index.html`

Os relatórios foram centralizados no runtime para evitar duplicacao de logica. A API os expõe e o painel apenas os consome.

Capacidades atuais:

- relatorio geral do sistema
- relatorio da fila
- relatorio de objetivos
- relatorio da memoria
- relatorio de auditoria
- healthcheck rico

## Preparacao para Nuvem

Locais principais:

- `runtime/system_config.py`
- `runtime/server.py`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `DEPLOY_PTBR.md`

O bloco 6 adicionou a camada minima de operacao em servidor simples:

- configuracao central por variaveis de ambiente
- paths persistentes configuraveis para fila, memoria, objetivos, logs e reports
- runner de servidor com API e loop continuo opcional
- logs de startup e shutdown
- relatorio de ambiente persistido em `reports/`
- preparacao para volume Docker em `data/`, `logs/` e `reports/`

## Estrategia de Deploy

O modo recomendado de operacao agora e:

1. carregar configuracao a partir de variaveis de ambiente
2. garantir diretorios persistentes
3. recuperar fila, memoria e objetivos
4. bootstrapar o runtime
5. subir a API
6. iniciar o loop continuo em background, se habilitado
7. persistir estado e emitir relatorio de shutdown ao encerrar

Essa estrategia foi mantida propositalmente simples para caber em uma VPS Linux barata, sem Kubernetes, sem filas distribuidas e sem componentes extras nesta fase.
