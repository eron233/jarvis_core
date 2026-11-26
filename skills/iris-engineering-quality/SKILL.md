---
name: iris-engineering-quality
description: Fluxo de testes, revisão e ferramentas de engenharia da Íris.
---

# Engenharia e qualidade

Antes de alterar: localizar os módulos, verificar contratos e testes existentes, minimizar mudanças e preservar REA.
Depois de alterar: criar regressões, executar `python tools/quality_check.py`, investigar apenas falhas pertinentes usando os logs locais. Não tratar testes pulados como aprovação para publicação. Não enviar logs brutos ou credenciais a serviços externos.

O inventário `config/engineering_tools.lock.json` identifica as 17 ferramentas e commits observados no GitHub. Não implica instalação, revisão de licença completa ou autorização de execução. Não usar atualização automática de HEAD. Verificar código e dependências antes de ativar ferramentas. Não converter plugins de ChatGPT em dependências de runtime por mera cópia de instruções.

Ferramentas por projeto, não obrigatórias na Íris: Vitest/Stryker/fast-check (JS), Playwright (web), TestEZ (Roblox, arquivado; avaliar sucessor), Nextest/Cargo Mutants (Rust), Cppcheck/GoogleTest (C++), k6 (carga). Context Mode, RTK e Headroom têm funções sobrepostas: medir separadamente e manter logs completos localmente. Graphify externo não substitui automaticamente o grafo existente. 
