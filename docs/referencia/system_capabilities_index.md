# Indice de Capacidades do Sistema

Projeto: Sistema Cognitivo JARVIS
Versao da arquitetura: 0.1.0
Idioma padrao: `pt-BR`
Entrypoint do runtime: `jarvis_core/runtime/internal_agent_runtime.py`
Entrypoint do loop local: `jarvis_core/main.py`
Entrypoint do servidor: `jarvis_core/runtime/server.py`
Launcher local oficial: `jarvis_core/jarvis.cmd`

## Objetivo

Este indice resume o que ja existe no JARVIS, onde cada capacidade mora, como o estado persiste e quais testes cobrem o comportamento atual.

## Capacidades Centrais

| Capacidade | Estado | Arquivos principais | Persistencia | Testes |
| --- | --- | --- | --- | --- |
| Identidade e principios constitucionais | Implementada | `constitutional_core/identity.json`, `constitutional_core/principles.json`, `constitutional_core/policy.py` | JSON de configuracao | `tests/test_constitutional_policy.py` |
| Planejador executivo deterministico | Implementada | `executive_planner/planner.py`, `executive_planner/prioritizer.py`, `executive_planner/validator.py`, `executive_planner/audit.py` | Auditoria persistente configuravel + memoria | `tests/test_planner.py`, `tests/test_audit_persistence.py` |
| Fila persistente de tarefas | Implementada | `executive_planner/queue.py` | JSON configuravel | `tests/test_task_queue_persistence.py` |
| Camada de objetivos | Implementada | `intent_layer/goal_manager.py` | JSON configuravel | `tests/test_goal_manager.py` |
| Memoria semantica persistente | Implementada + camada avancada opcional | `memory_system/semantic_memory.py`, `memory_system/advanced_memory.py` | JSON + Qdrant opcional | `tests/test_semantic_memory.py`, `tests/test_advanced_memory.py` |
| Memoria episodica persistente | Implementada | `memory_system/episodic_memory.py` | JSON atomico configuravel | `tests/test_advanced_memory.py`, `tests/test_runtime_bootstrap.py` |
| Memoria procedural persistente | Implementada | `memory_system/procedural_memory.py` | JSON configuravel | `tests/test_procedural_memory.py` |
| Recuperacao vetorial Qdrant + Qwen3 | Opcional, implementada | `memory_system/advanced_memory.py` | Qdrant local/remoto | `tests/test_advanced_memory.py` |
| Memoria conversacional Mem0 OSS | Opcional, implementada | `memory_system/advanced_memory.py` | Mem0 + Qdrant + Ollama | `tests/test_advanced_memory.py` |
| Mapa evolutivo cognitivo | Implementada | `runtime/cognitive_evolution.py`, `interface/brain_avatar/evolution_map.js`, `interface/dashboard/index.html` | `data/cognitive_evolution_history.json` | `tests/test_cognitive_evolution.py`, `tests/test_api.py`, `tests/test_dashboard.py` |
| Loop continuo local | Implementada | `main.py`, `startup_bootstrap.py` | Persistencia final de fila e memoria | `tests/test_main_loop.py`, `tests/test_startup_portability.py` |
| Runtime operacional | Implementada | `runtime/internal_agent_runtime.py`, `runtime/autonomy.py`, `runtime/runtime_identity.py`, `constitutional_core/policy.py` | Reaproveita fila, memoria, auditoria e objetivos | `tests/test_runtime_bootstrap.py`, `tests/test_constitutional_policy.py`, `tests/test_operational_reports.py` |
| API HTTP | Implementada | `interface/api/app.py` | Reaproveita o nucleo | `tests/test_api.py`, `tests/test_dashboard.py` |
| Comando textual unificado | Implementada | `interface/api/app.py`, `runtime/internal_agent_runtime.py`, `security/access_control.py` | Auditoria + memoria episodica | `tests/test_api.py`, `tests/test_access_control.py` |
| Painel mobile-first | Implementada | `interface/dashboard/index.html`, `interface/dashboard/access_gate.html` | Sessao de dispositivo confiavel | `tests/test_dashboard.py` |
| Cliente nativo leve | Implementada e validada | `interface/native_client/jarvis_client.py` | Usa a API local com `nonce` e `timestamp` | `tests/test_native_client.py` + smoke test real contra `/api/comando` |
| Workers uteis por dominio | Implementada | `workers/worker_runtime.py`, `workers/worker_study.py`, `workers/worker_studio.py`, `workers/worker_finance.py`, `workers/worker_utils.py` | Reaproveita memoria e auditoria do runtime | `tests/test_workers.py` |
| Autenticacao por dispositivo confiavel | Implementada | `interface/api/app.py`, `runtime/internal_agent_runtime.py` | Variaveis de ambiente + auditoria persistente | `tests/test_api.py`, `tests/test_dashboard.py` |
| Controle de acesso por voz ou senha | Implementada com endurecimento estrutural | `security/access_control.py`, `runtime/system_config.py`, `runtime/internal_agent_runtime.py`, `interface/api/app.py` | Bootstrap seguro em `data/jarvis_access_bootstrap.json` + headers da API | `tests/test_access_control.py`, `tests/test_api.py`, `tests/test_cloud_deploy.py` |
| Registro de dispositivos autorizados | Implementada | `device/device_registry.py`, `interface/api/app.py`, `runtime/internal_agent_runtime.py` | JSON configuravel | `tests/test_device_registry.py`, `tests/test_api.py` |
| Relatorios operacionais completos | Implementada | `runtime/internal_agent_runtime.py`, `interface/api/app.py` | Reaproveita estado do runtime | `tests/test_operational_reports.py` |
| Configuracao central de ambiente | Implementada | `runtime/system_config.py`, `.env.example` | Variaveis de ambiente | `tests/test_cloud_deploy.py` |
| Servidor para VPS simples | Implementada | `runtime/server.py`, `startup_bootstrap.py`, `jarvis.cmd` | `logs/` e `reports/` configuraveis | `tests/test_cloud_deploy.py`, `tests/test_startup_portability.py` |
| Servico leve do Windows | Auxiliar, fora do nucleo local validado | `service/jarvis_windows_service.py` | Usa `logs/jarvis.log` e reinicia o servidor | `tests/test_windows_service.py` + validacao administrativa pendente no host alvo |
| Autodefesa operacional | Implementada | `security/self_defense.py`, `runtime/internal_agent_runtime.py` | Relatorio JSON em `reports/` | `tests/test_self_defense.py` |
| Aprendizado estrutural futuro | Auxiliar observacional | `learning/self_improvement.py` | JSON configuravel | Cobertura indireta de runtime; nao participa do nucleo decisorio |
| Preparacao para container | Auxiliar, fora do nucleo local validado | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | Volumes `data/`, `logs/`, `reports/` | `tests/test_cloud_deploy.py` + validacao operacional pendente em host com Docker |
| Nucleo de conhecimento defensivo | Implementada | `security/security_knowledge_core.py`, `security/__init__.py` | Exportavel para memorias do sistema | `tests/test_security_knowledge_core.py` |
| Modelagem de ameaca interna | Implementada | `security/threat_model_engine.py`, `security/__init__.py` | Reaproveita estado do runtime e relatorios de ambiente | `tests/test_threat_model_engine.py` |
| Gemeo de seguranca isolado | Implementada | `security/security_twin.py`, `security/twin_state/.gitkeep` | JSON isolado em `security/twin_state/` ou path configurado | `tests/test_security_twin.py` |
| Validacao interna controlada | Implementada | `security/security_validation_engine.py`, `security/security_twin.py` | Executa apenas sobre o snapshot isolado | `tests/test_security_validation_engine.py` |
| Remediacao hibrida | Implementada | `security/remediation_engine.py`, `executive_planner/audit.py` | Reaproveita runtime, twin e relatorios de validacao | `tests/test_remediation_engine.py` |

