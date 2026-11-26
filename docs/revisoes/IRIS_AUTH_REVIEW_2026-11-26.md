# Revisão 3: autenticação e painel
Base: d1396bc2f2da548a612a6d0ac643f94c358ee95f. Inspeção estática, não execução da suíte.
- Corrige divergência da chave de token entre gate e painel; modo simplificado não envia credenciais antigas do armazenamento.
- Usa formato ISO UTC e nonce criptográfico em ambos os clientes web.
- Exige proteção anti-replay para mutações autenticadas pelo cookie de recuperação, com auditoria; clientes legados por token não mudam.
- Rejeita timestamps excessivos ou fora da faixa sem gerar erro interno.
- Desabilita cache do HTML protegido e do gate.
- Adiciona regressões para contrato HTML, modo de login, timestamp e replay.
Pendências: executar testes e navegador/Windows; substituir armazenamento persistente de token por sessão revogável e expirada, revisar CSRF e limites de tentativa de login, autorização do dono e operações sensíveis. Cookie atual não recebe expiração/revogação no servidor nesta etapa. REA intacto; dependências externas não instaladas.