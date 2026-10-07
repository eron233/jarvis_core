# JARVIS — Estado da Arte e Constituição Tecnológica

**Status:** rascunho técnico em `dev`  
**Data-base da pesquisa:** 2026-10-07  
**Escopo:** arquitetura e critérios de seleção; este documento não ativa automaticamente novos motores.

## 1. Objetivo

O JARVIS não deve ser um modelo monolítico nem um catálogo de integrações. Ele deve funcionar como uma plataforma cognitiva modular em que cada capacidade é atendida pelo melhor componente disponível dentro das restrições reais do sistema: gratuito ou open source sempre que possível, executável localmente, mensurável, substituível e compatível com o hardware disponível.

A palavra "melhor" neste projeto significa **melhor solução no conjunto de métricas relevante ao JARVIS**, e não simplesmente o maior modelo ou o repositório com mais estrelas.

O modelo-base permanece **TBD**. A escolha somente será feita após benchmark no hardware real do proprietário.

## 2. Princípios constitucionais tecnológicos

1. **Evidência acima de propaganda.** Nenhuma ferramenta entra por fama, estrelas, vídeo viral ou números de marketing. Alegações precisam ser reproduzíveis ou tratadas explicitamente como alegações do autor.
2. **Nenhuma capacidade falsa.** Indisponível é um estado válido; sucesso fabricado não é. O JARVIS não pode alegar pesquisa, extração, vulnerabilidade, confiança, benchmark ou ação que não tenha ocorrido.
3. **Modularidade e substituição.** Toda integração relevante deve possuir interface suficientemente desacoplada para poder ser trocada quando uma alternativa superar a atual.
4. **Local-first e privacidade.** O caminho normal deve funcionar localmente sempre que tecnicamente razoável. Serviços pagos ou proprietários podem ser fallback opcional, nunca requisito estrutural sem decisão explícita.
5. **Hardware-aware.** O JARVIS deve maximizar capacidade por RAM, VRAM, CPU, latência e energia. Componentes pesados devem ser carregados sob demanda.
6. **Baseline contra candidato.** Uma mudança é uma hipótese, não uma melhoria, até superar a versão de referência nas métricas definidas.
7. **Twin-first.** Tecnologias novas, autoalterações e otimizações passam primeiro pelo JARVIS Experimental Twin.
8. **Reprodutibilidade.** Toda promoção deve registrar versões, configuração, dataset/casos, seed quando aplicável, comandos, métricas, regressões, logs e hashes dos artefatos.
9. **Menor privilégio.** Código gerado ou experimental não recebe automaticamente segredos, credenciais, rede ou acesso ao host.
10. **Qualidade em português brasileiro.** Voz, texto, OCR, busca e percepção devem ser avaliados também em pt-BR; benchmarks apenas em inglês não fecham a decisão.
11. **Sem dependência ideológica de framework.** O planner constitucional e determinístico do JARVIS continua sendo a autoridade. Frameworks externos podem fornecer adapters, ferramentas ou padrões, não substituir o controle central sem evidência superior.
12. **Reavaliação contínua.** Nenhuma escolha é eterna. Uma tecnologia aprovada pode ser substituída quando um candidato vencer a bateria oficial do Twin.

## 3. Classes de integração

- **CORE:** leve, comprovado e essencial; pode permanecer residente ou quase residente.
- **ON_DEMAND:** comprovado, mas pesado/especializado; é carregado somente quando necessário.
- **EXPERIMENTAL:** candidato forte que ainda precisa vencer baseline no Twin.
- **WATCHLIST:** promissor, porém imaturo, pesado, licenciamento/integração incertos ou funcionalidade importante ainda não pronta.
- **REJECT/REPLACE:** implementação que produz falsos positivos, simulação não rotulada, duplicação sem valor ou resultado inferior comprovado.

## 4. Escala de evidência

