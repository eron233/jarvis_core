# Proximos Passos

## Proximo bloco recomendado

- consolidar a persistencia critica para alem de JSON puro nas trilhas de fila, auditoria e eventos mais sensiveis
- BLOCO 12.6 - relatorio semanal de seguranca
- validar instalacao real do servico Windows em terminal administrativo neste host

## Delta recomendado

- consolidar fraquezas, remedios e acoes automaticas em relatorio semanal em pt-BR
- avaliar migracao de fila e auditoria para armazenamento transacional simples
- registrar o servico `JarvisRuntimeService` com privilegio administrativo real
- validar inicio automatico do servico apos reboot controlado
- destacar imediatamente apenas riscos criticos e excecoes reais
- separar novidades da semana de achados recorrentes
- transformar a saida em base reutilizavel para painel e API

## Criterios de aceite

- nenhuma duplicacao da logica de runtime, API, deploy ou auditoria
- servico Windows instalado e iniciando `runtime/server.py` automaticamente
- prova de aderencia entre processo vivo e commit exposta via endpoint de identidade
- consolidacao periodica com escalonamento imediato apenas para urgencias criticas
- saidas tecnicas, diretas e auditaveis
- base pronta para consolidacao por excecao no ciclo seguinte
