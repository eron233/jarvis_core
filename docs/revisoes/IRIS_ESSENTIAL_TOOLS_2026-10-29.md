# Revisão das consultas com ferramentas — 2026-10-29

## Escopo e parecer

Revisão do commit `66fcea3dfe59a41001f16a0e8c193a2c3148c870`, das consultas
documentais/estruturais que ele reutiliza e do guia de preparação. Incluiu leitura
separada do código por outro revisor e reproduções em bancos temporários.
Não é uma auditoria integral de segurança de todo o repositório.

A entrega fornece um ciclo de consultas sobre recursos existentes. Não instala
todos os projetos citados nas referências, nem demonstra autonomia de engenharia.
O grafo fornece símbolos e dependências sintáticas; isso não equivale a compreender,
editar, executar e validar um projeto completo.

O código pode ser avaliado por testes de transporte e contratos. A operação com
um modelo real, a qualidade das respostas e o uso no computador de destino
continuam sem homologação. Uma resposta gerada com `status=sucesso` não é
verificação factual nem comprovação de tarefa concluída.

## Achados e correções

| Prioridade | Achado reproduzido | Correção |
| --- | --- | --- |
| P2 | A busca documental não encontrava `CONFIGURAÇÃO` ao consultar `configuração`; o mesmo problema existia para identificadores Python acentuados. As consultas reutilizavam o `LOWER` ASCII do SQLite. | Aplicar NFC e casefold tanto ao texto consultado quanto à consulta, preservando o conteúdo original. |
| P2 | A consulta documental `100%` incluía `1000 ciclos`, e `arquivo_final` incluía `arquivoXfinal`. `%` e `_` eram interpretados como curingas SQL. | Usar busca literal de substring nos documentos. A busca estrutural preserva seu comportamento anterior de padrões. |
| P2 condicional | Com MCP estrutural habilitado, o POST padrão de indexação podia atualizar apenas o índice externo. A consulta nova usa exclusivamente o grafo local e recebia zero resultados. Os testes já preparavam explicitamente o índice local. | Corrigir o guia para `POST /api/codebase/indexar?preferir_externo=false`. Não alterar a preferência global de outros consumidores da API. |
| P3 | Cortar o JSON serializado de um trecho longo eliminava `source_path` e `source_sha256`, que vinham depois do conteúdo. | Reduzir o texto de cada trecho, manter as fontes dos resultados incluídos e contar explicitamente os resultados omitidos para respeitar o limite de contexto. |

As falhas de Unicode e curingas já existiam nas consultas reutilizadas; a revisão
do novo caminho mostrou seu efeito no assistente. As correções não substituem
a busca textual por recuperação semântica, não criam um verificador de fatos e
não garantem que o modelo cite ou interprete corretamente as evidências.

## Validação e limites

Foram acrescentados oito cenários de regressão com documentos e grafo reais.
Seis reproduziram falhas antes das correções; dois preservam casos que já
funcionavam. O conjunto focado de consultas, documentos, grafo e módulos passou:
`66 passed`.

Suíte completa após as correções: **580 passed, 43 skipped, 115 subtests passed,
4 failed**, em 96,63 segundos. As quatro falhas são os mesmos testes anteriores:

- `WebFetchSchemeTests::test_aceita_endereco_http_comum`;
- `ContainerExecutorTests::test_comando_isolado_e_resultado_nao_comprova_conclusao`;
- `ContainerExecutorTests::test_ferramenta_falha_sem_sucesso_inventado`;
- `WebBrowserEngineTests::test_search_uses_real_sources_and_extracts_only_budgeted_pages`.

O ramo que omite resultados inteiros para respeitar o limite foi revisado em
leitura; não ganhou um cenário de regressão dedicado nesta alteração.

Os testes HTTP usam um servidor de modelo programado para devolver respostas
predefinidas. Eles verificam transporte, execução das consultas e mensagens
devolvidas ao modelo, sem provar que um modelo real escolhe ferramentas, usa
as fontes corretamente ou consegue responder ao pedido de maneira útil.

Ambiente disponível: Linux/Python 3.12. A validação no Windows de destino e com
o modelo local escolhido permanece pendente. Nenhum deploy foi realizado.
