# Proximos Passos

## Proximo bloco recomendado

- Implementar o BLOCO 4 reforcando autenticacao na API e no painel

## Delta recomendado

- mover o token minimo para configuracao operacional explicita
- proteger o painel com fluxo mais claro de autenticacao
- definir usuario inicial root e regra de acesso
- preparar reutilizacao da autenticacao nas proximas interfaces
- manter simplicidade sem criar sistema pesado de identidade

## Criterios de aceite

- nenhuma duplicacao de logica entre runtime, API e painel
- autenticacao simples, clara e segura o suficiente para exposicao inicial
- compatibilidade com deploy simples e operacao remota
