# Sistema Cognitivo JARVIS

O JARVIS e um sistema cognitivo modular em construcao, orientado por planejamento deterministico, memoria persistente, objetivos, API de controle, painel mobile-first, auditoria e operacao supervisionada. Nesta etapa, o projeto ja consegue subir como servico HTTP, manter fila e memoria entre reinicios, proteger acesso por token + dispositivo confiavel e ser preparado para deploy em VPS simples com Docker.

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

## O que o sistema ja faz

- bootstrap do runtime com planner acoplado
- fila persistente em JSON
- memoria semantica persistente em JSON
- objetivos persistentes com progresso
- loop continuo com encerramento gracioso
- API protegida por token e dispositivo confiavel
- painel web para uso em celular
- relatorios operacionais completos
- healthcheck publico de deploy em `/health`
- configuracao central por variaveis de ambiente
- preparacao para container e `docker-compose`

## Execucao Local

Loop continuo controlado:

```powershell
python main.py --max-cycles 1 --stop-when-idle
```

Servidor HTTP completo:

```powershell
set JARVIS_ENV=development
set JARVIS_TOKEN=seu_token_seguro
set JARVIS_TRUSTED_DEVICE_ID=eron-celular-principal
python -m runtime.server
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

O arquivo base fica em `.env.example`.

## Persistencia

Por padrao, o modo de servidor usa:

- `data/task_queue_store.json`
- `data/semantic_memory_store.json`
- `data/goals.json`
- `logs/jarvis.log`
- `reports/environment_report.json`
- `reports/shutdown_report.json`

Esses caminhos podem ser trocados por variaveis de ambiente.

## Fluxo de Desenvolvimento

1. Implementar apenas o delta faltante do bloco atual.
2. Cobrir comportamento novo com testes em `tests/`.
3. Atualizar `ARCHITECTURE.md`, `system_capabilities_index.md` e os relatorios obrigatorios.
4. Registrar a mudanca em `CHANGELOG.md`.
5. Rodar `python -m unittest discover -s tests -v`.
6. Criar checkpoint git ao final de cada ciclo.

## Documentacao Relacionada

- `ARCHITECTURE.md`
- `API_PTBR.md`
- `DEPLOY_PTBR.md`
- `system_capabilities_index.md`
- `SYSTEM_MATURITY_REPORT_PTBR.md`
