# Íris, interface nativa do Gênesis (primeiro incremento)

Produto: Gênesis. Nome/persona do assistente visual: Íris. O backend mantém identificadores JARVIS por compatibilidade.

## Implementado
- Retrato fotográfico leve derivado da imagem original gerada no chat, com arte vetorial ilustrativa como fallback.
- Personalização do retrato via variável IRIS_AVATAR_PATH com caminho local de PNG/JPEG (ou outro formato Qt compatível).
- Estados de interface ligados a eventos reais do cliente: offline, idle, working, error. Listening e thinking estão definidos, mas não simulados.
- Diagnóstico do cérebro recolhido por padrão, visualizador pesado construído apenas ao abrir; no modo conversa evita consultas cognitivas periódicas.
- Animação pequena apenas em estados ativos, podendo ser desativada por IRIS_REDUCED_MOTION=1.
- Captura de tela com uma quinta imagem no fluxo de testes Windows, preservando screenshot de widgets reais.
- Testes de normalização de estados, arte SVG e estados Qt.

## Limitações claras
- Não foi entregue reconhecimento de voz ou TTS conversacional da Íris neste incremento.
- O backend não foi renomeado e os comandos existentes JARVIS permanecem compatíveis.
- Desempenho e usabilidade em computador físico exigem medição; não há FPS/latência inventados.
- Um recorte leve da imagem gerada está incluído. A imagem original de alta resolução ainda pode ser selecionada localmente por IRIS_AVATAR_PATH.
- Manter esse incremento em dev até passar pelos testes Windows e suíte.

## Próximo lote
Captura de áudio real, wake phrase Íris (com fallback de compatibilidade), respostas TTS pt-BR configuráveis, modo mascote móvel, benchmark CPU/GPU e acessibilidade.

## Mascote flutuante, versão inicial
- Ativar/desativar usando **Mostrar mascote Íris** na barra lateral do Gênesis.
- Arrastar a personagem pelo desktop; posição é persistida nas configurações do usuário.
- Botão direito no mascote: mudar de monitor, fixar na borda, passeio automático ou abrir o laboratório visual.
- Clicar duas vezes no retrato (ou usar **Laboratório**) abre uma porta animada e uma sala própria.
- No laboratório, segure e arraste os três cartões internos. **Voltar ao desktop** devolve a Íris.
- Quando o mascote for oculto, pode ser reaberto pela janela principal. Não existe click-through irrecuperável.
- Respeita IRIS_REDUCED_MOTION=1 para não executar animação de deslocamento.
- Efeitos visuais nunca afirmam executar testes, observar abas ou controlar outros aplicativos.
- A voz, captura de microfone e sincronização labial continuam reservadas para a última etapa.

## Ambiente recriado da fotografia
A imagem anterior mostrava a Íris diante de um **escritório doméstico / estúdio de programação**, e não um quarto. O fundo é uma reconstrução artística da parte visível: luz quente, quadro urbano à esquerda, monitor com código, cadeira preta, prateleiras de madeira e planta à direita. A foto não permite reconstruir com fidelidade as dimensões ou o que está fora do enquadramento; nenhum detalhe oculto é apresentado como fato.

O arquivo editável está em \`interface/native_app/assets/iris_studio_room.svg\`.
O laboratório agora usa a recriação como cenário; cartões são arrastáveis e podem ser reorganizados e reposicionados; as luzes digitais alternam entre quente/noturna. Os controles afetam **somente o ambiente desenhado**.

A voz continua reservada para a etapa final.
