# Registro de Mudancas

Todas as mudancas relevantes deste repositorio devem ser documentadas neste arquivo.

## Em desenvolvimento

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
- Adicionada documentacao dedicada da API em `API_PTBR.md`.
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
- Atualizada a documentacao de deploy em `DEPLOY_PTBR.md`.
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

## v0.1.0 - Scaffold inicial

- Adicionado o scaffold base da arquitetura cognitiva do JARVIS.
- Adicionados os diretorios de nucleo constitucional, planejamento, intencao, memoria, workers, runtime, infraestrutura, interface e testes.
- Adicionados os arquivos JSON iniciais e os stubs de modulos Python.
- Adicionada a documentacao inicial da arquitetura e do fluxo de trabalho.
