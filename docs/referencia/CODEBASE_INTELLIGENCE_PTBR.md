# Ponto 8 — Inteligência Estrutural do Próprio Código

**Status:** implementação em `dev`  
**Objetivo:** permitir que o JARVIS conheça estruturalmente o próprio repositório — símbolos, chamadas, imports, rotas e impacto — sem depender de despejar arquivos inteiros no contexto ou inferir relações pelo nome.

## 1. Arquitetura

```text
JARVIS
  |
  +--> CodebaseIntelligenceEngine
          |
          +--> baseline local
          |     Python AST + SQLite
          |
          +--> backend preferido
                codebase-memory-mcp
                via MCP oficial
```

A camada local existe para garantir uma capacidade mínima real mesmo quando o binário externo não está instalado.

O backend externo existe para ampliar:
- linguagens;
- Tree-sitter;
- resolução híbrida/LSP;
- call graph;
- arquitetura;
- cobertura de índice;
- análise de impacto;
- rotas e serviços;
- consultas estruturais.

## 2. Backend preferido: codebase-memory-mcp

O candidato adotado é o projeto open source `DeusData/codebase-memory-mcp`, licença MIT.

A versão pinada para a prova do ponto 8 é:

```text
v0.11.0
publicada em 2026-09-15
```

O projeto declara:
- 162 linguagens via Tree-sitter;
- resolução híbrida/LSP em várias linguagens principais;
- grafo persistente;
- 17 tools MCP;
- busca estrutural/BM25/semântica;
- call graph;
- `detect_changes`;
- `get_architecture`;
- cobertura do índice;
- snippets e outlines.

Os números de desempenho publicados pelo projeto são **alegações do autor** até serem reproduzidos no JARVIS Experimental Twin.

O ponto 8 valida interoperabilidade e capacidade funcional; ele não adota automaticamente os números de marketing como nossos.

## 3. Prova de supply chain no CI

O workflow dedicado baixa um artefato exato:

```text
codebase-memory-mcp-linux-amd64.tar.gz
release v0.11.0
```

E verifica o SHA-256 publicado pelo release antes de executar:

```text
032b33c1833919a2d1de67ff6367fa6ea46aee8689c86ef223c88fae3b6e4536
```

Se o hash não coincidir, o job falha antes de iniciar o binário.

Isso não transforma uma dependência externa em confiável por decreto; apenas torna a reprodução determinística e impede troca silenciosa dos bytes no teste.

## 4. MCP com menor privilégio

O servidor externo entra através do MCP oficial implementado no ponto 7.

Exemplo:

```json
{
  "codebase-memory": {
    "enabled": false,
    "transport": "stdio",
    "command": "codebase-memory-mcp",
    "args": [],
    "cwd": ".",
    "env_allowlist": [],
    "allowed_tools": [
      "index_repository",
      "list_projects",
      "index_status",
      "check_index_coverage",
      "search_graph",
      "trace_path",
      "detect_changes",
      "get_graph_schema",
      "get_code_snippet",
      "get_file_outline",
      "get_architecture",
      "search_code"
    ],
    "allowed_resources": [],
    "allowed_prompts": []
  }
}
```

Ferramentas destrutivas ou desnecessárias não entram na allowlist padrão do exemplo.

Por exemplo:
- `delete_project`: não permitido;
- `manage_adr`: não permitido;
- `query_graph`: não permitido por padrão.

## 5. Indexação externa não é automática

Por padrão:

```env
JARVIS_CODEBASE_MCP_ENABLED=false
JARVIS_CODEBASE_MCP_AUTO_INDEX=false
```

Mesmo após cadastrar o servidor, o Jarvis não inicia indexação externa silenciosamente.

Quando o opt-in for dado, o adapter usa:

```text
persistence = false
```

Isso evita que o primeiro uso crie automaticamente um artefato `.codebase-memory/graph.db.zst` no repositório.

O próprio projeto alerta que commits frequentes desse snapshot binário podem inflar fortemente o histórico Git. Persistência compartilhada pode ser avaliada depois com uma política explícita.

## 6. Baseline local Python AST

`LocalPythonCodeGraph` é um baseline determinístico, leve e sem dependências externas.

Ele indexa:
- arquivos Python;
- classes;
- funções;
- async functions;
- chamadas;
- imports;
- rotas HTTP observadas em decorators;
- arquivo e linha da evidência.

Persistência:

```text
data/codebase_intelligence.sqlite3
```

