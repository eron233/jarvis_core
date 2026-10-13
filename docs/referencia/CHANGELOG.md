# Registro de Mudancas

Todas as mudancas relevantes deste repositorio devem ser documentadas neste arquivo.

## Em desenvolvimento

- Agencia de agentes v0: `runtime/agent_agency.py` adiciona perfis originais pt-BR (engenharia, seguranca, pesquisa, design, qualidade) e pipeline **real** de 1 elaboracao + ate 2 revisoes estruturadas, sem executar arquivos, codigo, shell, MCP ou deploy. Requer `JARVIS_AGENCY_ENABLED=true`, aprovacao por tarefa e modelo **local** existente em loopback; roteamento somente `llamacpp`/`ollama`, com `allow_external=False` e `data_classification=private` mesmo se FreeLLMAPI estiver habilitado. Limites: max. 3 chamadas de inferencia por tarefa, 512 tokens de resposta por etapa solicitados ao backend, textos e criterios limitados, nenhuma aprovacao se reviews forem vazias, truncadas, malformadas ou reprovadas. Parecer de LLM `aprovado` nunca significa testes, independencia comprovada ou homologacao; resultado `rascunho_revisado_nao_homologado` explicito. Auditoria em `data/agent_agency/<uuid>.json` grava hashes, modelos, uso numerico e estados, **sem persistir objetivos e respostas**. Endpoints protegidos: `GET /api/agencia/especialistas`, `POST /api/agencia/planejar` e `POST /api/agencia/executar` (JSON: `{"objetivo":"...","especialidade":"engenharia","criterios":["..."],"aprovado":true}`). `GET` e planejamento nunca executam nada. Exemplo de ativacao apenas depois do provisionamento: `JARVIS_INFERENCE_ENABLED=true`, alias `JARVIS_MODEL_CODING`/`GENERAL` e `JARVIS_MODEL_REASONING` configurados para modelos locais, `JARVIS_AGENCY_ENABLED=true`. Testes: `tests/test_agent_agency.py`, incluindo API autenticada, falhas, mocks de modelo, registro auditavel e integracao HTTP de verdade com **servidor local simulado**, nao modelo LLM real. Fontes conceituais avaliadas: `msitarzewski/agency-agents` (perfis) e `darianrosebrook/agent-agency` (governanca), sem importacao de prompts ou motores de terceiros. Pendente: execucao de ferramentas sandboxed, revisores verdadeiramente independentes, workflows paralelos, recuperacao/resumo persistente, suites de avaliacao em modelo real e homologacao no PC do dono.

- Inferencia FreeLLMAPI experimental: novo `runtime/freellmapi_backend.py` (cliente local OpenAI-compatible de gateway com possivel egresso externo), integrado ao `runtime/inference_stack.py` e `/api/inferencia/chat`, benchmark e status; por padrao DESABILITADO com `JARVIS_INFERENCE_OFFLINE_MODE=true`, fora da ordem de fallback. Exige chave local configurada, modelo explicitamente escolhido, ativacao no ambiente e consentimento por requisicao (`permitir_externo=true` e `classificacao=public`); o modo offline tambem se sobrepoe a endpoint remoto legado. Bloqueia URLs remotas e redirects, remove proxies de ambiente, limita payloads e nao mostra tokens em status. Configuracao `.env.example`, detalhes e limites em `docs/referencia/INFERENCE_STACK_PTBR.md`, regressao com servidor HTTP fake em `tests/test_freellmapi_integration.py`. Nao ha conta, chave ou prova de cota real: testes locais demonstram somente interoperabilidade e regras de seguranca, nao chamada a modelo externo. **Valor inicial:** nenhuma mudanca de comportamento sem opt-in.

- Fábrica de Capacidades v0 (`runtime/capability_foundry.py`): catálogo de receitas validáveis em pt-BR, planejamento sem geração fictícia e primeiro editor concreto `video.trim` baseado em FFmpeg opcional/preinstalado. Cortes exigem aprovação explícita, workspace fechado `data/studio_media`, bloqueio de path traversal/links, tempo limitado, subprocesso sem shell, sem sobrescrever destino e retorno `arquivo_criado_nao_homologado` sem fingir validação audiovisual. Endpoints autenticados `/api/foundry/*`; testes `tests/test_capability_foundry.py`.
- REA experimental (`runtime/rea_integration.py`): adaptador de engenharia reversa ESTÁTICA sob `data/rea_targets`, via MCP oficial com servidor exemplo desabilitado e permissões iniciais de ferramentas de leitura; sem autoinstalação, execução de alvos ou alegar Evidência validada. API autenticada `POST /api/rea/inspecionar`. Testes `tests/test_rea_integration.py` e workflow dedicado `.github/workflows/capability-smoke.yml` para comprovar REA/FFmpeg reais em runners efêmeros. Referência: `docs/referencia/CAPABILITY_FOUNDRY_REA_PTBR.md`. Ainda NÃO existe automação geral de desenvolvimento/reconstrução de software proprietario.

