# Revisao de seguranca e ferramentas da Iris — 2026-11-26

Base: dev c36e602d5d280ab3c2e48613dea17e243c54d7fd. Revisao estatica parcial; nao houve execucao da suite completa.
Existem 99 arquivos test_*.py na base, nao 99 casos executados.

## Mudancas propostas
- MCP: validar porta antes de aceitar URL local ou remota.
- MCP: nao autorizar executavel por basename quando o registro usa caminho.
- Testes de regressao sem rede; fixture SDK usa caminho autorizado explicitamente.
- Executar `python tools/quality_check.py` em checkout isolado com dependencias de teste. A saida JSON resume falhas; logs e XML ficam em diretorio temporario local. Nao publicar logs brutos, que podem conter dados sensiveis.

## Candidatos externos (nenhum instalado ou validado nesta revisao)
- Context Mode: mksglu/context-mode
- RTK: rtk-ai/rtk
- Graphify: Graphify-Labs/graphify
- Superpowers: obra de terceiros; confirmar origem e revisao exatas.
- Ponytail: DietrichGebert/ponytail
- Headroom: headroomlabs-ai/headroom
- Caveman: JuliusBrussee/caveman
- Vitest, Playwright, TestEZ, Nextest, Stryker, fast-check, k6, Cppcheck, GoogleTest, Cargo Mutants: ferramentas por linguagem/projeto; nao dependencias obrigatorias da Iris Python.

Antes de ativar: confirmar origem, licenca, commit fixado, integridade, dependencias transitivas, dados transmitidos, permissoes minimas, isolamento sem credenciais, testes e rollback. Nao executar instaladores remotos sem inspecao. Nao confundir Graphify interno com o externo. Reaproveitar grafo AST, MCP e limites de contexto existentes. Nao habilitar servidores MCP nem repassar segredos por padrao.

## Pendencias
Auditar API e autenticacao, isolamento Original/residentes, mesh, aprovacao de acoes, subprocessos, acesso a arquivos, prompt injection, credenciais, atualizacoes e dependencias. Revisar protecao das branches e exposicao de rede antes de publicar. Executar suite completa, testes reais Windows e integracoes opcionais em ambiente isolado; testes pulados nao equivalem a cobertura.