## Capacidades do Runtime

- bootstrapar planner, fila, memoria, objetivos e workers
- carregar e expor a politica constitucional ativa
- recuperar fila, memoria e objetivos no startup
- consultar e registrar guidance procedural
- enriquecer memoria semantica com resumos e evidencias dos workers
- registrar eventos episodicos e relatorios operacionais
- registrar crescimento cognitivo historico em niveis temporalmente filtraveis
- proteger execucao por regras de autonomia
- persistir estado no shutdown
- processar comandos textuais com niveis admin e guest
- executar autodiagnostico defensivo integrado
- manter watchdog do loop principal

## Capacidades da API

- healthcheck publico em `/health`
- healthcheck rico protegido em `/api/health`
- comando textual em `/api/comando`
- status do sistema
- execucao de ciclo do planner
- listagem e criacao de tarefas
- consulta de objetivos
- consulta de memoria recente
- mapa evolutivo cognitivo e analise cognitiva
- relatorios completos de sistema, fila, objetivos, memoria e auditoria

## Capacidades do Deploy

- start unico por `python runtime/server.py`
- start local oficial por `.\jarvis.cmd server`
- validacao local de ambiente por `.\jarvis.cmd check-config`
- start em container por `docker compose up --build -d` quando houver host com Docker validado
- configuracao por variaveis de ambiente
- logs em `logs/jarvis.log`
- relatorio de ambiente em `reports/environment_report.json`
- relatorio de shutdown em `reports/shutdown_report.json`
- recuperacao segura de arquivo JSON corrompido com backup `.corrompido-*.json`

