# API do JARVIS

## Objetivo

Fornecer uma camada minima de acesso externo ao nucleo operacional do JARVIS sem duplicar runtime, planner, memoria, fila ou objetivos.

## Inicializacao local

```powershell
set JARVIS_TOKEN=seu_token_seguro
set JARVIS_TRUSTED_DEVICE_ID=eron-celular-principal
python -m uvicorn interface.api.app:app --host 0.0.0.0 --port 8000
```

Se `JARVIS_TOKEN` ou `JARVIS_TRUSTED_DEVICE_ID` nao estiverem definidos, a API usa valores locais de desenvolvimento.

## Autenticacao

- Headers obrigatorios para endpoints protegidos:
  - `X-Jarvis-Token`
  - `X-Jarvis-Device-Id`
- Painel protegido por sessao de dispositivo confiavel, criada via `POST /api/auth/device-session`
- Healthcheck publico: `GET /api/saude`

## Endpoints atuais

- `GET /painel`
  Entrega o painel web do JARVIS ou a tela de validacao do dispositivo
- `POST /api/auth/device-session`
  Valida token + device id e cria a sessao do painel
- `DELETE /api/auth/device-session`
  Remove a sessao atual do painel
- `GET /api/saude`
  Retorna saude basica da API e do runtime
- `GET /api/status`
  Retorna o estado atual do sistema
- `POST /api/ciclos/executar`
  Executa um ciclo unico do planner
- `GET /api/tarefas`
  Lista as tarefas atuais da fila
- `POST /api/tarefas`
  Adiciona uma tarefa a fila
- `GET /api/objetivos`
  Retorna relatorio de objetivos
- `GET /api/memoria/recente`
  Retorna memoria semantica recente e eventos episodicos
- `GET /api/relatorio`
  Retorna um resumo operacional do sistema
- `GET /api/health`
  Retorna o healthcheck rico do sistema, protegido por token e dispositivo
- `GET /api/relatorio/sistema`
  Retorna o relatorio geral do sistema
- `GET /api/relatorio/fila`
  Retorna o relatorio detalhado da fila
- `GET /api/relatorio/objetivos`
  Retorna o relatorio operacional de metas e objetivos
- `GET /api/relatorio/memoria`
  Retorna o relatorio operacional da memoria semantica
- `GET /api/relatorio/auditoria`
  Retorna o relatorio consolidado de auditoria

## Observacoes

- Respostas visiveis foram mantidas em pt-BR.
- Identificadores internos estaveis continuam preservados dentro dos payloads para evitar quebra de integracao.
- A autenticacao atual combina token secreto e identificador do dispositivo confiavel.
- Toda tentativa negada gera registro de auditoria de acesso no runtime.
- O painel web usa o mesmo token da API e uma sessao curta derivada do dispositivo confiavel.
- O painel agora consome os endpoints de relatorio para mostrar saude, fila, objetivos, memoria e auditoria em formato operacional.