- **A — forte/reprodutível:** benchmark padronizado ou teste reproduzível, artefatos verificáveis e metodologia clara; idealmente evidência externa.
- **B — boa, mas do próprio projeto:** benchmark reproduzível apresentado pelo autor ou adoção técnica substancial.
- **C — implementação real, benefício não demonstrado:** código existe e funciona, porém vantagem ainda não foi demonstrada no nosso cenário.
- **D — alegação/placeholder:** marketing, demo limitada ou simulação que não comprova capacidade.

Nenhum item B/C é tratado como inferior por definição; ele simplesmente exige mais validação no Twin.

## 5. Matriz inicial de estado da arte

| Domínio | Candidato / tecnologia | Papel no JARVIS | Classe inicial | Observação |
|---|---|---|---|---|
| Runtime de LLM local | **llama.cpp** | Inferência GGUF quantizada, CPU/GPU offload, servidor local | EXPERIMENTAL → provável CORE | Excelente candidato para PC fraco; modelo ainda não escolhido |
| Gerência local de modelos | **Ollama** | Instalação/serviço/API e modelos locais | EXPERIMENTAL | Conveniência; não deve aprisionar o core |
| Gateway multi-modelo | **LiteLLM** | Interface unificada e roteamento | EXPERIMENTAL | Útil quando houver múltiplos backends; revisar licença/overhead |
| Orquestração tipada | **PydanticAI** | Padrões de tools, outputs, dependências e subagentes | EXPERIMENTAL / padrões | Não substituir o planner constitucional por padrão |
| Protocolo de ferramentas | **MCP oficial** | Integração interoperável de ferramentas/contexto | EXPERIMENTAL → provável CORE | Substitui implementações MCP simuladas |
| Memória vetorial | **Qdrant** | Índice vetorial persistente | VALIDADO | Já integrado de forma opcional |
| Embedding | **Qwen3-Embedding 0.6B** | Representação semântica multilíngue | VALIDADO/condicional | Já integrado; validar consumo no hardware |
| Reranking | **Qwen3-Reranker 0.6B** | Reordenação semântica | VALIDADO/condicional | Já integrado; validar consumo no hardware |
| Memória conversacional | **Mem0 OSS** | Consolidação/recuperação de memória longa | VALIDADO/condicional | Integração opcional; backend local preferido |
| Memória temporal/relacional | **Graphiti + FalkorDB** | Eventos, entidades, relações e validade temporal | EXPERIMENTAL | Complementa vetores; não substituir Qdrant automaticamente |
| Conhecimento do próprio código | **codebase-memory-mcp** | Grafo persistente, call graph, impacto, rotas e consultas | EXPERIMENTAL — alta prioridade | Candidato forte para autoconsciência estrutural do código |
| Contexto para agentes de desenvolvimento | **Graft** | Reduzir exploração repetitiva do repo por agentes | EXPERIMENTAL — dev only | Ferramenta para construir o JARVIS, não necessariamente cérebro residente |
| Segurança/dataflow de código | **Joern** | Code Property Graph e análise profunda | ON_DEMAND candidato | Especializado; mais pesado que busca estrutural cotidiana |
| Busca web privada | **SearXNG** | Metabusca local/self-hosted | EXPERIMENTAL | Descoberta de fontes; respeitar termos/fontes |
| Extração web | **Crawl4AI** | Web → Markdown/dados limpos para agentes | EXPERIMENTAL | Substitui scraping heurístico improvisado |
| Browser determinístico | **Playwright** | Navegação, testes e ações web reproduzíveis | EXPERIMENTAL → provável CORE tool | Preferir deterministicidade antes de agente visual |
| Browser adaptativo | **browser-use** | Tarefas web em páginas difíceis/dinâmicas | ON_DEMAND candidato | Fallback adaptativo, não primeiro caminho |
| Documentos | **Docling** | Parsing/layout/tabelas/múltiplos formatos | EXPERIMENTAL — alta prioridade | Substitui extração binária improvisada |
| Conversão difícil | **Marker** | Documento → Markdown/JSON estruturado | ON_DEMAND candidato | Challenger do Docling em documentos difíceis |
| OCR leve | **PaddleOCR PP-OCRv6** | OCR barato e rápido | VALIDADO opcional | Small como padrão; tiny para economia extrema |
| Visão documental | **PaddleOCR-VL 1.6** | Layout, tabelas, fórmulas/documentos complexos | ON_DEMAND validado por interface / backend pendente | Carregar só quando OCR simples não bastar e validar no hardware |
| Visão geral leve | **Moondream local endpoint** | Entendimento de imagem/VQA/detecção | INTERFACE VALIDADA / backend pendente | Adaptador local pronto; modelo exato depende de hardware |
| VAD | **Silero VAD** | Detectar fala antes do STT | EXPERIMENTAL → provável CORE voice | Muito leve |
| STT | **faster-whisper** | Transcrição local multilíngue | EXPERIMENTAL — principal | Benchmark pt-BR obrigatório |
| STT challenger | **Parakeet.cpp** | ASR eficiente quantizado | EXPERIMENTAL | Muito promissor; cobertura pt-BR deve ser provada |
| Wake word | **openWakeWord** | Ativação local ("hey jarvis" disponível) | EXPERIMENTAL | Testar falso positivo/negativo no ambiente real |
| Limpeza de voz | **DeepFilterNet** | Supressão de ruído/realce de fala | ON_DEMAND/CORE voice candidato | Medir custo x ganho |
| TTS | **Chatterbox PT-BR / Qwen3-TTS / candidato leve** | Voz natural local | BENCHMARK PENDENTE | Não escolher antes de teste pt-BR e hardware |
| Geração criativa | **ComfyUI** | Backend modular para imagem/vídeo/áudio/3D | ON_DEMAND candidato | Excelente ecossistema; pesado por natureza |
| Edição de vídeo agentiva | **video-use (arquitetura)** | Transcript → EDL → render → avaliação | EXPERIMENTAL | Reaproveitar arquitetura e substituir dependências pagas por locais |
| Editor visual | **OpenCut** | Editor open source | WATCHLIST | Headless/API/MCP são estratégicos, mas amadurecimento ainda necessário |
| Catálogo de agentes | **Agency Agents** | Fonte de papéis/processos especializados | MINE/PATTERNS ONLY | Extrair bons padrões; não carregar centenas de personas |
| Benchmark de LLM | **lm-evaluation-harness** | Benchmarks locais/reprodutíveis | EXPERIMENTAL → Twin CORE |
| Eval/red-team de IA | **Promptfoo** | Casos, assertions e superfícies de agente | EXPERIMENTAL → Twin CORE |
| Property testing | **Hypothesis** | Gerar edge cases e minimizar falhas | EXPERIMENTAL → Twin CORE |
| API generative testing | **Schemathesis** | OpenAPI/GraphQL stateful/property testing | EXPERIMENTAL → Twin CORE | Muito adequado ao FastAPI existente |
| Fuzzing contínuo | **ClusterFuzzLite** | Fuzzing em CI e crash artifacts | EXPERIMENTAL | Selecionar por componentes compatíveis |
| Fuzzing nativo | **AFL++** | Fuzzing C/C++/Rust/native | ON_DEMAND candidato | Não é a primeira ferramenta para Python puro |
| Lint/qualidade Python | **Ruff** | Lint/format veloz e amplo | EXPERIMENTAL → provável CORE CI |
| Segurança Python | **Bandit** | Análise AST de padrões inseguros | EXPERIMENTAL → Twin/CI |
| Dependências | **OSV-Scanner** | Vulnerabilidades de dependências/lockfiles | EXPERIMENTAL → provável CORE CI |
| SBOM + vulns | **Syft + Grype** | Inventário/SBOM e scanner mais amplo | ON_DEMAND candidato | Complemento ao OSV |
| Profiling leve | **py-spy** | CPU profiling externo com baixo overhead | EXPERIMENTAL → Twin CORE |
| Profiling profundo | **Scalene** | CPU/memória/GPU Python | ON_DEMAND candidato |
| Otimização | **Optuna** | Busca sistemática de thresholds/configurações | EXPERIMENTAL → Twin CORE | Não confundir otimização com autoaprovação |
| Adapters | **PEFT** | LoRA/adapters e troca de especializações | FUTURO / modelo | Depois do benchmark do modelo-base |
| Pós-treino | **TRL** | SFT/DPO/GRPO etc. | FUTURO / modelo | Só quando houver dataset e baseline |
| Treino eficiente | **Unsloth** | Reduzir custo de fine-tuning quando compatível | FUTURO / modelo | Deve ser testado no hardware real |
| Sandbox Windows/Linux | **MXC / containers/WSL2/VM** | Isolamento por risco | EXPERIMENTAL | Nenhuma camada única cobre todos os cenários |
| Ferramentas WASM | **Wasmtime/WASI** | Execução de módulos fortemente confináveis | ON_DEMAND candidato | Bom para tools adaptáveis a WASM |
| Observabilidade AI | **Langfuse / Phoenix** | Traces, datasets e evals | BENCHMARK PENDENTE | Escolher pelo custo operacional real no PC |

