# Relatorio de Localizacao pt-BR

## Objetivo

Converter a camada externa e operacional visivel do JARVIS para portugues do Brasil sem alterar identificadores internos estaveis nem recriar arquitetura.

## Arquivos inspecionados

- `C:\Users\User\Documents\jarvis_core\README.md`
- `C:\Users\User\Documents\jarvis_core\main.py`
- `C:\Users\User\Documents\jarvis_core\intent_layer\goal_manager.py`
- `C:\Users\User\Documents\jarvis_core\interface\api\app.py`
- `C:\Users\User\Documents\jarvis_core\interface\dashboard\index.html`
- `C:\Users\User\Documents\jarvis_core\API_PTBR.md`
- `C:\Users\User\Documents\jarvis_core\ARCHITECTURE.md`
- `C:\Users\User\Documents\jarvis_core\CHANGELOG.md`
- `C:\Users\User\Documents\jarvis_core\DEV_SESSION_CONTINUE.md`
- `C:\Users\User\Documents\jarvis_core\hardening_report.md`
- `C:\Users\User\Documents\jarvis_core\system_capabilities_index.md`
- `C:\Users\User\Documents\jarvis_core\executive_planner\audit.py`
- `C:\Users\User\Documents\jarvis_core\executive_planner\planner.py`
- `C:\Users\User\Documents\jarvis_core\executive_planner\prioritizer.py`
- `C:\Users\User\Documents\jarvis_core\executive_planner\queue.py`
- `C:\Users\User\Documents\jarvis_core\executive_planner\validator.py`
- `C:\Users\User\Documents\jarvis_core\runtime\autonomy.py`
- `C:\Users\User\Documents\jarvis_core\runtime\internal_agent_runtime.py`
- `C:\Users\User\Documents\jarvis_core\memory_system\episodic_memory.py`
- `C:\Users\User\Documents\jarvis_core\memory_system\procedural_memory.py`
- `C:\Users\User\Documents\jarvis_core\memory_system\semantic_memory.py`
- `C:\Users\User\Documents\jarvis_core\workers\worker_runtime.py`
- `C:\Users\User\Documents\jarvis_core\workers\worker_finance.py`
- `C:\Users\User\Documents\jarvis_core\workers\worker_studio.py`
- `C:\Users\User\Documents\jarvis_core\workers\worker_study.py`
- `C:\Users\User\Documents\jarvis_core\tests\test_planner.py`
- `C:\Users\User\Documents\jarvis_core\tests\test_runtime_bootstrap.py`
- `C:\Users\User\Documents\jarvis_core\tests\test_main_loop.py`
- `C:\Users\User\Documents\jarvis_core\tests\test_semantic_memory.py`
- `C:\Users\User\Documents\jarvis_core\tests\test_task_queue_persistence.py`
- `C:\Users\User\Documents\system_manifest.json`
- `C:\Users\User\Documents\scaffold_validation.md`
- `C:\Users\User\Documents\jarvis_core\constitutional_core\identity.json`
- `C:\Users\User\Documents\jarvis_core\constitutional_core\principles.json`
- `C:\Users\User\Documents\jarvis_core\intent_layer\goals.json`

## Arquivos traduzidos

- Documentacao principal e operacional em Markdown.
- Manifestos e arquivos JSON descritivos.
- Docstrings, comentarios e mensagens visiveis em modulos do planner, runtime, memoria e workers.
- Mensagens do processo continuo inicial em `main.py`.
- Relatorios e labels da camada de objetivos em `goal_manager.py`.
- Mensagens, rotas e documentacao visivel da API em pt-BR.
- Painel web inicial com labels e fluxo de uso em pt-BR.
- Rotulos expostos ao usuario por meio de equivalentes pt-BR em auditoria, estado de tarefa, status de runtime e motivos de bloqueio.
- Testes atualizados para validar a superficie localizada sem quebrar os identificadores internos.

## Arquivos mantidos em ingles e por que

- Nomes de arquivos Python, classes, funcoes e modulos: preservados para estabilidade arquitetural e compatibilidade com imports.
- Valores internos estaveis como `status`, `event`, `reason` e `state`: mantidos em ingles para nao quebrar fluxo interno, testes preexistentes e persistencia ja consolidada.
- Artefatos de persistencia `task_queue_store.json` e `semantic_memory_store.json`: mantidos como artefatos de dados, sem traducao estrutural para evitar migracao desnecessaria.

## Termos padronizados

- `pending` -> `pendente`
- `running` -> `em_execucao`
- `blocked` -> `bloqueada`
- `completed` -> `concluida`
- `failed` -> `falhou`
- `awaiting_approval` -> `aguardando_aprovacao`
- `initialized` -> `inicializado`
- `idle` -> `ociosa`
- `executed` -> `executada`
- `rejected` -> `rejeitada`
- `accepted` -> `aceita`
- `queued` -> `na_fila`
- `scheduled` -> `agendada`
- `executing` -> `em_execucao`
- `deferred` -> `adiada`
- `selected` -> `selecionada`
- `plan` -> `planejar`
- `prioritize` -> `priorizar`
- `validate` -> `validar`
- `schedule` -> `agendar`
- `execute` -> `executar`
- `review` -> `revisar`
- `bootstrap` -> `inicializar`
- `dispatch` -> `despachar`
- `no_tasks` -> `sem_tarefas`
- `no_executable_task` -> `sem_tarefa_executavel`
- `autonomy_gate` -> `bloqueada_pela_politica_de_autonomia`
- `unknown_worker` -> `worker_desconhecido`

## Possiveis impactos

- Consumidores externos agora podem usar campos localizados como `status_ptbr`, `state_ptbr`, `event_ptbr` e `reason_ptbr`.
- Integracoes que dependem apenas dos campos internos continuam funcionando porque as chaves originais foram preservadas.
- Consultas textuais em memoria semantica ficaram mais naturais em pt-BR para uso operacional real.
- Snapshots antigos podem continuar contendo alguns textos em ingles ate serem regravados pelo fluxo normal do sistema.

## O que ficou pendente

- Revisao futura de artefatos de dados historicos ja persistidos antes da localizacao, caso seja necessario migrar conteudo textual antigo.
- Expansao opcional da localizacao para interfaces ainda vazias em `api`, `cli` e `dashboard` quando essas camadas passarem a ter comportamento visivel ao usuario.

## Resultado

- A camada externa e operacional visivel ao usuario foi localizada para pt-BR.
- A arquitetura foi preservada.
- Nenhum modulo foi recriado.
- Nenhuma duplicacao desnecessaria foi introduzida.