- Segurança P0: corrigido `security/vulnerability_hunter.py`: o motor não executa scanner/fuzzer nem encontra vulnerabilidades reais. Agora declara explicitamente `nao_executado`, `simulation` separada, zero achados sem evidência e nenhuma correção fictícia, mantendo a API antiga com mensagem verdadeira. Nomes dos relatórios são saneados contra travessia de caminhos. Testes: `tests/test_hunter_evidence_contract.py` e atualização de `tests/test_vulnerability_hunter_and_web_reach.py`.
- Guardian v0: criado `security/guardian.py`, observador somente leitura do Microsoft Defender via cmdlets oficiais `Get-MpComputerStatus` e `Get-MpThreatDetection`. Exposto somente por `GET /api/seguranca/guardian/estado` com gate de dispositivo confiável. Sem varredura, quarentena, remoção, alteração de preferências, execução como administrador nem monitoramento contínuo. Distingue eventos históricos de ameaças ativas e retorno vazio de comprovação de segurança; falha como indisponível/parcial. Testes: `tests/test_guardian.py` (mocks Linux/Windows, política e rota) e workflow de Windows somente leitura `.github/workflows/guardian-windows.yml`. A validação funcional no PC do dono segue pendente.

- Experimental Twin Tier 2: criado executor Docker opt-in (`security/container_executor.py`), ligado às ferramentas geradas sem fallback inseguro; imagem com digest SHA-256 obrigatório e previamente local, nenhum mount/socket no container, rede desativada, filesystem somente leitura, usuário não-root, cap-drop, seccomp padrão, limites de recursos, I/O e timeout; reporte `executado_sem_verificacao` sem alegar conclusão. Criados testes unitários e workflow de execução Docker real. Windows nativo e VM Tier 3 ainda pendentes.

- Segurança P0: `ToolDeveloperEngine.develop_tool` valida código gerado apenas com AST/compilação, nunca importando-o ou executando efeitos de inicialização; nomes são limitados a um identificador de arquivo seguro, metadados são inseridos como literais escapados e nenhum sucesso é fabricado quando não há retorno.
- Segurança P0: `execute_tool_in_sandbox` agora falha fechado com `bloqueado_por_seguranca`, `executado=false` e `isolamento_validado=false`. O subprocesso anterior herdava o ambiente e não fornecia isolamento forte. A execução de ferramentas geradas permanecerá indisponível até um executor isolado ser implementado, auditado e testado em host compatível. Testes de regressão: `tests/test_tool_developer_safety.py`.
- Segurança P0: `UltraLightweightSandboxEngine` recusa `tool_name` que faria path traversal, inicia o Python com `-I` e ambiente explicitamente restrito, não inventa `sucesso` diante de stdout malformado e exige comprovação da aplicação de `RLIMIT_CPU` e `RLIMIT_AS` para relatar execução bem-sucedida. Isso NÃO transforma AST/subprocesso em sandbox de segurança forte. Testes de regressão: `tests/test_micro_sandbox_fail_closed.py`.

