# API do JARVIS

## Objetivo

Fornecer uma camada minima de acesso externo ao nucleo operacional do JARVIS sem duplicar runtime, planner, memoria, fila ou objetivos.

## Inicializacao local

```powershell
set JARVIS_API_TOKEN=seu_token_seguro
python -m uvicorn interface.api.app:app --host 0.0.0.0 --port 8000
```

Se a variavel `JARVIS_API_TOKEN` nao estiver definida, a API usa o token de desenvolvimento `jarvis-local-dev-token`.

## Autenticacao

- Header obrigatorio para endpoints protegidos: `X-Jarvis-Token`
- Healthcheck publico: `GET /api/saude`

## Endpoints atuais

- `GET /painel`
  Entrega o painel web mobile-first do JARVIS
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

## Observacoes

- Respostas visiveis foram mantidas em pt-BR.
- Identificadores internos estaveis continuam preservados dentro dos payloads para evitar quebra de integracao.
- A autenticacao atual e minima e baseada em token; podera ser expandida no bloco de autenticacao inicial.
- O painel web usa os mesmos endpoints e o mesmo token da API.
