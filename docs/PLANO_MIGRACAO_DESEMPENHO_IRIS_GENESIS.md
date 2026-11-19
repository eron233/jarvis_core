# Íris / Gênesis — Plano de migração e desempenho
Data: 2026-11-19 | Estado: planejamento, nenhuma conversão executada.
Repositório da Íris: eron233/jarvis_core (branch master). Kernel experimental: eron233/genesis-os (separado).

## Diretrizes
Objetivo: reduzir latência, RAM, CPU e inicialização preservando segurança, comportamento e operação offline. Rust é candidato ao núcleo, C++ a motores de inferência e C a interfaces de baixo nível; Python poderá permanecer como extensão isolada. Não reescrever sem medir. Não inserir IA no kernel do Gênesis.

## Etapa 0 — Inventário e baseline
- [ ] Auditar entradas genesis_launcher.py, main.py, runtime/, executive_planner/, memory_system/, workers/, security/, interface/, service/ e testes.
- [ ] Mapear dependências, threads, processos, tarefas periódicas, I/O, memória e fluxo de dados.
- [ ] Medir CPU em repouso, RAM pico e residente, startup frio/quente, p50/p95/p99 de resposta e despacho, carga concorrente e consumo por módulo.
- [ ] Definir matriz de hardware e SO; Windows 7 só com requisito e compatibilidade verificada.
Entrega: relatório de gargalos e benchmark reproduzível.

## Etapa 1 — Contratos, segurança e regressão
- [ ] Especificar mensagens versionadas de tarefas, eventos, erros, permissões, cancelamento e prazos.
- [ ] Testes de equivalência, segurança, migração de dados, falha e rollback.
- [ ] Definir chamadas internas e IPC autenticado entre processos isolados; evitar rede local desnecessária.
Entrega: interfaces estáveis e testes verdes.

## Etapa 2 — Otimizar o sistema existente antes de converter
- [ ] Substituir polling desnecessário por eventos; eliminar workers e processos ociosos.
- [ ] Inicializar interface, agentes e modelos sob demanda.
- [ ] Limitar concorrência, filas, caches, contextos e cópias de dados.
- [ ] Indexar consultas lentas e reduzir serializações.
Entrega: benchmarks antes/depois sem regressões.

## Etapa 3 — Executor e núcleo nativo Rust
- [ ] Prototipar scheduler com prioridades, filas limitadas, backpressure, deadlines, cancelamento e shutdown gracioso.
- [ ] Usar I/O assíncrono quando apropriado, pool limitado para CPU e supervisão de subprocessos.
- [ ] Persistir tarefas com recuperação e idempotência; preservar adaptador Python durante migração gradual.
- [ ] Migrar um caminho crítico por vez e comparar desempenho; reverter se piorar.
Entrega: núcleo Rust integrado por contratos e testado.

## Etapa 4 — Memória e armazenamento
- [ ] Separar memória operacional, persistente e de inferência.
- [ ] Recuperar somente contexto relevante; impor orçamento de RAM e cache.
- [ ] Avaliar SQLite versus armazenamento atual, com backup, migração reversível e testes de integridade.
Entrega: redução mensurada de memória e latência.

## Etapa 5 — Agentes e isolamento
- [ ] Definir permissões mínimas por agente, aprovação para ações sensíveis e auditoria.
- [ ] Aplicar quotas de CPU/RAM/processos usando recursos do SO e limites internos.
- [ ] Implementar watchdog, timeout, cancelamento e recuperação de falhas.
- [ ] Tratar arquivos e resultados de ferramentas como dados não confiáveis.
Entrega: testes de isolamento e recuperação.

## Etapa 6 — IA sob demanda
- [ ] Isolar inferência em processo próprio com backend C++/Rust opcional.
- [ ] Comparar modelos quantizados e compatibilidade CPU/GPU por hardware.
- [ ] Medir tempo até primeiro token, tokens/s, RAM do modelo e cache KV.
- [ ] Manter comandos determinísticos offline sem carregar modelo.
Entrega: escolha técnica com benchmark.

## Etapa 7 — Interface e pacote
- [ ] Preservar modo mascote independente e pacote Windows sem Chromium pesado.
- [ ] Medir renderização, animações, inicialização e consumo em repouso.
- [ ] Testar instalador, atualização e QA em máquina real.
Entrega: pacote leve e compatível.

## Etapa 8 — Integração futura com Gênesis OS
- [ ] Criar abstração para arquivos, relógio, memória, processos, IPC, eventos e permissões.
- [ ] Implementar adaptadores Windows/Linux e especificar adaptador futuro Gênesis.
- [ ] Validar kernel experimental em QEMU separadamente; manter Íris no espaço de usuário.
Entrega: contrato de integração sem acoplamento prematuro.

## Etapa 9 — Aceite
- [ ] Executar testes de carga, offline, falhas, retomada e integridade.
- [ ] Comparar p50/p95/p99, CPU, RAM, inicialização e paridade funcional.
- [ ] Liberar gradualmente com rollback validado.
Entrega: relatório de aceite.

## Metas preliminares, não verificadas
Núcleo sem IA em repouso: < 50 MB RAM e CPU próxima de zero; startup < 500 ms em SSD moderno; despacho interno p95 < 5 ms sob carga definida. Essas metas devem ser revisadas após baseline. Nenhum processo Python obrigatório ao final da migração, se a viabilidade for comprovada.

## Regras de execução
Cada etapa requer medição inicial, teste de regressão, limite de recursos, revisão de segurança e rollback. Não migrar módulos rápidos apenas por uniformidade. Este documento não altera código nem inicia a implementação. Respeitar a prioridade de lançamento dos outros dois projetos antes da Íris.
