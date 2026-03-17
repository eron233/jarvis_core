# API do JARVIS

## Objetivo

Fornecer acesso HTTP ao nucleo operacional do JARVIS sem duplicar planner, runtime, memoria, fila, objetivos ou relatorios.

## Inicializacao Recomendada

Servidor HTTP/API oficial:

```powershell
set JARVIS_ENV=development
set JARVIS_TOKEN=seu_token_seguro
set JARVIS_TRUSTED_DEVICE_ID=eron-celular-principal
python runtime\server.py
```

Launcher tecnico oficial no Windows atual:

```powershell
.\jarvis.cmd server
```

Validacao de configuracao antes da subida:

```powershell
.\jarvis.cmd check-config
```

Observacao operacional:

- `runtime/server.py` e o unico entrypoint oficial do servidor HTTP/API
- `.\jarvis.cmd server` e o wrapper tecnico oficial desse mesmo entrypoint no Windows atual
- o modo `api-direct` do launcher sobrevive apenas como shim legado e redireciona para `server`
- nao use `python -m uvicorn ...` nem `--reload` como caminho operacional oficial do projeto

## Autenticacao

Contrato atual:

- header `X-Jarvis-Token`
- header `X-Jarvis-Device-Id`
- sessao de painel criada via `POST /api/auth/device-session`

Endpoints protegidos exigem token valido e `device id` do dispositivo confiavel. O healthcheck publico de deploy em `/health` nao exige autenticacao.

Camada adicional de comando:

- voz reconhecida `eron` continua apenas como contexto especial para a frase reservada
- a senha administrativa precisa vir do ambiente ou do bootstrap seguro gerado em `data/jarvis_access_bootstrap.json`
- sem essas credenciais, o comando opera em modo guest
- a frase `Jarvis ta ai` responde `Sim, Sr. Maciel.` apenas com a voz `eron`

## Endpoints Principais

- `GET /health`
  Healthcheck publico de deploy com resumo de ambiente
- `GET /api/saude`
  Saude basica da API
- `GET /painel`
  Painel web do JARVIS ou tela de validacao do dispositivo
- `POST /api/auth/device-session`
  Valida token + dispositivo e cria sessao do painel
- `DELETE /api/auth/device-session`
  Remove a sessao atual do painel
- `GET /api/status`
  Estado atual do sistema
- `POST /api/ciclos/executar`
  Executa um ciclo do planner
- `POST /api/comando`
  Processa comando textual, wake phrase, guest/admin e autodiagnostico seguro
- `GET /api/tarefas`
  Lista a fila atual
- `POST /api/tarefas`
  Adiciona tarefa a fila
- `GET /api/objetivos`
  Consulta objetivos
- `GET /api/memoria/recente`
  Consulta memoria recente
- `GET /api/cognicao/evolucao`
  Payload visual do mapa evolutivo cognitivo
- `GET /api/cognicao/evolucao/analise`
  Analise interna das regioes e trilhas cognitivas
- `GET /api/runtime/identidade`
  Identidade do runtime em execucao com commit, boot, entrypoint, PID e configuracao relevante
- `GET /api/relatorio`
  Relatorio operacional geral
- `GET /api/health`
  Healthcheck rico protegido
- `GET /api/relatorio/sistema`
  Relatorio geral do sistema
- `GET /api/relatorio/fila`
  Relatorio detalhado da fila
- `GET /api/relatorio/objetivos`
  Relatorio detalhado dos objetivos
- `GET /api/relatorio/memoria`
  Relatorio da memoria semantica
- `GET /api/relatorio/auditoria`
  Relatorio de auditoria

## Configuracao de Ambiente

Principais variaveis:

- `JARVIS_ENV`
- `JARVIS_TOKEN`
- `JARVIS_TRUSTED_DEVICE_ID`
- `JARVIS_API_HOST`
- `JARVIS_API_PORT`
- `JARVIS_ENABLE_RUNTIME_LOOP`
- `JARVIS_ENABLE_DASHBOARD`
- `JARVIS_DATA_DIR`
- `JARVIS_LOGS_DIR`
- `JARVIS_REPORTS_DIR`
- `JARVIS_PROCEDURAL_STORAGE_PATH`
- `JARVIS_DEVICE_REGISTRY_PATH`
- `JARVIS_COGNITIVE_EVOLUTION_STORAGE_PATH`
- `JARVIS_ADMIN_VOICE`
- `JARVIS_ADMIN_PASSWORD`

Arquivo base: `.env.example`

Se os segredos nao forem fornecidos explicitamente, a API passa a usar o bootstrap seguro persistido em `data/jarvis_access_bootstrap.json` e registra a orientacao inicial em `reports/JARVIS_ADMIN_BOOTSTRAP_CREDENTIAL_PTBR.txt`.

## Observacoes Operacionais

- respostas visiveis continuam em pt-BR
- endpoints protegidos continuam protegidos no modo de servidor
- chamadas mutantes protegidas agora exigem tambem `X-Jarvis-Nonce` e `X-Jarvis-Timestamp`
- o painel e servido pela mesma API
- o deploy recomendado usa `python runtime/server.py`, `.\jarvis.cmd server` ou `docker compose up -d`
- `runtime/server.py --check-config` pode ser usado para validar o ambiente antes do start efetivo
- os relatorios operacionais agora incluem um resumo seguro da politica constitucional ativa
- o painel consome os endpoints cognitivos e carrega os modulos do brain avatar por `/brain-avatar/*`

## Limites Atuais da Autenticacao HTTP

- a mitigacao anti-replay atual reduz reaproveitamento trivial de requisicoes, mas ainda nao substitui assinatura criptografica
- a protecao de `nonce` e local ao processo e nao e compartilhada entre multiplas instancias
- o campo de voz nao deve ser tratado como autenticacao forte; ele e apenas informativo para fluxos textuais controlados