- Removido de vez o modo legado `api-direct` de `jarvis.cmd`; o launcher agora rejeita esse caminho em vez de mantê-lo como sombra operacional.
- Aposentado `jarvis_native.vbs`; `jarvis_native.pyw` passou a ser o único wrapper técnico remanescente do app nativo.
- Removidos os ganchos de migração automática por paths legados em fila, memória semântica e objetivos; `data/` passa a ser a única origem operacional suportada.
- Convertida `interface/native_app/brain_scene.js` em host fino da biblioteca oficial `interface/brain_avatar`, eliminando a engine paralela de renderização no desktop.
- Unificados os entrypoints e launchers por responsabilidade: `main.py` ficou como loop puro standalone, `runtime/server.py` como servidor HTTP/API oficial e `jarvis.cmd` como launcher tecnico oficial.
- Reduzidos `jarvis_run.cmd`, `jarvis_native.pyw` e `jarvis_native.vbs` a wrappers auxiliares explicitamente documentados, sem disputar a fonte de verdade operacional.
- Transformado o modo `api-direct` de `jarvis.cmd` em shim legado que apenas redireciona para `server`, eliminando um caminho divergente de subida.
- Eliminada a senha administrativa fraca como fallback efetivo; `runtime/system_config.py` agora resolve credenciais seguras por ambiente ou bootstrap persistido em `data/jarvis_access_bootstrap.json`.
- Atualizados `security/access_control.py`, `interface/native_client/jarvis_client.py`, `interface/native_app/config.py` e `jarvis_run.cmd` para consumir o bootstrap seguro em vez de defaults previsiveis.
- Unificados os stores vivos oficiais em `data/` e adicionada migracao automatica de fila, memoria semantica e objetivos a partir dos caminhos legados.
- Corrigido `main.py::bootstrap_runtime()` para preservar componentes explicitamente injetados no runtime e evitar sobrescrita silenciosa por paths vindos do ambiente.
- Endurecido `device/device_registry.py` para remover automaticamente o `device_id` legado fraco `jarvis-dispositivo-local` do store persistente e rejeitar sua reintroducao.
- Endurecidos `memory_system/semantic_memory.py`, `memory_system/procedural_memory.py`, `intent_layer/goal_manager.py`, `runtime/cognitive_evolution.py` e `runtime/server.py` com escrita atomica para reduzir corrupcao parcial.
- Ajustados `.gitignore` e a trilha operacional para separar melhor codigo versionado de estado vivo e artefatos de validacao nativa.
- Corrigido `interface/native_client/jarvis_client.py` para enviar `X-Jarvis-Nonce` e `X-Jarvis-Timestamp`, ficando compativel com a API endurecida.
- Estendido `SystemLoopConfig` com `device_registry_path` e `self_defense_report_path`, eliminando deriva para paths padrao no bootstrap do runtime.
- Ajustado `runtime/server.py`, `main.py` e `interface/api/app.py` para propagar corretamente os paths configurados do registro de dispositivos e do relatorio de autodefesa.
- Tornado `runtime.enqueue_task()` explicitamente duravel no caminho real da API com flush do store apos enfileiramento.
- Endurecido `device/device_registry.py` e `security/self_defense.py` com escrita atomica via arquivo temporario + `os.replace`.
- Adicionados `tests/test_native_client.py` e nova prova da persistencia real da rota `/api/tarefas` em `tests/test_api.py`.
- Revalidado em smoke real o fluxo vivo com fila persistente, cliente nativo, `device_registry` configurado e `self_defense` gravando no diretório de relatórios configurado.

- Endurecida a integridade operacional do runtime com identidade explicita de build e boot em `runtime/runtime_identity.py`.
- Adicionado endpoint `/api/runtime/identidade` para expor commit, timestamps, entrypoint, PID e configuracao relevante da versao em execucao.
- Corrigida a janela de perda silenciosa da fila persistente: o planner deixou de consumir `drain()` antes do commit e passou a usar snapshot + replace atomico.
- Endurecido `executive_planner/queue.py` com travas locais e escrita atomica em disco via `os.replace`.
- Tornada a auditoria persistente em `executive_planner/audit.py` com snapshot, escrita atomica e recarga no bootstrap do runtime.
- Adicionada protecao inicial anti-replay para chamadas mutantes da API por `nonce` e `timestamp`.
- Ajustado `security/access_control.py` para tratar voz apenas como sinal informativo; acesso administrativo agora depende de senha.
- Adicionadas travas reentrantes no runtime para reduzir condicoes de corrida nas rotinas centrais e nos relatorios.
- Atualizados os testes de runtime, fila, API, dashboard, deploy e auditoria; adicionada `tests/test_audit_persistence.py`.
- Validada a deriva do processo vivo antigo em `127.0.0.1:8010`, interrompido o processo residual e comprovada aderencia do codigo atual em execucao controlada.

