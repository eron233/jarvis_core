# Deploy do JARVIS em VPS Simples

## Visao Geral

O modo de deploy atual sobe um unico servico chamado `jarvis_app`. Esse servico:

- carrega a configuracao por variaveis de ambiente
- recupera fila, memoria semantica e objetivos persistidos
- sobe a API HTTP
- serve o painel web em `/painel`
- inicia o loop continuo em background quando habilitado
- grava logs em arquivo
- persiste relatorios de ambiente e shutdown

## Pre-requisitos

- VPS Linux simples
- Docker instalado
- Docker Compose instalado
- porta da API liberada no firewall

## Variaveis de Ambiente

Arquivo base: `.env.example`

Variaveis principais:

- `JARVIS_ENV`
  Modo do ambiente. Use `production` em servidor.
- `JARVIS_TOKEN`
  Token secreto exigido pelos endpoints protegidos.
- `JARVIS_TRUSTED_DEVICE_ID`
  Identificador do dispositivo confiavel.
- `JARVIS_API_HOST`
  Host de bind da API. Em container, use `0.0.0.0`.
- `JARVIS_API_PORT`
  Porta HTTP exposta pela API.
- `JARVIS_LOOP_INTERVAL_SECONDS`
  Intervalo entre ciclos do runtime.
- `JARVIS_IDLE_SLEEP_SECONDS`
  Intervalo usado quando a fila estiver vazia.
- `JARVIS_LOG_LEVEL`
  Nivel de log do servico.
- `JARVIS_ENABLE_RUNTIME_LOOP`
  Liga ou desliga o loop continuo em background.
- `JARVIS_ENABLE_DASHBOARD`
  Liga ou desliga a entrega do painel web.
- `JARVIS_DATA_DIR`
  Diretorio base dos dados persistentes.
- `JARVIS_LOGS_DIR`
  Diretorio dos logs.
- `JARVIS_REPORTS_DIR`
  Diretorio dos relatorios operacionais do deploy.

Variaveis de caminho fino:

- `JARVIS_QUEUE_STORAGE_PATH`
- `JARVIS_SEMANTIC_STORAGE_PATH`
- `JARVIS_GOALS_STORAGE_PATH`

## Passo a Passo de Deploy

1. Copie o projeto para a VPS.
2. Entre no diretorio `jarvis_core`.
3. Gere o arquivo `.env` a partir de `.env.example`.
4. Defina `JARVIS_TOKEN` e `JARVIS_TRUSTED_DEVICE_ID` com valores reais.
5. Suba o servico:

```bash
docker compose up --build -d
```

6. Valide o healthcheck:

```bash
curl http://SEU_HOST:8000/health
```

7. Acesse o painel:

```text
http://SEU_HOST:8000/painel
```

## Persistencia

Por padrao, o `docker-compose.yml` monta:

- `./data:/app/data`
- `./logs:/app/logs`
- `./reports:/app/reports`

Arquivos principais:

- fila: `data/task_queue_store.json`
- memoria semantica: `data/semantic_memory_store.json`
- objetivos: `data/goals.json`
- logs: `logs/jarvis.log`
- relatorio de ambiente: `reports/environment_report.json`
- relatorio de encerramento: `reports/shutdown_report.json`

## Atualizacao sem Perda de Dados

1. Mantenha `data/`, `logs/` e `reports/`.
2. Atualize o codigo do projeto.
3. Refaça o build:

```bash
docker compose up --build -d
```

Como os volumes continuam montados, fila, memoria e objetivos sao preservados.

## Comandos Uteis

Subir:

```bash
docker compose up --build -d
```

Parar:

```bash
docker compose down
```

Ver logs:

```bash
docker compose logs -f jarvis_app
```

## Resolucao de Problemas

### API nao sobe

- confira `docker compose logs -f jarvis_app`
- valide `JARVIS_API_HOST` e `JARVIS_API_PORT`
- confirme que a porta esta liberada na VPS

### Token ausente ou invalido

- revise `JARVIS_TOKEN` no `.env`
- reinicie o servico apos alterar o arquivo

### Device id ausente ou invalido

- revise `JARVIS_TRUSTED_DEVICE_ID`
- confirme que o painel ou cliente esta enviando `X-Jarvis-Device-Id`

### Memoria nao carrega

- verifique `data/semantic_memory_store.json`
- confira o backup `.corrompido-*.json` se o arquivo anterior estiver invalido

### Fila corrompida

- verifique `data/task_queue_store.json`
- confira o backup `.corrompido-*.json`
- o bootstrap recria um arquivo limpo sem apagar o backup

### Painel nao abre

- confirme `JARVIS_ENABLE_DASHBOARD=true`
- valide `http://SEU_HOST:8000/painel`
- confira o healthcheck em `/health`

## Estrategia Atual de Startup

O entrypoint do container executa:

```bash
python -m runtime.server
```

Esse runner:

- valida a configuracao
- garante diretorios persistentes
- carrega fila, memoria e objetivos
- grava o resumo de ambiente
- sobe a API
- inicia o loop continuo em background, se habilitado
- persiste estado no shutdown

## Operacao Local Portavel

No ambiente Windows atual, a forma oficial de menor atrito e:

```powershell
.\jarvis.cmd check-config
.\jarvis.cmd server
```

Isso evita depender de `python` ou `uvicorn` no `PATH` e usa o mesmo `runtime/server.py` do deploy.
