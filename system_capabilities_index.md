# Indice de Capacidades do Sistema

Projeto: Sistema Cognitivo JARVIS
Versao da arquitetura: 0.1.0
Idioma padrao: `pt-BR`
Entrypoint do runtime: `jarvis_core/runtime/internal_agent_runtime.py`
Entrypoint do loop local: `jarvis_core/main.py`
Entrypoint do servidor: `jarvis_core/runtime/server.py`

## Objetivo

Este indice resume o que ja existe no JARVIS, onde cada capacidade mora, como o estado persiste e quais testes cobrem o comportamento atual.

## Capacidades Centrais

| Capacidade | Estado | Arquivos principais | Persistencia | Testes |
| --- | --- | --- | --- | --- |
| Identidade e principios constitucionais | Implementada | `constitutional_core/identity.json`, `constitutional_core/principles.json` | JSON de configuracao | Indireta |
| Planejador executivo deterministico | Implementada | `executive_planner/planner.py`, `executive_planner/prioritizer.py`, `executive_planner/validator.py`, `executive_planner/audit.py` | Auditoria em memoria | `tests/test_planner.py` |
| Fila persistente de tarefas | Implementada | `executive_planner/queue.py` | JSON configuravel | `tests/test_task_queue_persistence.py` |
| Camada de objetivos | Implementada | `intent_layer/goal_manager.py` | JSON configuravel | `tests/test_goal_manager.py` |
| Memoria semantica persistente | Implementada | `memory_system/semantic_memory.py` | JSON configuravel | `tests/test_semantic_memory.py` |
| Loop continuo local | Implementada | `main.py` | Persistencia final de fila e memoria | `tests/test_main_loop.py` |
| Runtime operacional | Implementada | `runtime/internal_agent_runtime.py`, `runtime/autonomy.py` | Reaproveita fila, memoria e objetivos | `tests/test_runtime_bootstrap.py` |
| API HTTP | Implementada | `interface/api/app.py` | Reaproveita o nucleo | `tests/test_api.py` |
| Painel mobile-first | Implementada | `interface/dashboard/index.html`, `interface/dashboard/access_gate.html` | Sessao de dispositivo confiavel | `tests/test_dashboard.py` |
| Autenticacao por dispositivo confiavel | Implementada | `interface/api/app.py`, `runtime/internal_agent_runtime.py` | Variaveis de ambiente + auditoria | `tests/test_api.py`, `tests/test_dashboard.py` |
| Relatorios operacionais completos | Implementada | `runtime/internal_agent_runtime.py`, `interface/api/app.py` | Reaproveita estado do runtime | `tests/test_operational_reports.py` |
| Configuracao central de ambiente | Implementada | `runtime/system_config.py`, `.env.example` | Variaveis de ambiente | `tests/test_cloud_deploy.py` |
| Servidor para VPS simples | Implementada | `runtime/server.py` | `logs/` e `reports/` configuraveis | `tests/test_cloud_deploy.py` |
| Preparacao para container | Implementada | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Volumes `data/`, `logs/`, `reports/` | Validacao documental + `tests/test_cloud_deploy.py` |
| Nucleo de conhecimento defensivo | Implementada | `security/security_knowledge_core.py`, `security/__init__.py` | Exportavel para memorias do sistema | `tests/test_security_knowledge_core.py` |

## Capacidades do Runtime

- bootstrapar planner, fila, memoria, objetivos e workers
- recuperar fila, memoria e objetivos no startup
- registrar eventos episodicos e relatorios operacionais
- proteger execucao por regras de autonomia
- persistir estado no shutdown

## Capacidades da API

- healthcheck publico em `/health`
- healthcheck rico protegido em `/api/health`
- status do sistema
- execucao de ciclo do planner
- listagem e criacao de tarefas
- consulta de objetivos
- consulta de memoria recente
- relatorios completos de sistema, fila, objetivos, memoria e auditoria

## Capacidades do Deploy

- start unico por `python -m runtime.server`
- start em container por `docker compose up --build -d`
- configuracao por variaveis de ambiente
- logs em `logs/jarvis.log`
- relatorio de ambiente em `reports/environment_report.json`
- relatorio de shutdown em `reports/shutdown_report.json`
- recuperacao segura de arquivo JSON corrompido com backup `.corrompido-*.json`

## Capacidades de Autodefesa

- organizar conhecimento defensivo por dominio
- mapear controles de identidade e acesso
- mapear controles de aplicacao
- mapear controles de infraestrutura
- mapear controles de continuidade
- mapear controles de observabilidade
- exportar sementes para memoria semantica
- exportar guias para memoria procedural

## Artefatos de Persistencia

- `data/task_queue_store.json`
  Finalidade: fila persistente do planner
- `data/semantic_memory_store.json`
  Finalidade: memoria semantica persistente
- `data/goals.json`
  Finalidade: objetivos persistentes
- `logs/jarvis.log`
  Finalidade: log operacional do servidor
- `reports/environment_report.json`
  Finalidade: resumo do ambiente no startup
- `reports/shutdown_report.json`
  Finalidade: resumo persistido no encerramento

## Cobertura de Validacao

- `tests/test_planner.py`
  Ciclo do planner, tarefa invalida, tarefa bloqueada e fila vazia
- `tests/test_main_loop.py`
  Loop minimo, bootstrap com persistencia e reinicio seguro
- `tests/test_goal_manager.py`
  Metas estrategicas, objetivos ativos e progresso
- `tests/test_api.py`
  API principal, autenticacao e operacao dos endpoints
- `tests/test_dashboard.py`
  Redirecionamento raiz e protecao do painel
- `tests/test_operational_reports.py`
  Healthcheck rico e endpoints de relatorio
- `tests/test_runtime_bootstrap.py`
  Bootstrap do runtime e execucao de ciclo
- `tests/test_semantic_memory.py`
  Busca, dominio e persistencia da memoria semantica
- `tests/test_task_queue_persistence.py`
  Persistencia e recuperacao da fila
- `tests/test_cloud_deploy.py`
  Configuracao de ambiente, startup em paths configuraveis, healthcheck de deploy e recuperacao de storage corrompido
- `tests/test_security_knowledge_core.py`
  Dominios defensivos, controles estruturados e semeadura de memoria semantica/procedural

## Lacunas Atuais

- ainda nao houve smoke test real de container neste ambiente por ausencia de `docker`
- os workers continuam minimos e seguros
- a modelagem de ameaca, o gemeo de seguranca e a remediacao assistida ainda nao foram implementados
- a geracao controlada de tarefas ainda nao foi implementada
- a memoria procedural ainda nao saiu do nivel inicial
- o monitoramento externo de infraestrutura ainda nao foi adicionado