O indexador ignora por padrão:
- `.git`;
- ambientes virtuais;
- `node_modules`;
- builds;
- caches;
- `data`;
- `logs`;
- `reports`.

Symlinks e arquivos acima do limite configurado também são ignorados.

## 7. Rastreamento

Exemplo:

```text
target()
   ^
   |
caller()
   ^
   |
second_caller()
```

O motor pode responder:
- quem chama `target`;
- o que `caller` chama;
- até profundidade configurável de 1 a 5.

Cada aresta contém:
- arquivo da evidência;
- linha;
- origem;
- destino;
- método de resolução.

O fallback resolve apenas casos que consegue provar de forma simples.

Chamadas ambíguas ou dinâmicas ficam marcadas como:

```text
unresolved_or_ambiguous
```

em vez de serem inventadas.

## 8. Impacto

O fallback local implementa blast radius estrutural inbound.

Ele retorna símbolos que dependem do alvo.

Mas:

```text
classificacao_risco = null
```

porque dependência estrutural não prova risco.

Risco exige testes, contexto, criticidade e evidência adicional.

O backend externo possui `detect_changes` e análise mais ampla; esses resultados também devem continuar sendo tratados como evidência estrutural, não como autorização automática para alterar código.

## 9. Snippets auditáveis

`snippet(symbol)` retorna somente as linhas associadas ao símbolo indexado, com:
- path;
- linha inicial;
- linha final.

Isso reduz a necessidade de carregar arquivos completos no contexto.

## 10. Graphify antigo

O `runtime/graphify_engine.py` antigo criava relações artificiais:
- ligava componentes em sequência;
- criava um ciclo de retroalimentação;
- atribuía scores arbitrários.

Essas relações não vinham de evidência.

No ponto 8 isso foi removido.

Graphify agora pode organizar componentes observados/informados, mas:

```text
arestas_inferidas_sem_evidencia = false
```

e não cria grafo genérico quando a entrada está vazia.

Para código-fonte real, a autoridade estrutural passa a ser `CodebaseIntelligenceEngine`.

## 11. API

```text
GET  /api/codebase/status
POST /api/codebase/indexar
GET  /api/codebase/arquitetura
GET  /api/codebase/buscar?q=...
GET  /api/codebase/rastrear?simbolo=...
GET  /api/codebase/impacto?simbolo=...
GET  /api/codebase/snippet?simbolo=...
```

Todos os endpoints usam autenticação de dispositivo confiável já existente.

## 12. Configuração

```env
JARVIS_CODEBASE_AST_ENABLED=true
JARVIS_CODEBASE_DB_PATH=data/codebase_intelligence.sqlite3

JARVIS_CODEBASE_MCP_ENABLED=false
JARVIS_CODEBASE_MCP_SERVER=codebase-memory
JARVIS_CODEBASE_MCP_PROJECT=jarvis_core
JARVIS_CODEBASE_MCP_AUTO_INDEX=false
```

Para ativar o binário externo via stdio, o executável também precisa ser explicitamente adicionado à allowlist MCP:

```env
JARVIS_MCP_ALLOWED_STDIO_COMMANDS=python,python3,uv,uvx,codebase-memory-mcp
```

## 13. Graft

Graft continua como candidato separado.

Ele resolve outro problema: **governança de leitura/contexto para agentes**, entregando vistas estruturais menores e recusando arquivos inadequados em vez de simplesmente construir um grafo persistente.

Portanto:

```text
codebase-memory-mcp = conhecimento estrutural persistente
Graft               = política/governança de leitura para coding agents
```

Não são substitutos diretos. Graft permanece na fila experimental para avaliação própria.

## 14. Fontes primárias

- https://github.com/DeusData/codebase-memory-mcp
- https://github.com/DeusData/codebase-memory-mcp/releases
- https://github.com/DeusData/codebase-memory-mcp/security
- https://github.com/flyingrobots/graft

## 15. Critério de validação

Para fechar o ponto 8 são exigidos:

1. suíte core verde;
2. baseline AST local:
   - index;
   - search;
   - trace;
   - impact;
   - snippet;
3. nenhuma aresta Graphify fabricada;
4. release externo pinado por hash;
5. servidor `codebase-memory-mcp` real iniciado;
6. MCP discovery real;
7. `index_repository` real;
8. `search_graph` real;
9. `trace_path` real;
10. `get_architecture` real.

Só depois disso o backend externo pode ser registrado como funcionalmente validado. Seus benchmarks publicados continuam sendo evidência do autor até reprodução específica no Twin.
