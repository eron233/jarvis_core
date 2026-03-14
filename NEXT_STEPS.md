# Proximos Passos

## Proximo bloco recomendado

- BLOCO C - memoria procedural forte

## Delta recomendado

- transformar `procedural_memory.py` em store persistente e pesquisavel
- registrar heuristicas e padroes bem-sucedidos apos execucao real
- permitir recuperacao por dominio, tipo de tarefa e resultado
- integrar esse aprendizado ao runtime e ao planner sem duplicar memoria semantica

## Criterios de aceite

- nenhuma duplicacao de logica entre memoria procedural, runtime e planner
- persistencia real em JSON com roundtrip coberto por testes
- heuristicas recuperaveis em execucao real
- atualizacoes auditaveis e relatorios coerentes em pt-BR
