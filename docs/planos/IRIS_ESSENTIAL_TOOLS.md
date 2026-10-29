# Integração das ferramentas essenciais da Íris

Objetivo: permitir que a inferência local consulte ferramentas existentes e use
os resultados na resposta, sem depender de uma assinatura do ChatGPT.

Escopo deste incremento:

1. Catálogo com esquemas e validação estrita para documentos, código, impacto,
   estado das integrações e pesquisa/leitura web.
2. Ciclo limitado de chamadas de ferramentas, usando apenas llama.cpp/Ollama
   em loopback. Nenhum shell, instalação, edição de arquivo ou execução MCP
   arbitrária pelo modelo. Rede precisa ser selecionada por execução.
3. Bootstrap e API autenticada; quando há autoridade de instâncias, acesso
   exclusivo da Original. Memória privada das residentes permanece isolada.
4. Testes com base documental e grafo reais, transporte HTTP local simulado,
   autenticação, limites e falhas. Executar também a suíte completa.

Decisão: reaproveitar memória, ingestão, grafo, SearXNG e MCP já presentes.
Não adicionar um segundo orquestrador ou outro armazenamento de memória agora.
Hindsight, PageIndex, ferramentas de vídeo/design e novos servidores MCP ficam
para adaptações específicas quando houver necessidade e backend provisionado.

Baseline nesta sessão: 534 testes passaram, 43 foram pulados; quatro falhas
anteriores à alteração dependem de DNS público e do socket Docker deste host
(WebFetchSchemeTests, dois ContainerExecutorTests e WebBrowserEngineTests).

## Resultado da implementação — 2026-10-29

- 38 testes novos passaram, incluindo ciclo HTTP local, documentos/grafo reais,
  autenticação, repetição de pedido, isolamento da Original, proxy, redirecionamento,
  DNS rebinding e fallback IPv6/IPv4 de `localhost`.
- Suíte completa em execução serial: 572 passaram, 43 pulados e 115 subtestes
  passaram. Permaneceram as mesmas quatro falhas da baseline:
  `WebFetchSchemeTests::test_aceita_endereco_http_comum`,
  `ContainerExecutorTests::test_comando_isolado_e_resultado_nao_comprova_conclusao`,
  `ContainerExecutorTests::test_ferramenta_falha_sem_sucesso_inventado` e
  `WebBrowserEngineTests::test_search_uses_real_sources_and_extracts_only_budgeted_pages`.
- Revisão separada aprovada após corrigir transporte de rede e limites dos
  resultados. Nenhum dado privado ou histórico de conversa é incluído no patch.
- Ambiente desta execução: Linux/Python 3.12; Python 3.11, Windows físico e modelo
  local real não estavam disponíveis para homologação. Não houve deploy.
