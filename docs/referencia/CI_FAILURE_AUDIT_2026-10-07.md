# Auditoria de falhas do GitHub Actions — 2026-10-07

Status: inventário incremental. Este arquivo existe para evitar que falhas antigas e
pendências reais sejam misturadas numa única sessão de correção.

## Regra de trabalho

- corrigir uma família de erro por vez;
- confirmar no GitHub Actions;
- registrar o restante sem expandir o escopo automaticamente;
- falhas de commits intermediários não são tratadas como bugs atuais quando o mesmo
  workflow já passa no estado atual;
- integrações externas em quarentena não devem bloquear o core silenciosamente.

## 1. Suite de testes — ponto 10

Estado: **RESOLVIDO**.

Falhas observadas:
- ausência da chave legada `total_hits_acumulados`;
- teste legado ainda exigia `estimativa_tokens_economizados`, apesar de essa métrica
  não ser observada de verdade.

Correção:
- `total_hits_acumulados` preservado como soma observada de hits exatos + vetoriais;
- teste legado atualizado para não exigir economia fictícia de tokens.

Evidência atual:
- Suite de testes em `dev`: verde;
- MCP oficial em `dev`: verde;
- Suite de testes em `validado`: verde;
- MCP oficial em `validado`: verde.

## 2. Graft context real

Estado: **QUARENTENA / NÃO BLOQUEADOR DO CORE**.

Falha reproduzida:
```text
Error: Git command failed with code 128
```

Contexto:
- flyingrobots/graft v0.14.0;
- dependências pinadas conforme release/lock;
- repositório Git mínimo válido criado no runner;
- `git rev-parse HEAD` passou;
- o CLI do próprio Graft falhou antes da integração MCP;
- runner observado com Git 2.55.0.

Situação atual:
- o workflow dedicado `Graft context real` não existe mais nas branches atuais
  `dev` e `validado`;
- o adapter continua desativado por padrão;
- a falha permanece como evidência histórica para reavaliar uma release futura.

Pendência associada:
- o install isolado do Graft reportou 1 vulnerabilidade npm de severidade alta.
  Não promover/reabilitar o backend sem nova auditoria da cadeia de dependências.

## 3. Falhas antigas de Suite de testes em commits intermediários

Estado: **HISTÓRICAS / SUPERADAS**.

Foram observadas falhas durante trabalhos de:
- voz;
- web;
- inferência;
- inteligência de código;
- cache semântico.

Elas permanecem nos e-mails e no histórico do Actions, mas não são, por si só,
evidência de falha atual. O estado atual deve ser decidido pelos runs mais recentes
das branches ativas.

## 4. Runtime Node 20 das GitHub Actions

Estado: **CORREÇÃO EM ANDAMENTO NESTE LOTE**.

Aviso observado no runner:
- `actions/checkout@v4` e `actions/setup-python@v5` usam runtime Node 20
  descontinuado e estavam sendo forçados pelo runner a Node 24.

Correção aplicada em `dev`:
- `actions/checkout@v7`;
- `actions/setup-python@v7`.

Arquivos:
- `.github/workflows/tests.yml`;
- `.github/workflows/mcp-tests.yml`;
- `.github/workflows/codebase-memory-tests.yml`.

Critério de fechamento:
- workflows relevantes verdes em PR para `validado`;
- depois merge e confirmação do push em `validado`.

## 5. Warnings ainda não corrigidos

Estado: **PARCIALMENTE RESOLVIDO**.

A suíte atualmente verde reportou:
- depreciação de `httpx` via `starlette.testclient`;
- warning do Pydantic: campo `schema` sombreando atributo de `BaseModel`.

### Pydantic `schema`

Estado: **CORRIGIDO NESTE LOTE**.

Causa:
- o parâmetro Python `schema` do endpoint `/api/web/scrapegraph/extrair`
  fazia o FastAPI gerar um modelo Pydantic com campo interno chamado `schema`,
  colidindo com atributo de `BaseModel`.

Correção:
- o nome interno agora é `extraction_schema`;
- o contrato HTTP continua aceitando a chave JSON pública `schema` por alias;
- foi adicionado teste de regressão do endpoint.

### Starlette/httpx

Estado: **ANOTADO / NÃO INICIADO**.

A depreciação do `TestClient` será tratada em lote separado.

## 6. Inconsistência separada: defaults antigos de modelo

Estado: **ANOTADO / NÃO É FALHA DE CI DESTE LOTE**.

Existe código antigo de memória avançada com nomes de Qwen3 como defaults.
Isso conflita com a decisão atual de não selecionar modelo por padrão.
Não foi corrigido neste lote para não misturar CI com política de modelos.
