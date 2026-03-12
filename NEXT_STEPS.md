# Proximos Passos

## Proximo bloco recomendado

- Implementar o BLOCO 2 com `intent_layer/goal_manager.py`

## Delta recomendado

- ler e atualizar `intent_layer/goals.json`
- separar metas estrategicas de objetivos ativos
- ligar tarefas a `parent_goal_id`
- calcular progresso por objetivo
- expor relatorios de objetivo em pt-BR
- integrar objetivo com fila, planner, runtime e indice de capacidades

## Criterios de aceite

- nenhuma duplicacao da logica de fila ou planner
- estados de objetivo auditaveis
- testes dedicados cobrindo leitura, atualizacao e progresso
