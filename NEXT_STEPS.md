# Proximos Passos

## Proximo bloco recomendado

- Implementar o BLOCO 3 com `executive_planner/task_generation.py`

## Delta recomendado

- gerar proximas tarefas a partir dos objetivos ativos
- exigir `parent_goal_id` em toda tarefa derivada
- limitar a quantidade de tarefas inferidas por ciclo
- validar toda tarefa gerada antes de entrar na fila
- registrar geracao em auditoria
- manter o escopo apenas em dominios seguros

## Criterios de aceite

- nenhuma duplicacao da logica de fila, validacao ou planner
- tarefas geradas sempre auditaveis
- testes dedicados cobrindo limite, seguranca e vinculo com objetivo
