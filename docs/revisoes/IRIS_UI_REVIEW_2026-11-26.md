# Revisão de interface e segurança — etapa 2

Inspeção estática de interface nativa e painel HTML. A direção adota a clareza de assistentes modernos com identidade própria da Íris, não uma cópia de marcas. O código anterior ainda exibia Zero no painel web e afirmava que todos os módulos estavam disponíveis sem consultar o backend. A janela nativa também usava o modo automático de interpretação de texto do QLabel para mensagens.

Mudanças propostas: identidade correta, cores e hierarquia compartilhadas, respostas da assistente sem cartões pesados, foco e seleção, painel web adaptável, mensagem inicial sem afirmações falsas, nonce criptográfico e erros HTTP tratados. Campo de senha nativo limpo ao enviar. Adicionada regressão Qt para texto literal e seleção. REA não alterado.

Pendências: testar com Qt real, navegador e Windows; conferir contraste e dimensões em screenshots; auditar login web simplificado, armazenamento de credenciais no navegador, autorização de operações mutantes, registro MCP, cadeia de fornecimento e sandbox. Não afirmar que essas áreas foram corrigidas. Instalação dos projetos externos continua pendente de acesso a ambiente com rede e execução; a skill de design é autoral e não substitui os plugins externos.

O PR permanece rascunho até validação.
