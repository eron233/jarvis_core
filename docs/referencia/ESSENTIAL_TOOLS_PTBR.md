# Consultas com ferramentas locais

A Íris pode receber um pedido, solicitar uma ferramenta, ler seu resultado e
formular a resposta. O ciclo usa o roteador de inferência existente e não
depende de uma assinatura do ChatGPT. Precisa de um modelo local que suporte
chamadas de funções no protocolo OpenAI-compatible de llama.cpp ou Ollama.

## Preparação

1. Provisione o modelo no seu computador e configure `JARVIS_INFERENCE_ENABLED=true`
   e `JARVIS_MODEL_GENERAL` com o identificador real dele. Consulte
   [inferência](INFERENCE_STACK_PTBR.md). Não há download automático de modelo.
2. Para consultar documentos, use a ingestão já existente em
   `POST /api/ingestao/universal` (`caminho_arquivo`). A consulta conserva o texto,
   o caminho da fonte, seu hash e o identificador do trecho.
3. Para consultar código, indexe o projeto com o endpoint existente
   `POST /api/codebase/indexar?preferir_externo=false`. Sem esse parâmetro, um MCP
   habilitado pode atualizar apenas o índice externo, que estas consultas não usam.
   A ferramenta usa o grafo AST local; não dispara
   um servidor MCP externo. A análise de impacto descreve dependências, sem
   alegar comprovação dinâmica ou segurança de uma alteração.
4. Inicie o servidor e o aplicativo pelos comandos usuais do README.

## Uso na conversa

Digite, por exemplo:

```text
consultar: O que meus documentos dizem sobre duração da bateria? Cite a fonte.
consultar: Quais funções dependem de bootstrap_runtime?
```

O prefixo utiliza somente ferramentas locais. Os outros comandos da conversa
continuam seguindo o fluxo existente. O aplicativo permite até
`JARVIS_NATIVE_ASSISTANT_TIMEOUT` segundos de espera nessa consulta (500 por
padrão); o tempo da inferência continua sujeito à configuração do roteador.

Quando a autoridade de instâncias estiver ativa, configure no cliente
`IRIS_NATIVE_INSTANCE_ID` e `IRIS_NATIVE_INSTANCE_TOKEN` com credenciais válidas
da Original, além das credenciais usuais do dispositivo. Sem isso o acesso é
negado. Residentes e delegadas não recebem a base documental da Original.
Não há conversão automática do token global em credenciais da Original.

## API

As rotas exigem autenticação do dispositivo, proteção contra repetição nos
POSTs e, no modo com instâncias, credenciais da Original:

- `GET /api/assistente/ferramentas`: esquemas locais e opções web.
- `POST /api/assistente/executar`: uma execução independente, sem histórico
  persistido por este componente.

Corpo de uma consulta local:

```json
{"texto": "Localize referências à bateria nos documentos"}
```

Para autorizar pesquisa pública nesta execução, selecione explicitamente as
ferramentas. A lista substitui a seleção padrão:

```json
{
  "texto": "Pesquise documentação pública do Python sobre sqlite3",
  "ferramentas_permitidas": ["web_search", "web_fetch"],
  "max_rodadas": 2
}
```

Pesquisa precisa do SearXNG configurado. Leitura web reaproveita o motor
HTTP existente com transporte sem proxy, DNS fixado na conexão e sem execução
de JavaScript. Recusa endereços privados/locais, inclusive nos redirecionamentos.
Queries e URLs saem do computador
quando ferramentas web são selecionadas; use pedidos públicos nessa seleção.
Não há fallback para modelo em nuvem, FreeLLMAPI ou endpoint de modelo remoto.

## Ferramentas e limites

| Ferramenta | Função |
| --- | --- |
| `documents_search` | Até cinco trechos da base documental existente |
| `code_search` | Até dez símbolos com arquivo e linha |
| `code_impact` | Dependentes no grafo local, profundidade dois |
| `integrations_status` | Configuração de web/MCP e presença de backend de mídia; não comprova disponibilidade dos serviços |
| `web_search` | Até três resultados públicos do SearXNG, sem extração automática |
| `web_fetch` | Conteúdo de página pública pelas restrições do motor web |

Máximo de quatro tentativas de inferência, três rodadas de ferramentas e seis
chamadas de ferramentas por pedido. Retornos longos são truncados em envelopes
JSON válidos e sinalizados no rastreio. Nos documentos, o corte reduz o texto de
cada trecho e conserva as fontes dos resultados incluídos. Fontes que não couberem
são omitidas com contagem explícita. Ausência de modelo, resposta incompleta,
chamada malformada ou orçamento esgotado não vira sucesso fictício.

`status=sucesso` indica uma resposta gerada pelo ciclo. Não atesta correção factual,
fidelidade às fontes, qualidade do raciocínio ou conclusão de uma tarefa real.
As instruções do prompt não são uma garantia programática contra invenções.

São consultas: não há shell, edição de arquivos, instalação, execução de código
gerado, negociação financeira nem chamada arbitrária de ferramentas MCP pelo
modelo. MCP e FFmpeg continuam acessíveis pelas APIs próprias, com as políticas
anteriores. A memória cifrada das instâncias não é copiada para a base documental.

## Validação

Execute `python -m pytest tests/test_essential_tools.py -q` e a suíte do README.
Os testes exercitam documentos e grafo reais, autenticação, isolamento,
transporte HTTP local e limites. As respostas do modelo no teste são fixtures;
isso não comprova a qualidade ou o suporte a ferramentas de um modelo real.
Uma validação no computador de destino com o modelo escolhido continua necessária.
