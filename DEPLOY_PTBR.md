# Deploy do JARVIS

## Estado atual

O deploy em nuvem ainda nao foi implementado. Este documento existe para consolidar o ponto de partida e evitar lacunas de documentacao ate o BLOCO 12.

## Execucao local atual

```powershell
python main.py --max-cycles 1 --stop-when-idle
```

## Preparacao minima ja existente

- fila persistente em arquivo JSON
- memoria semantica persistente em arquivo JSON
- entrypoint unico do processo continuo em `main.py`

## Pendente para o BLOCO 12

- Dockerfile
- compose ou equivalente
- configuracao por variaveis de ambiente
- documentacao de startup em servidor
- estrategia de logs e volumes persistentes
