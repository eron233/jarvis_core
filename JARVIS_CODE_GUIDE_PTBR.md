# Guia de Codigo do JARVIS

## Visao geral

O JARVIS e um sistema cognitivo modular com runtime compartilhado, planejamento deterministico, memorias persistentes, camada de objetivos, API HTTP protegida e workers por dominio. O codigo foi organizado para que o runtime central seja reutilizado por:

- loop continuo local
- servidor HTTP
- API FastAPI
- painel web
- testes automatizados

## Fluxo principal de execucao

1. O sistema sobe por [main.py](/C:/Users/User/Documents/jarvis_core/main.py) ou [runtime/server.py](/C:/Users/User/Documents/jarvis_core/runtime/server.py).
2. O bootstrap instancia [InternalAgentRuntime](/C:/Users/User/Documents/jarvis_core/runtime/internal_agent_runtime.py), carrega fila, objetivos e memorias persistentes.
3. O planner em [planner.py](/C:/Users/User/Documents/jarvis_core/executive_planner/planner.py) drena a fila, prioriza, valida e agenda tarefas.
4. O runtime consulta politica constitucional e gate de autonomia antes do dispatch.
5. O worker correto executa a tarefa e devolve resposta estruturada.
6. O runtime registra auditoria, memoria episodica, memoria semantica e memoria procedural.
7. A API em [app.py](/C:/Users/User/Documents/jarvis_core/interface/api/app.py) expõe status, fila, objetivos, memoria e relatorios.

## Papel de cada diretorio

- [constitutional_core](/C:/Users/User/Documents/jarvis_core/constitutional_core): identidade, principios e politica viva que governa validator e runtime.
- [executive_planner](/C:/Users/User/Documents/jarvis_core/executive_planner): fila persistente, priorizacao, validacao, auditoria e ciclo do planner.
- [runtime](/C:/Users/User/Documents/jarvis_core/runtime): bootstrap do nucleo, gate de autonomia, configuracao e servidor HTTP.
- [memory_system](/C:/Users/User/Documents/jarvis_core/memory_system): memorias episodica, semantica e procedural.
- [intent_layer](/C:/Users/User/Documents/jarvis_core/intent_layer): metas estrategicas, objetivos ativos e progresso por objetivo.
- [workers](/C:/Users/User/Documents/jarvis_core/workers): executores por dominio com retorno estruturado.
- [interface/api](/C:/Users/User/Documents/jarvis_core/interface/api): camada HTTP, autenticacao por token e dispositivo confiavel, painel e relatorios.
- [tests](/C:/Users/User/Documents/jarvis_core/tests): regressao automatizada do comportamento atual.

## Ciclo do agente

O ciclo operacional relevante esta em [run_planner_cycle](/C:/Users/User/Documents/jarvis_core/executive_planner/planner.py) e segue esta ordem:

1. `plan`
2. `prioritize`
3. `validate`
4. `schedule`
5. `execute`
6. `review`

Cada etapa e auditada por [AuditLogger](/C:/Users/User/Documents/jarvis_core/executive_planner/audit.py) e refletida em estados localizados em pt-BR.

## Como navegar no codigo

Se a meta for entender o nucleo:

- comece por [runtime/internal_agent_runtime.py](/C:/Users/User/Documents/jarvis_core/runtime/internal_agent_runtime.py)
- depois leia [executive_planner/planner.py](/C:/Users/User/Documents/jarvis_core/executive_planner/planner.py)
- em seguida veja [executive_planner/queue.py](/C:/Users/User/Documents/jarvis_core/executive_planner/queue.py) e [executive_planner/validator.py](/C:/Users/User/Documents/jarvis_core/executive_planner/validator.py)

Se a meta for entender seguranca e limites:

- leia [constitutional_core/policy.py](/C:/Users/User/Documents/jarvis_core/constitutional_core/policy.py)
- depois [runtime/autonomy.py](/C:/Users/User/Documents/jarvis_core/runtime/autonomy.py)
- por fim [interface/api/app.py](/C:/Users/User/Documents/jarvis_core/interface/api/app.py)

Se a meta for entender persistencia e aprendizado:

- [memory_system/semantic_memory.py](/C:/Users/User/Documents/jarvis_core/memory_system/semantic_memory.py)
- [memory_system/procedural_memory.py](/C:/Users/User/Documents/jarvis_core/memory_system/procedural_memory.py)
- [intent_layer/goal_manager.py](/C:/Users/User/Documents/jarvis_core/intent_layer/goal_manager.py)

Se a meta for entender integracao externa:

- [runtime/server.py](/C:/Users/User/Documents/jarvis_core/runtime/server.py)
- [interface/api/app.py](/C:/Users/User/Documents/jarvis_core/interface/api/app.py)
- [interface/dashboard/index.html](/C:/Users/User/Documents/jarvis_core/interface/dashboard/index.html)

## Como iniciar o sistema

Loop continuo local:

```powershell
& 'C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe' C:\Users\User\Documents\jarvis_core\main.py
```

Servidor HTTP completo:

```powershell
& 'C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe' -m runtime.server
```

No Windows, o atalho de uso rapido pode ser disparado pelo Menu Iniciar digitando `J`.

## Arquivos criticos

- [main.py](/C:/Users/User/Documents/jarvis_core/main.py): loop continuo local
- [runtime/server.py](/C:/Users/User/Documents/jarvis_core/runtime/server.py): servidor HTTP e bootstrap de deploy
- [runtime/internal_agent_runtime.py](/C:/Users/User/Documents/jarvis_core/runtime/internal_agent_runtime.py): nucleo operacional
- [executive_planner/planner.py](/C:/Users/User/Documents/jarvis_core/executive_planner/planner.py): ciclo deterministico do planner
- [executive_planner/queue.py](/C:/Users/User/Documents/jarvis_core/executive_planner/queue.py): fila persistente
- [executive_planner/validator.py](/C:/Users/User/Documents/jarvis_core/executive_planner/validator.py): validacao estrutural e constitucional
- [constitutional_core/policy.py](/C:/Users/User/Documents/jarvis_core/constitutional_core/policy.py): politica viva
- [interface/api/app.py](/C:/Users/User/Documents/jarvis_core/interface/api/app.py): API e autenticacao

## Leitura recomendada para futuras IAs

1. Leia primeiro [JARVIS_CODE_GUIDE_PTBR.md](/C:/Users/User/Documents/jarvis_core/JARVIS_CODE_GUIDE_PTBR.md).
2. Depois leia [runtime/internal_agent_runtime.py](/C:/Users/User/Documents/jarvis_core/runtime/internal_agent_runtime.py).
3. Siga para [executive_planner/planner.py](/C:/Users/User/Documents/jarvis_core/executive_planner/planner.py) e [executive_planner/validator.py](/C:/Users/User/Documents/jarvis_core/executive_planner/validator.py).
4. Termine em [interface/api/app.py](/C:/Users/User/Documents/jarvis_core/interface/api/app.py) para entender a camada externa.
