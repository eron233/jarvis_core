# Ponto 9 — Governança de Contexto para Agentes de Desenvolvimento

**Status:** baseline nativo validado em `dev`; backend externo Graft em quarentena  
**Data da avaliação:** 2026-10-07

## 1. Problema que este ponto resolve

O ponto 8 deu ao JARVIS conhecimento estrutural do próprio código.

O ponto 9 resolve um problema diferente:

> quanto código um agente deve poder ler, em qual formato e com qual evidência de consumo?

Um coding agent não deve despejar o repositório inteiro no contexto só porque consegue.

A política correta é:

```text
pedido de leitura
      |
      v
governor
      |
      +--> secret/binário/lockfile/build -> recusa
      +--> arquivo pequeno              -> conteúdo
      +--> arquivo grande               -> outline
      +--> trecho conhecido             -> range limitado
      |
      v
recibo auditável
```

## 2. Implementação validada: governor nativo do JARVIS

Arquivo:

```text
learning/development_context_engine.py
```

A implementação local é determinística e não depende de modelo.

### Política de leitura

Defaults adotados:

```text
arquivo inteiro:
  até 150 linhas
  e até 12 KiB

cap por profundidade de sessão:
  early: 20 KiB
  mid:   10 KiB
  late:   4 KiB

read_range:
  máximo 250 linhas
```

Quando um `budget_remaining` é informado, uma leitura individual não pode
consumir mais de 5% do restante.

## 3. Recusas

O baseline local recusa:
- `.env` e variantes secretas;
- PEM/key/P12/PFX;
- `credentials.*`;
- binários;
- lockfiles;
- arquivos minificados;
- build output;
- paths fora do projeto;
- symlinks;
- patterns em `.graftignore`.

Uma recusa nunca devolve o conteúdo recusado.

## 4. Outlines

Arquivos grandes não são retornados integralmente.

Python:
- classes;
- funções;
- async functions;
- linha inicial/final.

Markdown:
- headings.

Formato sem parser local:
- outline vazio;
- nenhuma estrutura é inventada.

## 5. Ranges

`read_range` permite leitura focada por linhas.

A política de segredo/binário continua valendo.

Não existe bypass do governor por usar range.

## 6. Recibos e sessão

Toda leitura local relevante registra:
- bytes retornados;
- bytes evitados;
- decisão;
- contagem de leituras do path;
- consumo cumulativo.

Tripwires atuais:

```text
REPEATED_PATH_READ  -> mesmo path lido 4 vezes
RUNAWAY_READ_LOOP   -> 30 chamadas na sessão
```

O recibo não afirma "tokens economizados" sem tokenizer/modelo concreto.
Ele mede bytes, que são observáveis.

## 7. API interna

```text
GET /api/dev-context/status
GET /api/dev-context/read
GET /api/dev-context/outline
GET /api/dev-context/range
GET /api/dev-context/session/{session_id}
```

Todos usam o gate de dispositivo confiável existente.

## 8. Avaliação do flyingrobots/graft

Projeto avaliado:

```text
flyingrobots/graft
release v0.14.0
Apache-2.0
```

Papel:
- context governor;
- safe reads;
- outlines;
- read ranges;
- receipts;
- governança de sessão;
- histórico estrutural/WARP.

Tarball oficial usado no teste:

```text
flyingrobots-graft-0.14.0.tgz
SHA-256:
0322579bb8e9d3e26840eabdeec2fcb7a3c795f1424c3514e49eacefcbb1ef02
```

## 9. Reproduzindo a release de verdade

O `package.json` da v0.14.0 usa ranges semver.

O `pnpm-lock.yaml` da própria tag registra:

```text
@git-stunts/plumbing          2.8.0
@git-stunts/git-warp          16.0.0
@modelcontextprotocol/sdk     1.29.0
```

A prova externa fixou também essas versões para evitar drift transitivo.

Portanto o teste não foi apenas "npm install latest".

## 10. Resultado factual da prova externa

A integração MCP foi preparada corretamente e o servidor anunciou as tools.

Durante o trabalho também corrigimos o cliente MCP do JARVIS para respeitar
as capabilities negociadas, porque o Graft anuncia tools mas não resources
ou prompts.

Depois disso, a chamada real ainda falhou.

Para separar MCP de runtime, foi executado diretamente:

```text
graft --cwd <repo_git_minimo> read safe small.py --json
```

sobre um repositório temporário:
- `git init`;
- commit real;
- `git rev-parse HEAD` confirmado pelo teste;
- dependências transitivas pinadas conforme o lockfile da release.

Resultado observado:

```text
Error: Git command failed with code 128
```

Git do runner:

```text
git version 2.55.0
```

Logo:

**a falha não é do adapter MCP do JARVIS. O CLI oficial da release falha no
ambiente reproduzido antes mesmo da camada MCP.**

## 11. Decisão constitucional

`flyingrobots/graft v0.14.0` NÃO é promovido para backend validado.

Estado:

```text
QUARANTINED / WATCHLIST
```

O adapter continua no código porque:
- a arquitetura é útil;
- a integração MCP está pronta;
- uma versão futura pode corrigir a incompatibilidade.

Mas fica:

```env
JARVIS_GRAFT_CONTEXT_ENABLED=false
```

por padrão.

Nenhum `graft init`, hook ou daemon é executado automaticamente.

## 12. Least privilege do adapter externo

Mesmo se uma futura release passar nos testes, a allowlist padrão continua
read-only:

```text
safe_read
file_outline
read_range
changed_since
```

Não entram por padrão:
- `graft_edit`;
- run capture;
- daemon control;
- hooks;
- qualquer mutação do repositório.

## 13. Dois projetos chamados Graft

Também foi avaliado o projeto TrailHQ/Nanonets Graft.

Ele resolve principalmente:
- codebase graph;
- contexto estrutural;
- busca/callers;
- enriquecimento de contexto para coding agents.

Isso sobrepõe fortemente o ponto 8 (`codebase-memory-mcp` + AST local).

Suas alegações públicas de redução de custo/tempo/tokens permanecem
**alegações do autor** até benchmark no Experimental Twin.

Portanto:

```text
flyingrobots/graft -> governor de leitura/contexto
TrailHQ Graft      -> challenger de code-context/graph
```

O segundo não substitui automaticamente o backend estrutural já validado.

## 14. Arquivos principais

```text
learning/development_context_engine.py
tests/test_development_context.py
tests/test_graft_context_external.py
config/mcp_servers.example.json
.env.example
interface/api/app.py
runtime/internal_agent_runtime.py
```

## 15. Critério para retirar o Graft externo da quarentena

Uma nova release só pode entrar se passar:

1. hash/artefato pinado;
2. dependências transitivas reproduzíveis;
3. CLI direto em repo Git mínimo;
4. MCP discovery;
5. `safe_read` pequeno;
6. outline grande;
7. `file_outline`;
8. `read_range`;
9. recusa real de secret;
10. suíte completa do JARVIS;
11. ausência de regressão de segurança relevante.

## 16. Fontes primárias

- https://github.com/flyingrobots/graft
- https://github.com/flyingrobots/graft/releases
- https://github.com/trailhq/Graft
- https://github.com/modelcontextprotocol/python-sdk
