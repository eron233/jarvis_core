# Proximos Passos

## Proximo bloco recomendado

- BLOCO 7 — continuidade de estado em ambiente de servidor

## Delta recomendado

- validar retomada real apos restart de container
- ampliar o relatorio de shutdown com historico de ultima retomada
- adicionar smoke test real de Docker quando houver ambiente com Docker disponivel
- reforcar observabilidade de infraestrutura sobre o deploy simples ja criado

## Criterios de aceite

- restart do servico preserva fila, memoria e objetivos
- relatorios de ambiente e shutdown permanecem consistentes
- nenhum enfraquecimento da autenticacao por token e dispositivo confiavel
- nenhuma duplicacao entre runner de servidor, runtime e API