## 6. Arquitetura alvo por camadas

```text
Usuário / eventos / dispositivos
             |
             v
Constitutional Core + Executive Planner
             |
             +---- Policy / permissions / provenance / audit
             |
             v
Capability Router
  |          |            |             |
  v          v            v             v
Modelos    Memória      Ferramentas   Especialistas
  |          |            |             |
llama.cpp  Qdrant       MCP           código
Ollama*    Mem0*        Playwright    pesquisa
TBD model  Graphiti*    SearXNG*      segurança
           Code graph*  Crawl4AI*     criação
             |
             v
Percepção e conhecimento
voz / visão / OCR / documentos / mídia
             |
             v
JARVIS Experimental Twin
segurança + qualidade + desempenho + capacidade + modelo
```

`*` indica componente opcional/sob demanda/experimental conforme registry.

O Capability Router não deve usar "todos os melhores componentes" simultaneamente. Ele deve escolher o **menor conjunto capaz de cumprir a tarefa com a qualidade exigida**.

## 7. Política de recursos: residente vs sob demanda

### Residentes leves
Candidatos que fazem sentido manter disponíveis quase continuamente:
- planner constitucional;
- memória estrutural mínima;
- index/metadata;
- roteador de capacidades;
- VAD quando voz estiver ativa;
- health/auditoria;
- componentes extremamente leves de segurança e qualidade.

