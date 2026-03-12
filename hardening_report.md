# Relatorio de Hardening do JARVIS

Data: 2026-03-12
Workspace: `C:\Users\User\Documents\jarvis_core`

## Escopo

Esta etapa combinou:

- hardening de arquitetura e codigo
- suporte deterministico a fila persistente de tarefas
- validacao de recuperacao apos reinicio

## Arquivos Revisados

- `.gitignore`
- `README.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `DEV_SESSION_CONTINUE.md`
- `constitutional_core/identity.json`
- `constitutional_core/principles.json`
- `executive_planner/audit.py`
- `executive_planner/planner.py`
- `executive_planner/prioritizer.py`
- `executive_planner/queue.py`
- `executive_planner/validator.py`
- `intent_layer/goals.json`
- `memory_system/episodic_memory.py`
- `memory_system/procedural_memory.py`
- `memory_system/semantic_memory.py`
- `memory_system/semantic_memory_store.json`
- `runtime/autonomy.py`
- `runtime/internal_agent_runtime.py`
- `workers/worker_runtime.py`
- `workers/worker_finance.py`
- `workers/worker_studio.py`
- `workers/worker_study.py`
- `tests/test_planner.py`
- `tests/test_runtime_bootstrap.py`
- `tests/test_semantic_memory.py`

## Problemas Encontrados

- `executive_planner/queue.py` existia apenas em memoria e nao sobrevivia a reinicializacao do processo.
- O bootstrap do runtime nao restaurava o trabalho enfileirado a partir do disco.
- O formato da tarefa na fila estava subespecificado para persistencia e recuperacao.
- O planejador duplicava a logica de esvaziamento da fila em vez de delegar essa responsabilidade ao modulo da fila.
- `executive_planner/prioritizer.py` considerava apenas `importance`, enquanto o novo esquema da fila exige `impact`.
- Os testes de persistencia eram mais estreitos do que o ideal porque a fila persistente ainda nao tinha cobertura direta.
- Instancias vazias de `TaskQueue` passaram a ser avaliadas como falsas apos a adicao de `__len__`, expondo um bug oculto de injecao de dependencia no fallback entre planner e runtime.

## Melhorias Aplicadas

- Implementado armazenamento persistente da fila em `executive_planner/queue.py`.
- Adicionado suporte a snapshot em disco em `executive_planner/task_queue_store.json`.
- Adicionados `save_to_disk()`, `load_from_disk()`, `drain()`, `__len__()` e `auto_persist_on_change()` em `TaskQueue`.
- Normalizadas as tarefas persistidas para preservar:
  - `task_id`
  - `description`
  - `domain`
  - `urgency`
  - `impact`
  - `cost`
  - `reversibility`
  - `risk`
  - `approval`
  - `state`
  - `evidence`
  - `parent_goal`
  - timestamps
- Atualizado o bootstrap do runtime para recarregar a fila a partir do disco no reinicio e persistir mutacoes posteriores.
- Simplificado o carregamento de tarefas no planner ao substituir o loop manual de dequeue por `TaskQueue.drain()`.
- Endurecida a injecao de dependencias entre planner e runtime ao trocar fallbacks falsy com `or` por verificacoes explicitas com `is None`.
- Atualizada a priorizacao para usar `impact` com fallback para `importance`.
- Fortalecidos os testes com cobertura direta para persistencia da fila e recuperacao apos reinicio.
- Substituido o comportamento fragil com diretorios temporarios mockados nos testes de memoria semantica por arquivos deterministas dentro da workspace.
- Adicionados diretorios de artefatos de teste ignorados no `.gitignore` para manter a execucao limpa.

## O Que Foi Removido

- Removido o loop manual de drenagem da fila no planner, delegando essa responsabilidade para `TaskQueue`.
- Removido o patch baseado em mock de arquivo de memoria semantica em `tests/test_semantic_memory.py`, substituindo por persistencia real dentro da workspace.
- Removido o fallback implicito falsy que trocava filas vazias injetadas por instancias padrao de fila.

Nenhum arquivo-fonte rastreado foi excluido nesta etapa.

## O Que Foi Mantido Intencionalmente

- `constitutional_core/*` foi mantido sem alteracoes por desenho.
- `executive_planner/planner.py:create_plan()` foi mantido mesmo fora do fluxo atual de execucao, porque continua pertencendo a superficie planejada do planner.
- Importacoes tardias dentro de `runtime/internal_agent_runtime.py:bootstrap()` foram mantidas para evitar pressao de importacao circular entre runtime e planner.
- `workers/*.py` permanecem como stubs minimos porque ainda sao pontos de extensao intencionais para o despacho futuro do runtime.
- Placeholders `.gitkeep` sob `infrastructure/`, `interface/` e `tests/` foram mantidos porque preservam a estrutura de repositorio solicitada.
- O comportamento de persistencia da memoria semantica nao foi refatorado alem do endurecimento dos testes, porque esta etapa foi focada em persistencia da fila.

## Riscos Detectados

- `executive_planner/task_queue_store.json` usa JSON simples sem file locking, entao gravacoes concorrentes entre processos continuam inseguras.
- A pontuacao da fila permanece propositalmente simples e deterministica; ela ainda nao considera `cost`, `reversibility` ou `risk` na agenda de execucao.
- O runtime ainda registra entradas semanticas em memoria durante bootstrap e despacho sem recarregar automaticamente o historico semantico no startup.
- Os handlers de workers continuam sendo stubs de aceitacao, entao a execucao em runtime esta estruturalmente correta, mas operacionalmente rasa.

## Testes e Validacao

Executado:

- `python -m unittest discover -s tests -v`

Resultado:

- 12 testes aprovados

Cobertura adicionada para:

- roundtrip de persistencia da fila
- recuperacao do runtime a partir de estado persistido da fila
- consistencia do estado da fila apos reload
- manutencao do comportamento existente de planner, runtime e memoria semantica apos a integracao da persistencia
