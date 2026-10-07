# Ponto 5 — Web, Pesquisa e Navegação do JARVIS

**Status:** implementação em `dev`  
**Objetivo:** pesquisa web real, crawling limpo e navegação determinística sem fontes, confiança ou conteúdo fabricados.

## Arquitetura

```text
consulta do JARVIS
      |
      v
SearXNG self-hosted
      |
      +--> resultados reais + engines + snippets
      |
      v
roteador de recuperação
      |
      +--> Crawl4AI       -> Markdown/conteúdo limpo
      +--> Playwright     -> página JS/renderizada
      +--> HTTP stdlib    -> fallback leve para HTML/texto simples
      |
      v
evidência web auditável
```

## 1. Pesquisa: SearXNG

SearXNG é o motor de descoberta principal do ponto 5.

Motivos:
- open source e self-hosted;
- API HTTP simples;
- agrega múltiplos motores;
- permite JSON;
- filtros de idioma, categoria, safe search e intervalo temporal;
- o JARVIS não precisa depender diretamente de um único buscador.

O adapter usa o endpoint:

```text
GET /search?q=...&format=json
```

O SearXNG precisa estar configurado para permitir `format=json`.

Configuração:

```env
JARVIS_WEB_ADVANCED_ENABLED=true
JARVIS_SEARXNG_URL=http://127.0.0.1:8080
JARVIS_SEARXNG_LANGUAGE=pt-BR
JARVIS_SEARXNG_SAFESEARCH=1
```

Se SearXNG estiver indisponível, a busca retorna `indisponivel`.

O JARVIS não cria uma URL local, snippet ou resultado substituto.

## 2. Crawling: Crawl4AI 0.9.4

Crawl4AI é usado para páginas que precisam de extração mais robusta e conteúdo LLM-ready.

A versão fixada nesta fase é **0.9.4**, release de segurança de setembro de 2026.

Ela foi escolhida porque:
- gera Markdown;
- suporta páginas dinâmicas;
- permite extração JSON por CSS/XPath sem LLM;
- integra browser assíncrono;
- a 0.9.4 corrigiu caminhos SSRF e trust-boundary relevantes para servidores self-hosted.

Instalação:

```powershell
pip install -r requirements-web.txt
crawl4ai-setup
crawl4ai-doctor
```

Se o setup do browser falhar:

```powershell
python -m playwright install chromium
```

Configuração:

```env
JARVIS_CRAWL4AI_ENABLED=true
JARVIS_CRAWL4AI_BROWSER=chromium
JARVIS_CRAWL4AI_HEADLESS=true
```

## 3. Browser determinístico: Playwright

Playwright é a camada de navegação determinística.

Ele entra quando:
- o site depende de JavaScript;
- o DOM precisa ser renderizado;
- uma ação futura precisa de seletores/estado de página;
- queremos um caminho reproduzível antes de recorrer a um agente visual.

Nesta fase o adapter implementa **renderização/leitura**, não automação autônoma de formulários ou compras.

Isso mantém o ponto 5 seguro e determinístico.

## 4. Fallback HTTP real

Para páginas simples, não faz sentido iniciar Chromium.

O `SimpleHTTPExtractor`:
- usa apenas HTTP/HTTPS;
- limita bytes;
- aceita somente conteúdo textual;
- remove script/style/noscript/svg;
- extrai título e texto visível;
- não fabrica conteúdo quando falha.

## 5. Proteção SSRF

O stack bloqueia por padrão:
- localhost;
- loopback;
- IP privado;
- link-local;
- multicast;
- reservado;
- endereço não especificado;
- credenciais embutidas na URL.

O DNS é resolvido antes da busca e redirects passam novamente pelo gate.

```env
JARVIS_WEB_ALLOW_PRIVATE_TARGETS=false
```

Essa flag só deve ser alterada conscientemente para ambientes internos autorizados.

## 6. Módulos fictícios removidos/corrigidos

### `runtime/web_browser_engine.py`

Antes:
- DuckDuckGo HTML via regex;
- se a rede falhasse, retornava uma fonte `pesquisa.local` inventada.

Agora:
- SearXNG real;
- zero resultados quando indisponível;
- extração de páginas real e opcional.

### `learning/scrapegraph_engine.py`

Antes:
- podia retornar `100.0`, `Item extraído 1` ou `Valor adaptativo...` sem evidência.

Agora:
- exige schema JSON-CSS explícito;
- usa Crawl4AI;
- schema legado insuficiente retorna `indisponivel`;
- nenhum valor de placeholder é criado.

### `runtime/scrapling_mcp_engine.py`

Antes:
- afirmava "stealth";
- afirmava bypass anti-bot;
- gerava HTML artificial;
- declarava um protocolo MCP como se um servidor real existisse.

Agora:
- usa o fetch web real;
- `anti_bot_bypass=false`;
- `stealth_supported=false`;
- `mcp_protocol_version=null`;
- declara explicitamente que o envelope é legado e não é MCP oficial.

O MCP oficial continua sendo uma etapa tecnológica separada.

### `learning/agent_reach_engine.py`

Antes:
- criava resultados para quatro fontes;
- inventava confiabilidade `92.5%`;
- inventava consistência `94%`;
- declarava zero divergências.

Agora:
- consulta categorias reais via WebBrowserEngine/SearXNG;
- deduplica URLs;
- mede domínios e engines;
- nunca converte cobertura em verdade factual;
- consistência/confiança permanecem `null` sem uma análise de alegações real.

## 7. Por que Browser Use/Stagehand não estão no CORE deste ponto

Frameworks agentivos de browser são úteis quando a página é desconhecida e exige decisões abertas.

Mas eles:
- dependem de um modelo;
- gastam mais tokens/recursos;
- são menos determinísticos;
- ainda dependem do modelo-base que nós deliberadamente não escolhemos.

Portanto:
- Playwright = camada determinística principal;
- Browser Use/Stagehand = challengers `ON_DEMAND` futuros.

Quando o modelo-base for escolhido, o Experimental Twin poderá comparar taxa de sucesso, tempo, tokens e robustez.

## 8. Política de custo

```text
busca -> SearXNG
HTML simples -> HTTP leve
página rica -> Crawl4AI
JS específico -> Playwright
workflow desconhecido -> agente browser futuro
```

O JARVIS escolhe a ferramenta mais barata que cumpre a tarefa.

## 9. Dependências opcionais

```powershell
pip install -r requirements-web.txt
crawl4ai-setup
```

SearXNG é serviço separado/self-hosted e não entra no `requirements.txt` Python.

## 10. Fontes primárias

- https://docs.searxng.org/dev/search_api.html
- https://github.com/searxng/searxng
- https://github.com/unclecode/crawl4ai
- https://docs.crawl4ai.com/core/quickstart/
- https://docs.crawl4ai.com/extraction/no-llm-strategies/
- https://playwright.dev/python/docs/library
- https://github.com/browser-use/browser-use
- https://github.com/browserbase/stagehand

## 11. Estado de validação

A suíte automatizada valida:
- ausência de resultados falsos;
- parsing do contrato JSON SearXNG;
- bloqueio SSRF básico;
- roteamento de extração;
- ScrapeGraph sem placeholders;
- adapter legado sem alegação MCP/stealth;
- Agent Reach sem confiança fabricada.

SearXNG/Crawl4AI/Playwright continuam opcionais até serem provisionados no hardware alvo.