- Criado `runtime/cognitive_evolution.py` para registrar e persistir o historico evolutivo cognitivo do Jarvis.
- Criado `data/cognitive_evolution_history.json` como store persistente do mapa evolutivo.
- Adicionados endpoints `/api/cognicao/evolucao` e `/api/cognicao/evolucao/analise`.
- Integrado `runtime/internal_agent_runtime.py` para registrar eventos `EVENT_NEW_KNOWLEDGE`, `EVENT_PATTERN_DISCOVERED`, `EVENT_SKILL_IMPROVED`, `EVENT_MEMORY_CONSOLIDATED` e `EVENT_NETWORK_RESTRUCTURE`.
- Criada a camada `interface/brain_avatar/` com renderer, plasticidade, consciencia e `evolution_map.js`.
- Atualizado o painel para exibir o cerebro cognitivo evolutivo e acionar os comandos "Jarvis, mostre sua evolucao" e "Jarvis, analise sua evolucao cognitiva".
- Adicionados testes dedicados em `tests/test_cognitive_evolution.py` e cobertura de API/painel para a nova camada cognitiva.
- Validado smoke test real de `runtime/server.py`, `/health`, `/painel`, `/brain-avatar/evolution_map.js` e `/api/cognicao/evolucao`.
- Criado `security/access_control.py` com voz especial reconhecida (`eron`), senha administrativa segura e fallback guest.
- Criado `device/device_registry.py` para inventario e persistencia de dispositivos autorizados.
- Adicionado endpoint textual `/api/comando` para comando unificado com resposta do runtime.
- Atualizado o painel para enviar comandos ao runtime pela API em vez de resolver tudo no cliente.
- Criado `interface/native_client/jarvis_client.py` como cliente leve para `/api/comando`.
- Criado `security/self_defense.py` como camada operacional de autodiagnostico sobre os motores defensivos existentes.
- Integrado o runtime com autodefesa, registro de dispositivos, aprendizado futuro e logging de comandos.
- Adicionado watchdog no loop principal para continuar operando apos excecoes controladas.
- Criado `service/jarvis_windows_service.py` com supervisao do processo `runtime/server.py` via `win32serviceutil`.
- Criado `learning/self_improvement.py` para preparar a trilha de aprendizado estrutural futuro.
- Adicionada dependencia `pywin32` em `requirements.txt`.
- Adicionados testes para acesso, registro de dispositivos, autodefesa, watchdog e servico Windows.
- Validado smoke test real de `runtime/server.py`, `/health`, `/docs`, `/painel` e `/api/comando`.
- Tentativa de instalacao real do servico Windows ficou bloqueada por permissao administrativa do sistema (`Acesso negado (5)`).
- Evoluidos `worker_runtime.py`, `worker_study.py`, `worker_studio.py` e `worker_finance.py` para utilidade real por dominio.
- Adicionado `workers/worker_utils.py` para respostas estruturadas deterministicas e validacao de dominio.
- Integrado o runtime para aproveitar `summary`, `details` e `evidence` dos workers na memoria semantica.
- Adicionados testes de workers e dispatch em `tests/test_workers.py`.
- Transformada `memory_system/procedural_memory.py` em memoria procedural persistente e pesquisavel.
- Adicionado registro estruturado de heuristicas, contexto, precondicoes, evidencias e resultado observado.
- Integrado o runtime para consultar guidance procedural antes da execucao e registrar novos padroes apos o dispatch.
- Adicionado suporte configuravel a `JARVIS_PROCEDURAL_STORAGE_PATH`.
- Adicionados testes dedicados de roundtrip e integracao em `tests/test_procedural_memory.py`.
- Integrado o constitutional core ao `validator` e ao `runtime` como politica viva.
- Criado `constitutional_core/policy.py` para carregar identidade, principios e limites operacionais.
- Atualizado o gate de autonomia para bloquear por politica proibitiva e exigir aprovacao humana em tarefas sensiveis.
- Adicionada introspeccao segura da politica ativa em `build_system_report`, `build_health_report` e `describe_state`.
- Adicionados testes da politica constitucional em `tests/test_constitutional_policy.py`.
- Tornada portavel a subida de `main.py` e `runtime/server.py` em ambientes Python isolados.
- Adicionado `startup_bootstrap.py` para localizar a raiz do projeto nos entrypoints oficiais.
- Adicionado `jarvis.cmd` como launcher oficial no Windows atual para loop, servidor e validacao de configuracao.
- Adicionado `runtime/server.py --check-config` para validar ambiente e paths sem subir a API.
- Adicionados testes de portabilidade dos entrypoints e smoke coverage do launcher em `tests/test_startup_portability.py`.
- Implementado o loop continuo inicial do sistema em `main.py`.
- Concluida a recarga automatica da memoria semantica no bootstrap do runtime.
- Adicionada persistencia explicita de estado do runtime para encerramento gracioso.
- Adicionados testes do processo continuo, bootstrap com memoria e recuperacao segura de reinicio.
- Atualizada a documentacao obrigatoria do ciclo 1 e o indice de capacidades.
- Implementado `intent_layer/goal_manager.py` para metas estrategicas e objetivos ativos.
- Adicionado vinculo entre tarefas e objetivos por `parent_goal_id`, `parent_goal` e `goal_priority`.
- Integrado o runtime para atualizar progresso de objetivos apos execucao.
- Adicionados testes da camada de objetivos e da integracao com runtime.
- Implementada a API minima do JARVIS em FastAPI em `interface/api/app.py`.
- Adicionada autenticacao inicial por token para endpoints protegidos.
- Expostos endpoints de status, ciclo, tarefas, objetivos, memoria recente e relatorio operacional.
- Adicionada documentacao dedicada da API em `docs/referencia/API_PTBR.md`.
- Implementado o painel mobile-first em `interface/dashboard/index.html`.
- Adicionadas rotas web para acesso ao painel e redirecionamento pela API.
- Incluida entrada textual simples e acoes rapidas para operacao inicial pelo celular.
- Implementada autenticacao inicial por dispositivo confiavel na API e no painel.
- Adicionados `X-Jarvis-Token` e `X-Jarvis-Device-Id` como contrato de acesso protegido.
- Adicionada auditoria de acessos autorizados e negados no runtime.
- Implementados relatorios operacionais completos no runtime e na API.
- Adicionados endpoints dedicados de relatorio e healthcheck rico.
- Atualizado o painel para exibir saude, fila, objetivos, memoria e ocorrencias recentes.
- Implementada configuracao central de ambiente em `runtime/system_config.py`.
- Adicionado runner de servidor em `runtime/server.py` para subir API + loop continuo opcional.
- Adicionada recuperacao segura de arquivos JSON corrompidos com backup no bootstrap.
- Criados `Dockerfile`, `.dockerignore`, `.env.example` e `docker-compose.yml`.
- Definidos diretorios persistentes `data/`, `logs/` e `reports/`.
- Adicionado healthcheck publico em `/health` com resumo de ambiente.
- Escrita de `environment_report.json`, `shutdown_report.json` e `jarvis.log` preparada para deploy.
- Adicionados testes de configuracao, startup e deploy em `tests/test_cloud_deploy.py`.
- Atualizada a documentacao de deploy em `docs/referencia/DEPLOY_PTBR.md`.
- Criado o modulo `security/security_knowledge_core.py` como base de conhecimento defensiva interna.
- Estruturados dominios de identidade, aplicacao, infraestrutura, continuidade e observabilidade.
- Adicionada exportacao deterministica do conhecimento para memoria semantica e procedural.
- Adicionados testes do nucleo defensivo em `tests/test_security_knowledge_core.py`.
- Criado o modulo `security/threat_model_engine.py` para modelagem de ameaca interna.
- Adicionados inventario de ativos, mapa de superficies, dependencias criticas e classificacao de risco.
- Adicionados testes do motor de ameaca em `tests/test_threat_model_engine.py`.
- Criado o modulo `security/security_twin.py` para o gemeo de seguranca isolado.
- Adicionados snapshots sanitizados de configuracao, fila, memoria, objetivos e estado operacional.
- Adicionada validacao de integridade do gemeo e persistencia dedicada em `security/twin_state/`.
- Adicionados testes do gemeo de seguranca em `tests/test_security_twin.py`.
- Criado o modulo `security/security_validation_engine.py` para validacao interna controlada.
- Adicionadas simulacoes defensivas de autenticacao, configuracao, persistencia, observabilidade, continuidade e integridade operacional.
- Adicionada geracao de fraquezas com score de risco, evidencias e cenarios afetados apenas sobre o gemeo.
- Adicionados testes da validacao interna controlada em `tests/test_security_validation_engine.py`.
- Criado o modulo `security/remediation_engine.py` para remediacao hibrida.
- Adicionadas tres solucoes estruturadas por fraqueza: imediata, estrutural e mitigacao operacional.
- Adicionada autoaplicacao limitada a correcoes seguras e reversiveis com auditoria em `security_remediation`.
- Adicionados testes do motor de remediacao em `tests/test_remediation_engine.py`.

## v0.1.0 - Scaffold inicial

- Adicionado o scaffold base da arquitetura cognitiva do JARVIS.
- Adicionados os diretorios de nucleo constitucional, planejamento, intencao, memoria, workers, runtime, infraestrutura, interface e testes.
- Adicionados os arquivos JSON iniciais e os stubs de modulos Python.
- Adicionada a documentacao inicial da arquitetura e do fluxo de trabalho.
