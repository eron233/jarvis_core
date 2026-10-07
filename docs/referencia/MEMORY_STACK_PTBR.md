# Memoria Avancada do JARVIS

## Objetivo

A camada de memoria foi evoluida sem remover o fallback deterministico existente.
O runtime continua funcional sem dependencias pesadas, mas pode ativar uma pilha
local de recuperacao semantica e memoria conversacional persistente.

## Componentes

- **Qwen3-Embedding-0.6B**: embeddings locais para similaridade semantica.
- **Qwen3-Reranker-0.6B**: reranking dos candidatos recuperados.
- **Qdrant**: indice vetorial persistente, local por padrao ou remoto por URL.
- **Mem0 OSS**: memoria conversacional de longo prazo, opcional.
- **Ollama**: LLM local usado pelo Mem0 para extracao/consolidacao de memorias.
- **Fallback deterministico**: busca por tokens do JARVIS permanece ativa quando
  a camada avancada estiver desligada ou indisponivel.

## Instalacao opcional

```powershell
pip install -r requirements-memory.txt
```

Para usar Mem0 sem API paga, instale o Ollama e disponibilize o modelo definido
em `JARVIS_MEM0_LLM_MODEL`.

## Ativacao minima

```env
JARVIS_ADVANCED_MEMORY_ENABLED=true
JARVIS_QDRANT_PATH=/app/data/qdrant
JARVIS_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
JARVIS_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B
```

A primeira consulta semantica pode carregar os modelos localmente. A partir dai,
as entradas novas sao indexadas no Qdrant e a busca combina vetores, reranking e
o score deterministico existente.

## Mem0

Para memoria conversacional consolidada:

```env
JARVIS_MEM0_ENABLED=true
JARVIS_MEM0_USER_ID=jarvis-owner
JARVIS_OLLAMA_BASE_URL=http://localhost:11434
JARVIS_MEM0_LLM_MODEL=qwen3:4b
```

O Mem0 e opcional. A indisponibilidade dele nao impede memoria semantica,
episodica ou procedural.

## Memoria episodica

A memoria episodica agora aceita `storage_path`, usa escrita atomica e e
carregada pelo runtime a partir de `JARVIS_EPISODIC_STORAGE_PATH`. Isso evita
perder o historico recente simplesmente por reiniciar o processo.

## Politica de falha

A memoria avancada nunca e requisito para o bootstrap. Qualquer falha ao carregar
Qdrant, Qwen, Mem0 ou Ollama rebaixa a busca para
`deterministic_token_search`, mantendo o Jarvis operacional e auditavel.