## Capacidades de Autodefesa

- organizar conhecimento defensivo por dominio
- mapear controles de identidade e acesso
- mapear controles de aplicacao
- mapear controles de infraestrutura
- mapear controles de continuidade
- mapear controles de observabilidade
- exportar sementes para memoria semantica
- exportar guias para memoria procedural
- inventariar ativos protegidos
- mapear superficies de contato do sistema
- classificar risco por ativo em baixo, medio, alto e critico
- resumir dependencias criticas e risco geral em pt-BR
- espelhar configuracao, fila, memoria, objetivos e estado operacional
- sanitizar conteudo livre e omitir segredos antes da validacao
- validar integridade do gemeo antes de simular falhas defensivas
- simular cenarios de autenticacao, configuracao, persistencia, observabilidade, continuidade e integridade operacional
- gerar fraquezas com score de risco, evidencias e cenarios afetados
- propor tres solucoes estruturadas por fraqueza
- aplicar automaticamente apenas correcoes seguras, reversiveis e auditadas
- escalar para aprovacao humana tudo o que afetar autenticacao, identidade ou arquitetura sensivel

## Artefatos de Persistencia

- `data/task_queue_store.json`
  Finalidade: fila persistente do planner
- `data/semantic_memory_store.json`
  Finalidade: memoria semantica persistente
- `data/procedural_memory_store.json`
  Finalidade: memoria procedural persistente
- `data/goals.json`
  Finalidade: objetivos persistentes
- `data/device_registry.json`
  Finalidade: dispositivos autorizados
- `data/cognitive_evolution_history.json`
  Finalidade: historico persistente de crescimento cognitivo
- `data/jarvis_access_bootstrap.json`
  Finalidade: token efetivo, device confiavel principal e hash seguro da senha administrativa
- `logs/jarvis.log`
  Finalidade: log operacional do servidor
- `reports/environment_report.json`
  Finalidade: resumo do ambiente no startup
- `reports/shutdown_report.json`
  Finalidade: resumo persistido no encerramento
- `reports/self_defense_latest.json`
  Finalidade: ultimo autodiagnostico defensivo do sistema

## Cobertura de Validacao

- `tests/test_planner.py`
  Ciclo do planner, tarefa invalida, tarefa bloqueada e fila vazia
- `tests/test_main_loop.py`
  Loop minimo, bootstrap com persistencia e reinicio seguro
- `tests/test_goal_manager.py`
  Metas estrategicas, objetivos ativos e progresso
- `tests/test_api.py`
  API principal, autenticacao, `/api/comando` e operacao dos endpoints
- `tests/test_access_control.py`
  Voz reconhecida, senha administrativa, wake phrase e modo guest
- `tests/test_device_registry.py`
  Registro, confianca e roundtrip de dispositivos autorizados
- `tests/test_self_defense.py`
  Autodiagnostico operacional integrado ao runtime
- `tests/test_windows_service.py`
  Contrato do launcher do servico Windows
- `tests/test_dashboard.py`
  Redirecionamento raiz e protecao do painel
- `tests/test_operational_reports.py`
  Healthcheck rico e endpoints de relatorio
- `tests/test_runtime_bootstrap.py`
  Bootstrap do runtime e execucao de ciclo
- `tests/test_constitutional_policy.py`
  Carregamento da politica, bloqueios absolutos, aprovacao humana e gate de autonomia
- `tests/test_semantic_memory.py`
  Busca, dominio e persistencia da memoria semantica
- `tests/test_procedural_memory.py`
  Estrutura, busca, persistencia e guidance procedural no runtime
- `tests/test_cognitive_evolution.py`
  Persistencia, niveis temporais e analise do historico cognitivo
- `tests/test_workers.py`
  Utilidade concreta dos workers, evidencias e integracao com o dispatch
- `tests/test_task_queue_persistence.py`
  Persistencia e recuperacao da fila