### Sob demanda
- rerankers/modelos maiores;
- VLMs;
- Joern;
- Docling/Marker em documentos grandes;
- ComfyUI e modelos generativos;
- fuzzers;
- profilers profundos;
- stacks de treino;
- observabilidade pesada.

### Regra
Uma capacidade pesada deve descarregar memória ao terminar quando não houver benefício mensurável em mantê-la residente.

## 8. Protocolo oficial para adotar tecnologia

1. **Descoberta:** registrar candidato e fonte.
2. **Triagem:** confirmar que o projeto existe, licença, atividade, arquitetura e compatibilidade.
3. **Reprodução:** reproduzir pelo menos a capacidade central alegada.
4. **Baseline:** executar a implementação atual do JARVIS no mesmo corpus/cenário.
5. **Benchmark:** comparar qualidade, latência, CPU, RAM/VRAM, falhas, estabilidade e pt-BR quando aplicável.
6. **Integração isolada:** adapter atrás de feature flag no Twin/`dev`.
7. **Regressão:** suite completa e casos específicos.
8. **Decisão:** integrar, integrar parcialmente, manter como challenger, colocar em watchlist ou rejeitar.

Stars, forks e popularidade são metadados de descoberta; **não são métrica de aceitação**.

## 9. Política de melhoria própria

O JARVIS pode propor melhorias em:
- prompts e instruções;
- thresholds;
- roteamento;
- memória;
- chunking/retrieval;
- ferramentas;
- sequência de ferramentas;
- cache;
- parâmetros de inferência;
- algoritmos internos;
- código;
- adapters/modelos futuramente.

Mas o JARVIS vivo não altera a si próprio como prova de conceito. A hipótese é construída e testada em uma cópia isolada no Experimental Twin.

