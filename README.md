# Sistema Cognitivo JARVIS

O JARVIS e um sistema cognitivo modular em construcao, orientado por planejamento deterministico, memoria persistente, objetivos, API de controle, painel mobile-first, auditoria, operacao supervisionada e autodefesa interna. Nesta etapa, o projeto ja consegue subir como servico HTTP, manter fila e memoria entre reinicios, proteger acesso por token + dispositivo confiavel, ser preparado para deploy em VPS simples com Docker e manter um nucleo defensivo de conhecimento para diagnostico de risco do proprio sistema.

Idioma padrao da camada visivel: `pt-BR`

## Visao Geral da Arquitetura

- `constitutional_core/`: identidade e principios do sistema
- `executive_planner/`: fila, priorizacao, validacao, auditoria e ciclo do planner
- `intent_layer/`: metas estrategicas e objetivos ativos
- `memory_system/`: memoria episodica, semantica e procedural
- `workers/`: workers por dominio
- `runtime/`: bootstrap do runtime, autonomia, configuracao e servidor
- `interface/api/`: API FastAPI integrada ao nucleo
- `interface/dashboard/`: painel web mobile-first servido pela API
- `data/`, `logs/`, `reports/`: paths padrao de persistencia e observabilidade
- `tests/`: suite automatizada de regressao

## Entrypoints

- Runtime interno: `runtime/internal_agent_runtime.py`
- Loop continuo local: `main.py`
- Servidor para VPS/API/painel: `runtime/server.py`
- Launcher oficial no Windows atual: `jarvis.cmd`

## O que o sistema ja faz

- bootstrap do runtime com planner acoplado
- constitutional core carregado como politica viva de validator e runtime
- fila persistente em JSON
- memoria semantica persistente em JSON
- memoria procedural persistente com heuristicas reutilizaveis
- objetivos persistentes com progresso
- loop continuo com encerramento gracioso
- API protegida por token e dispositivo confiavel
- painel web para uso em celular
- relatorios operacionais completos
- healthcheck publico de deploy em `/health`
- configuracao central por variaveis de ambiente
- preparacao para container e `docker-compose`
- nucleo de conhecimento defensivo para autodefesa interna
- motor de modelagem de ameaca sobre o proprio estado do sistema
- gemeo de seguranca isolado com snapshots sanitizados
- validacao interna controlada apenas sobre o gemeo autorizado
- remediacao hibrida com autoaplicacao limitada a correcoes seguras

## Politica Constitucional Viva

O constitutional core agora deixa de ser apenas configuracional e passa a governar o sistema por meio de `constitutional_core/policy.py`.

Capacidades atuais:

- carregar identidade e principios como politica ativa
- marcar tarefas proibidas por politica constitucional
- exigir aprovacao humana para escopos sensiveis
- orientar o gate de autonomia do runtime
- expor um resumo seguro da politica ativa nos relatorios operacionais

## Memoria Procedural

O JARVIS agora registra padroes de execucao reutilizaveis em `memory_system/procedural_memory.py`.

Capacidades atuais:

- armazenar procedimentos estruturados por dominio e tipo de tarefa
- persistir heuristicas em JSON configuravel
- buscar procedimentos por texto, dominio, tipo e sucesso
- registrar padroes apos execucao real do runtime
- reaproveitar guidance procedural em tarefas semelhantes

## Execucao Local

Loop continuo controlado:

```powershell
python main.py --max-cycles 1 --stop-when-idle
```

No Windows atual, se `python` nao estiver no `PATH`, use o launcher oficial:

```powershell
.\jarvis.cmd loop --max-cycles 1 --stop-when-idle
```

Servidor HTTP completo:

```powershell
set JARVIS_ENV=development
set JARVIS_TOKEN=seu_token_seguro
set JARVIS_TRUSTED_DEVICE_ID=eron-celular-principal
python -m runtime.server
```

Opcao equivalente, mais robusta no ambiente local atual:

```powershell
.\jarvis.cmd server
```

Validacao rapida da configuracao sem subir a API:

```powershell
.\jarvis.cmd check-config
```