- `tests/test_cloud_deploy.py`
  Configuracao de ambiente, startup em paths configuraveis, healthcheck de deploy e recuperacao de storage corrompido
- `tests/test_startup_portability.py`
  Entrypoints oficiais, bootstrap de imports, launcher Windows e validacao do servidor
- `tests/test_security_knowledge_core.py`
  Dominios defensivos, controles estruturados e semeadura de memoria semantica/procedural
- `tests/test_threat_model_engine.py`
  Inventario de ativos, superficies, dependencias e classificacao de risco do sistema atual
- `tests/test_security_twin.py`
  Snapshot isolado, sanitizacao real e deteccao de adulteracao do gemeo
- `tests/test_security_validation_engine.py`
  Suite defensiva no gemeo com deteccao de fraquezas por categoria
- `tests/test_remediation_engine.py`
  Plano de remediacao, autoaplicacao segura e escalonamento para aprovacao humana

## Lacunas Atuais

- a mitigacao anti-replay ainda e local ao processo e nao substitui assinatura criptografica ou sessao forte
- a persistencia em JSON foi endurecida, mas continua sendo o principal gargalo estrutural para concorrencia multi-processo
- o processo vivo precisa ser sempre validado por `/api/runtime/identidade`; smoke isolado nao basta sem essa prova
- ainda nao houve smoke test real de container neste ambiente por ausencia de `docker`
- a instalacao real do servico Windows ainda depende de terminal com privilegio administrativo neste host
- a politica viva ja governa validator e runtime, mas ainda nao existe geracao controlada de tarefas alinhada a essa mesma politica
- o launcher local oficial existe para Windows atual, e o servico Windows ja esta implementado, mas o registro do servico foi bloqueado por `Acesso negado (5)` neste host
- os workers ja sao uteis, mas ainda nao consomem entrada multimodal nem conectores externos autorizados
- o relatorio consolidado de seguranca e a consolidacao por excecao ainda nao foram implementados
- a geracao controlada de tarefas ainda nao foi implementada
- o monitoramento externo de infraestrutura ainda nao foi adicionado


## Voz local — Ponto 2

| Capacidade | Estado | Implementacao | Observacao |
|---|---|---|---|
| STT local | Implementado opcional | `runtime/voice_stack.py` | faster-whisper + Silero VAD integrado |
| TTS pt-BR leve | Implementado opcional | `runtime/voice_stack.py` | Kokoro ONNX; fallback nativo |
| Wake word | Implementado opcional | `runtime/voice_stack.py` | openWakeWord com modelo local |
| Enhancement | Implementado opcional | `runtime/voice_stack.py` | DeepFilterNet Python/CLI isolado |
| Captura de microfone | Implementada opcional | `runtime/audio_processing_engine.py` | sounddevice; nao simula captura |
| DSP fallback | Implementado | `runtime/audio_processing_engine.py` | noise gate mensuravel; nao inventa SNR |


## Visão/OCR — Ponto 3

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| OCR real leve | Implementado opcional | `learning/vision_stack.py` | PP-OCRv6 small por padrão; tiny configurável |
| Metadados de imagem | Implementado opcional | `learning/image_vision_engine.py` | Pillow; sem inferir dados ausentes |
| Documento visual complexo | Implementado opcional | `learning/vision_stack.py` | PaddleOCR-VL, somente sob demanda |
| Visão geral / VQA | Implementado opcional | `learning/vision_stack.py` | endpoint local Moondream |
| Pré-contexto visual | Implementado | `learning/image_vision_engine.py` | inclui apenas percepções realmente produzidas |
| Pseudo-OCR por bytes | Removido | `learning/image_vision_engine.py` | strings binárias nunca são tratadas como texto visto |


## Documentos — Ponto 4

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| Parsing estrutural | Adapter implementado opcional | `learning/document_stack.py` | Docling; backend real requer provisionamento |
| TXT/JSON/CSV/código | Implementado | `learning/universal_file_extractor.py` | Parsers nativos leves e estritos |
| PDF/Office/EPUB/etc. | Implementado opcional | `learning/document_stack.py` | Sem scraping de bytes |
| Chunking integral | Implementado | `learning/document_stack.py` | Determinístico, configurável |
| Persistência de chunks | Implementado | `learning/research_knowledge_engine.py` | tabela `document_chunks` |
| Artefato Markdown + manifesto | Implementado | `learning/universal_file_extractor.py` | SHA-256 e metadados auditáveis |
| Extração de strings binárias | Removido | `learning/universal_file_extractor.py` | formato sem parser retorna indisponível |