A promoção exige benefício mensurável sem regressão inaceitável.

## 10. Integridade epistemológica — bloqueadores atuais

Até serem reimplementados com backends reais, os módulos abaixo não podem servir como evidência de capacidade:

- `security/vulnerability_hunter.py`: atualmente contém cenários simulados que produzem achados e até rótulo "zero-day" sem descoberta real.
- `learning/agent_reach_engine.py`: resultados/confianças simulados.
- `runtime/scrapling_mcp_engine.py`: conteúdo/claims de extração simulados.
- `learning/scrapegraph_engine.py`: valores placeholder em determinados caminhos.
- `runtime/quantum_tree_search_engine.py`: respostas e conclusões de qualidade excessivamente templadas.

A regra para esses módulos é: **real backend + evidência ou estado "indisponível"**.

## 11. Decisão sobre modelo-base

**ADIADA.**

Nenhum modelo será constitucionalmente escolhido durante esta fase.

No benchmark local, candidatos serão medidos com:
- tempo até primeiro token;
- tokens/s;
- RAM e VRAM;
- qualidade pt-BR;
- raciocínio;
- tool calling;
- structured output;
- capacidade de seguir política;
- coding;
- memória/contexto;
- estabilidade;
- quantização disponível.

O runtime deve aceitar troca de modelo sem alterar a identidade constitucional do JARVIS.

## 12. Fontes primárias da pesquisa inicial

Projetos avaliados nesta fase:
- https://github.com/ggerganov/llama.cpp
- https://github.com/ollama/ollama
- https://github.com/BerriAI/litellm
- https://github.com/pydantic/pydantic-ai
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/qdrant/qdrant
- https://github.com/mem0ai/mem0
- https://github.com/getzep/graphiti
- https://github.com/DeusData/codebase-memory-mcp
- https://github.com/trailhq/Graft
- https://github.com/joernio/joern
- https://github.com/searxng/searxng
- https://github.com/unclecode/crawl4ai
- https://github.com/microsoft/playwright
- https://github.com/browser-use/browser-use
- https://github.com/docling-project/docling
- https://github.com/datalab-to/marker
- https://github.com/PaddlePaddle/PaddleOCR
- https://github.com/vikhyat/moondream
- https://github.com/SYSTRAN/faster-whisper
- https://github.com/snakers4/silero-vad
- https://github.com/dscripka/openWakeWord
- https://github.com/Rikorose/DeepFilterNet
- https://github.com/QwenLM/Qwen3-TTS
- https://github.com/resemble-ai/chatterbox
- https://github.com/comfyanonymous/ComfyUI
- https://github.com/browser-use/video-use
- https://github.com/OpenCut-app/OpenCut
- https://github.com/msitarzewski/agency-agents
- https://github.com/EleutherAI/lm-evaluation-harness
- https://github.com/promptfoo/promptfoo
- https://github.com/HypothesisWorks/hypothesis
- https://github.com/schemathesis/schemathesis
- https://github.com/google/clusterfuzzlite
- https://github.com/AFLplusplus/AFLplusplus
- https://github.com/astral-sh/ruff
- https://github.com/PyCQA/bandit
- https://github.com/google/osv-scanner
- https://github.com/anchore/syft
- https://github.com/anchore/grype
- https://github.com/benfred/py-spy
- https://github.com/plasma-umass/scalene
- https://github.com/optuna/optuna
- https://github.com/huggingface/peft
- https://github.com/huggingface/trl
- https://github.com/unslothai/unsloth
- https://github.com/microsoft/mxc
- https://github.com/bytecodealliance/wasmtime
- https://github.com/langfuse/langfuse
- https://github.com/Arize-ai/phoenix

## 13. Status desta constituição

Este documento é o **baseline de pesquisa**, não uma declaração de que todas as ferramentas acima já foram integradas. A próxima fase deve executar experimentos controlados por categoria, um componente por vez, seguindo `dev → testes → validado`.

A constituição tecnológica é viva: o JARVIS deve saber **por que** usa cada peça e qual evidência justificou essa decisão.
