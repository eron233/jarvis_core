# Ponto 7 — Model Context Protocol (MCP) Oficial

**Status:** implementação em `dev`  
**Objetivo:** substituir qualquer uso nominal/simulado de MCP por interoperabilidade real usando o SDK Python oficial, sem transformar integração em execução irrestrita.

## 1. Versão adotada

O JARVIS usa a linha **v2** do SDK Python oficial do Model Context Protocol.

No corte desta implementação:
- v2 é a linha estável;
- a release atual observada é 2.2.x;
- implementa a revisão MCP de 2026-07-28;
- negocia compatibilidade com revisões anteriores;
- suporta cliente e servidor;
- transportes principais: `stdio` e Streamable HTTP;
- SSE permanece apenas por compatibilidade histórica.

Dependência opcional:

```text
mcp>=2.2,<3
```

## 2. Arquitetura

```text
JARVIS
  |
  +--> OfficialMCPClientManager
  |       |
  |       +--> registry local
  |       +--> allowlist tools
  |       +--> allowlist resources
  |       +--> allowlist prompts
  |       |
  |       +--> MCP stdio
  |       +--> MCP Streamable HTTP
  |
  +--> JARVIS MCP Server
          |
          +--> runtime_status (read-only)
          +--> jarvis://capabilities (resource read-only)
```

## 3. Descoberta não é autorização

Conectar a um servidor MCP não concede automaticamente o direito de chamar tudo que ele anuncia.

O fluxo é:

```text
discover
   |
   +--> tools listadas
   +--> resources listados
   +--> prompts listados
          |
          v
registro/allowlist local
          |
          v
execução permitida ou bloqueada
```

Cada servidor possui listas independentes:

```json
{
  "allowed_tools": [],
  "allowed_resources": [],
  "allowed_prompts": []
}
```

Uma tool descoberta mas não permitida retorna `bloqueado` antes de abrir nova execução.

## 4. Registro MCP

Exemplo em:

```text
config/mcp_servers.example.json
```

Registro operacional padrão:

```text
data/mcp_servers.json
```

Exemplo HTTP local:

```json
{
  "enabled": true,
  "transport": "streamable-http",
  "url": "http://127.0.0.1:8000/mcp",
  "allowed_tools": ["search_code"],
  "allowed_resources": [],
  "allowed_prompts": []
}
```

## 5. stdio com menor privilégio

Servidor `stdio` é um processo real, portanto é uma superfície de execução.

O JARVIS aplica:
- sem `shell=True`;
- comando precisa estar na allowlist;
- argumentos precisam ser lista de strings;
- `cwd` permanece dentro do projeto;
- variáveis de ambiente não são copiadas em massa;
- somente nomes explicitamente presentes em `env_allowlist` são encaminhados.

Allowlist padrão de executáveis:

```text
python, python3, uv, uvx
```

Ela pode ser alterada por configuração, mas isso é decisão explícita.

## 6. Streamable HTTP local-first

Por padrão:

```env
JARVIS_MCP_ALLOW_REMOTE_HTTP=false
```

O cliente aceita normalmente:
- localhost;
- 127.0.0.1;
- ::1.

Endpoints remotos ficam bloqueados.

O SDK oficial v2 também restringe redirects HTTP a destinos compatíveis com a origem, reduzindo redirecionamentos inesperados.

## 7. JARVIS como servidor MCP

O próprio JARVIS agora pode ser publicado como servidor MCP oficial:

```powershell
python -m runtime.mcp_server
```

O padrão é `stdio`.

Para Streamable HTTP local:

```env
JARVIS_MCP_SERVER_TRANSPORT=streamable-http
JARVIS_MCP_SERVER_HOST=127.0.0.1
JARVIS_MCP_SERVER_PORT=8765
JARVIS_MCP_SERVER_PATH=/mcp
```

A exposição atual é deliberadamente read-only:
- tool `runtime_status`;
- resource `jarvis://capabilities`.

Operações mutantes não são expostas diretamente.

Elas continuam sob:
- autenticação do JARVIS;
- planner constitucional;
- políticas;
- auditoria;
- aprovação quando necessária.

## 8. Bind remoto protegido

O launcher recusa bind de rede externa por padrão.

Por exemplo:

```text
0.0.0.0
```

não é aceito silenciosamente.

A liberação exige:

```env
JARVIS_MCP_SERVER_ALLOW_REMOTE_BIND=true
```

Isso não significa que um deployment remoto esteja automaticamente pronto para produção. Autorização/OAuth, TLS e política de rede devem ser tratados antes de exposição real.

## 9. API interna do JARVIS

Status:

```text
GET /api/mcp/status
```

Descoberta:

```text
GET /api/mcp/{server}/discover
```

Tool:

```text
POST /api/mcp/{server}/tools/{tool}
```

Resource:

```text
GET /api/mcp/{server}/resource?uri=...
```

Prompt:

```text
POST /api/mcp/{server}/prompt/{prompt}
```

Todos os endpoints usam o gate de dispositivo confiável da API existente.

## 10. O antigo ScraplingMCP não é MCP oficial

`runtime/scrapling_mcp_engine.py` permanece apenas como compatibilidade histórica de endpoint web.

Ele já foi corrigido no ponto 5 para declarar:

```text
mcp_protocol_version = null
mcp_compatibility = legacy_envelope_not_official_mcp_server
```

O ponto 7 é a primeira implementação real do protocolo MCP dentro do core.

## 11. Features deliberadamente não habilitadas

Nesta fase o JARVIS não ativa automaticamente:
- OAuth remoto;
- sampling MCP;
- elicitation;
- roots;
- execução autônoma de tools descobertas;
- Tasks extension;
- servidores MCP remotos não confiáveis.

O SDK pode suportar parte dessas capacidades, mas suporte da biblioteca não equivale a política de autorização do JARVIS.

A Tasks extension continua com lacunas declaradas no roadmap do SDK oficial v2 e não é requisito desta fase.

## 12. Por que isso importa para os próximos pontos

Com MCP oficial, tecnologias como:
- codebase-memory-mcp;
- ferramentas de desenvolvimento;
- servidores de bancos;
- Git;
- browsers;
- sistemas locais;

podem entrar por um protocolo comum sem criar um adapter proprietário diferente para cada projeto.

Mas o protocolo não substitui a Constituição.

```text
MCP diz como chamar
Constituição decide se pode chamar
```

## 13. Fontes primárias

- https://github.com/modelcontextprotocol/python-sdk
- https://py.sdk.modelcontextprotocol.io/
- https://py.sdk.modelcontextprotocol.io/v2/client/
- https://py.sdk.modelcontextprotocol.io/v2/run/
- https://github.com/modelcontextprotocol/python-sdk/blob/main/ROADMAP.md

## 14. Estado de validação

A suíte automatizada cobre:
- MCP desligado por padrão;
- HTTP remoto bloqueado;
- descoberta sem execução;
- allowlist de tool;
- allowlists independentes de resource/prompt;
- comando stdio não permitido bloqueado antes do spawn;
- runtime inicializando sem SDK pesado obrigatório;
- ausência de MCP fabricado.