## Web/Pesquisa/Navegação — Ponto 5

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| Metabusca | Adapter implementado opcional | `runtime/web_stack.py` | SearXNG JSON API |
| Crawling/Markdown | Adapter implementado opcional | `runtime/web_stack.py` | Crawl4AI 0.9.4 |
| Browser JS determinístico | Adapter implementado opcional | `runtime/web_stack.py` | Playwright |
| Fetch HTTP leve | Implementado | `runtime/web_stack.py` | fallback real sem browser |
| Gate SSRF | Implementado | `runtime/web_stack.py` | bloqueia destinos locais/privados por padrão |
| Pesquisa ativa | Implementado | `runtime/web_browser_engine.py` | zero fonte fictícia quando backend cai |
| Extração estruturada | Implementado opcional | `learning/scrapegraph_engine.py` | JSON-CSS Crawl4AI; sem placeholders |
| Envelope web legado | Corrigido | `runtime/scrapling_mcp_engine.py` | não afirma MCP/stealth/bypass |
| Agregação multi-fonte | Corrigido | `learning/agent_reach_engine.py` | mede cobertura, não inventa confiança |


## Inferência Local — Ponto 6

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| Runtime llama.cpp | Adapter implementado opcional | `runtime/inference_stack.py` | OpenAI-compatible; modelo não escolhido |
| Runtime Ollama | Adapter implementado opcional | `runtime/inference_stack.py` | fallback/gerenciamento local |
| Roteamento de modelo | Implementado | `runtime/inference_stack.py` | capability → tier → general |
| Fallback de provider | Implementado | `runtime/inference_stack.py` | ordem configurável |
| Métricas de inferência | Implementado | `runtime/inference_stack.py` | latência, usage e tokens/s quando disponível |
| API de inferência | Implementado | `interface/api/app.py` | status/probe/chat |
| Hierarquia sem modelo fictício | Implementado | `runtime/corporate_agent_hierarchy.py` | aliases vazios até benchmark |
| Modelo-base | Deliberadamente pendente | Constituição | escolher somente no hardware real |


## MCP Oficial — Ponto 7

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| Cliente MCP v2 | Adapter implementado opcional | `runtime/mcp_stack.py` | SDK oficial `mcp>=2.2,<3` |
| Descoberta tools/resources/prompts | Implementado | `runtime/mcp_stack.py` | descoberta não concede execução |
| Allowlist de tools | Implementado | `runtime/mcp_stack.py` | bloqueio antes da chamada |
| Allowlist resources/prompts | Implementado | `runtime/mcp_stack.py` | permissões independentes |
| Transporte stdio | Implementado opcional | `runtime/mcp_stack.py` | command/env/cwd controlados |
| Streamable HTTP | Implementado opcional | `runtime/mcp_stack.py` | remoto bloqueado por padrão |
| Servidor MCP do JARVIS | Implementado opcional | `runtime/mcp_stack.py`, `runtime/mcp_server.py` | read-only por padrão |
| API MCP interna | Implementado | `interface/api/app.py` | protegida por dispositivo confiável |
| MCP simulado | Rejeitado | Constituição | envelope legado não conta como protocolo |


## Inteligência do Código — Ponto 8

| Capacidade | Estado | Implementação | Observação |
|---|---|---|---|
| Grafo AST Python local | Implementado | `learning/codebase_intelligence_engine.py` | baseline determinístico + SQLite |
| Símbolos/classes/funções | Implementado | `learning/codebase_intelligence_engine.py` | path/linha auditáveis |
| Call graph local | Implementado | `learning/codebase_intelligence_engine.py` | ambiguidades permanecem não resolvidas |
| Imports e rotas HTTP | Implementado | `learning/codebase_intelligence_engine.py` | evidência estrutural |
| Trace callers/callees | Implementado | `learning/codebase_intelligence_engine.py` | profundidade 1–5 |
| Impacto estrutural | Implementado | `learning/codebase_intelligence_engine.py` | não inventa score de risco |
| Snippet por símbolo | Implementado | `learning/codebase_intelligence_engine.py` | leitura localizada |
| codebase-memory-mcp | Validado opcional / interop real | `learning/codebase_intelligence_engine.py` | v0.11.0 pinado por SHA-256 no CI |
| Graphify heurístico | Endurecido | `runtime/graphify_engine.py` | não fabrica dependências/ciclos |
