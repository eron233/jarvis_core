# Revisão arquitetônica de linguagens — Íris
Data: 2026-11-26. Base inspecionada: 8c365c822ec458913f513cc648df1dc763b0efd5. Revisão estática; 241 arquivos Python incluem código e testes, não são 241 módulos de produção. Não há Rust/C/C++ no núcleo atual. Esta etapa não substitui implementações.

## Decisão
Arquitetura híbrida local-first: Python para integração e experimentação; Rust para componentes nativos medidos e fronteiras de memória/concorrência; C/C++ para bibliotecas nativas maduras quando necessário (inferência, multimídia), sem duplicar seus motores. Não usar C/C++ por princípio onde Rust seguro resolve. Python não é automaticamente gargalo de chamadas HTTP/IO, bibliotecas nativas, GPU ou modelos remotos. Não impor framework web pesado nem runtime adicional por estética.

## Inventário e ordem
| Área | Evidência na base | Direção inicial |
|---|---|---|
| Runtime/orquestração | runtime/internal_agent_runtime.py (~99 KB), runtime/agent_agency.py | separar contratos, medir inicialização, ciclos e polling antes de extrair daemon; não portar monólito linha por linha |
| Fila e planner | executive_planner/queue.py usa deque, RLock, deepcopy e persistência JSON; prioritizer.py é aritmética simples | benchmark sem/com persistência; estudar IO transacional e batching sem perder durabilidade; não portar fórmula isolada para ganhar nanosegundos |
| Memória | memory_system/semantic_cache_engine.py: Qdrant opcional, JSON, deepcopy e hashing | medir busca/serialização e RSS; preservar esquemas, permissões e proveniência; avaliar índice nativo somente após perfil |
| Instâncias/segurança | security/iris_instance_policy.py, dashboard_sessions.py, login_limiter.py | preservar autoridade única, isolamento e revogação; não criar fallback permissivo; vetores de paridade antes de qualquer migração |
| Contexto e tools | runtime/essential_tools.py limita saída e mantém fontes; graphify_engine.py é motor interno | medir bytes/tokens e latência; não confundir com Graphify externo; possível extensão Rust para processamento em lote |
| Inferência | runtime/inference_stack.py usa backends HTTP compatíveis com OpenAI | medir latência do backend, TTFT e tokens/s; reutilizar motores C++/Rust existentes, não implementar LLM do zero |
| Sistema | runtime/system_automation.py usa subprocessos | adaptadores de SO; não ampliar permissões na mudança de linguagem |
| UI | interface/native_app PySide6 e dashboard HTML/JS | medir startup, RSS e responsividade; manter Qt enquanto protótipo nativo não provar benefício e acessibilidade |
| REA | runtime/rea_integration.py | preservar integralmente; sem remoção, reescrita ou expansão de privilégios |

## Risco de segurança descoberto durante revisão
runtime/internal_agent_runtime.py: validate_request_replay remove nonces ao exceder 500; runtime/vital_organs/self_optimization_core.py reduz o cache para 200. Evicção por quantidade pode invalidar a proteção antes de expirar a janela HTTP de 120 s. Revisar TTL, saturação fail-closed, atomicidade e persistência por processo, com regressões específicas, antes de otimizar memória. Esta revisão não corrige esse comportamento.

## Contratos de migração
1. Baseline local reproduzível, dados sintéticos, sem credenciais ou envio de métricas. Usar tools/architecture_baseline.py para fila e prioridade; não confundir heap Python com RSS. Medir runtime completo em ambiente de testes isolado, incluindo cold start, CPU ociosa, RSS/PSS quando disponível, p50/p95, recuperação, duração de requisições e consumo de contexto.
2. Priorizar por evidência. Meta de experimento (não resultado): melhoria material e repetível (ex. 20% de p95 ou memória no gargalo escolhido) sem regressão funcional/segurança e sem aumentar custo total de manutenção. Comparar mesmo hardware, entradas, build release, versões, número de amostras e cache.
3. Primeira extensão Rust opcional, interface pequena e em lote; avaliar PyO3/maturin somente após validar toolchain, licença e compatibilidade Windows/Linux. Nenhuma dependência Rust obrigatória até paridade. Python permanece referência durante piloto. Alternativa IPC versionado e local caso seja necessário isolamento de processo; não converter dados internos em uma API de rede pública.
4. Testes diferenciais, limites de entrada, falhas, Unicode, overflow, concorrência, cancelamento, compatibilidade de dados e rollback. Para operações autorizativas, qualquer erro deve negar, não recorrer a implementação mais permissiva.
5. Medir custo da fronteira e regressões, executar quality_check.py e validações reais. Só então ativar módulo nativo, um de cada vez.
6. Compatibilidade: validar Linux x86-64 e Windows moderno primeiro. Windows 7/Pentium/3 GB é cenário restrito, não promessa de suporte por Rust, Qt ou bibliotecas modernas. Não reduzir segurança do sistema para suportá-lo.
7. Íris e Gênesis independentes. Integração futura por processo em userspace com IPC, permissões explícitas, sem chaves ou memória privada no kernel. Nenhuma dependência de boot em IA.

## Estado
Benchmark inicial adicionado nesta etapa, ainda não executado com checkout completo. Rust/Cargo ausentes neste ambiente; sem clone direto GitHub; não houve compilação nativa ou migração funcional. Não alterar produção nem ativar ferramentas externas sem validação. Sem GitHub Actions.
