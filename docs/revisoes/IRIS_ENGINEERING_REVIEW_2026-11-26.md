# Etapa 5: limites de login, gate de qualidade e inventário de ferramentas
- Limite de 10 tentativas de login do painel por minuto, por processo, sem coletar IP ou credenciais no limitador. Pode bloquear temporariamente usuários legítimos sob abuso; complementar com proteção de borda, sem confiar em X-Forwarded-For arbitrário.
- Limite de comprimento de senha de recuperação.
- Novas regressões HTTP/WebSocket e testes unitários do limitador.
- Executor de qualidade: timeout, falhas resumidas até 100, relatório local integral e release_ready falso se houver skips. --allow-skips é apenas para validação parcial.
- Inventário de 17 revisões verificadas via API GitHub, não instalação. Cppcheck foi movido para cppcheck-opensource/cppcheck; TestEZ arquivado. Metadados de licença não equivalem a revisão jurídica.
- Skill autoral de engenharia adicionada; runtime ainda não tem integração externa validada.
- REA preservado. Sem deploy nem GitHub Actions. Suite completa ainda pendente por falta de checkout local. 
- Risco remanescente: micro-sandbox AST não é fronteira de segurança do SO. Não executar código não confiável por essa via; avaliar migração para executor isolado e bloqueio por padrão. Auditar permissões de ferramentas, múltiplos processos, feed de eventos entre instâncias, limites de saída, credenciais e testes de Windows.