## Execucao com Docker

Build:

```powershell
docker build -t jarvis-core .
```

Subida com compose:

```powershell
copy .env.example .env
docker compose up --build -d
```

Healthcheck:

```powershell
curl http://localhost:8000/health
```

Painel:

```text
http://localhost:8000/painel
```

## Variaveis de Ambiente Principais

- `JARVIS_TOKEN`
- `JARVIS_TRUSTED_DEVICE_ID`
- `JARVIS_API_HOST`
- `JARVIS_API_PORT`
- `JARVIS_LOOP_INTERVAL_SECONDS`
- `JARVIS_ENV`
- `JARVIS_DATA_DIR`
- `JARVIS_LOG_LEVEL`
- `JARVIS_ENABLE_RUNTIME_LOOP`
- `JARVIS_ENABLE_DASHBOARD`
- `JARVIS_PROCEDURAL_STORAGE_PATH`

O arquivo base fica em `.env.example`.

## Persistencia

Por padrao, o modo de servidor usa:

- `data/task_queue_store.json`
- `data/semantic_memory_store.json`
- `data/procedural_memory_store.json`
- `data/goals.json`
- `logs/jarvis.log`
- `reports/environment_report.json`
- `reports/shutdown_report.json`

Esses caminhos podem ser trocados por variaveis de ambiente.

## Autodefesa Interna

O projeto agora inclui `security/security_knowledge_core.py`, que organiza conhecimento defensivo sobre:

- identidade e acesso
- aplicacao
- infraestrutura
- continuidade
- observabilidade

Essa base foi feita para apoiar diagnostico, modelagem de risco e propostas futuras de endurecimento sem executar qualquer acao externa nao autorizada.

O modulo `security/threat_model_engine.py` complementa essa base transformando o estado atual do JARVIS em:

- inventario de ativos protegidos
- mapa de superficies de contato
- classificacao de risco em baixo, medio, alto e critico
- dependencias criticas do sistema

O modulo `security/security_twin.py` amplia a autodefesa criando um espelho isolado do estado atual do JARVIS com:

- snapshot sanitizado de configuracao, fila, memoria e objetivos
- resumo operacional seguro do runtime
- metadados de API e seguranca sem expor segredos
- persistencia isolada em `security/twin_state/`
- validacao de integridade do espelho antes de qualquer simulacao defensiva

O modulo `security/security_validation_engine.py` executa cenarios defensivos controlados somente sobre esse espelho para verificar:

- autenticacao e identidade
- configuracao e startup
- persistencia
- observabilidade
- continuidade
- integridade operacional

O modulo `security/remediation_engine.py` transforma fraquezas detectadas em:

- solucao imediata
- solucao estrutural
- mitigacao operacional

Quando o risco e baixo e a correcao e reversivel, o proprio sistema pode aplicar automaticamente apenas a parte segura, mantendo auditoria e sem tocar em autenticacao estrutural ou no constitutional core.

## Fluxo de Desenvolvimento

1. Implementar apenas o delta faltante do bloco atual.
2. Cobrir comportamento novo com testes em `tests/`.
3. Atualizar `ARCHITECTURE.md`, `system_capabilities_index.md` e os relatorios obrigatorios.
4. Registrar a mudanca em `CHANGELOG.md`.
5. Rodar `python -m unittest discover -s tests -v`.
6. Criar checkpoint git ao final de cada ciclo.

## Notas de Portabilidade

- `main.py` e `runtime/server.py` agora se bootstrapam de forma explicita para localizar a raiz do projeto em ambientes Python isolados
- o modo servidor nao depende do executavel `uvicorn` no `PATH`
- a API pode continuar sendo iniciada por `python -m runtime.server`, `python runtime/server.py` ou `.\jarvis.cmd server`
- `runtime/server.py --check-config` valida ambiente e paths sem prender o terminal com o servidor

## Documentacao Relacionada

- `ARCHITECTURE.md`
- `API_PTBR.md`
- `DEPLOY_PTBR.md`
- `system_capabilities_index.md`
- `SYSTEM_MATURITY_REPORT_PTBR.md`
