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

## Íris articulada (incremento 2)
O mascote anterior com moldura foi substituído por uma personagem 2D de corpo inteiro, desenhada em Qt, preservando a referência facial da androide. Pernas, braços, joelhos, punhos e cinco dedos têm segmentos próprios e os dedos fecham progressivamente em 500 ms. Estados incluem andar, sentar, alcançar, agarrar, puxar e portal. O menu agora é aberto pelo clique direito sobre a personagem, sem controles permanentes.

### Puxar janelas de verdade (Windows)
Posicione a mão da Íris perto da borda superior de uma janela comum, clique com o botão direito e escolha **Agarrar borda de janela próxima**. Os dedos fecham visualmente. Segure e arraste a Íris com o botão esquerdo para deslocar a janela, se o Windows permitir. Solte o botão para abrir a mão. A ação não tenta mover aplicativos elevados, janelas do sistema nem janelas do Gênesis, e não simula um sucesso quando o SO nega o movimento. **Sentar em janela próxima** posiciona a Íris na borda e muda as pernas de postura.

No laboratório da Íris, as abas são movíveis por arraste. Abas de terceiros requerem integração específica, não são manipuladas universalmente. O código não lê telas, não grava áudio, não injeta cliques nem eleva privilégios. Voz continua por último.

**Atalho:** segure Shift enquanto começa a arrastar a Íris perto da borda superior de uma janela compatível. A mão tenta agarrar automaticamente, sem precisar abrir o menu. Caso o Windows negue o movimento, a interação é cancelada; avisos aparecem próximos à personagem e no status do Gênesis.


## Mascote ilustrada chibi (visual V3)
O recorte fotográfico no corpo do boneco foi substituído por **rosto desenhado em Qt**: olhos grandes, pupilas que olham para o cursor, piscar, cabelo prateado com movimento leve, cabeça proporcionalmente maior, traje branco com detalhes azuis e dedos individuais fechando ao agarrar.

**Clique com o botão direito na Íris**:
- **Tamanho:** mini (56%), normal (100%), grande (145%) ou personalizado (40% a 215%). Corpo, área clicável e âncora da mão são redimensionados juntos, com posição corrigida para monitores reais.
- **Estilo visual:** mais fofinha, clássica ou elegante. São variações artísticas de proporções, olhos e cabelo; não representam idade biológica.
- **Iniciar com o Windows:** aparece apenas no executável Windows, desativado por padrão. Esta opção modifica somente a chave de inicialização do usuário atual. Pode ser revertida pelo mesmo menu.

Movimentos mantidos: caminhar, sentar, agarrar, puxar, saltar, repousar e atravessar o portal do estúdio. Não existe voz nem captura de microfone nesta etapa.

## Instalação e inicialização
A transferência de arquivos **não pode executar software automaticamente**, por segurança do sistema operacional. Ao extrair o pacote Windows e executar voluntariamente **Instalar-Iris.cmd**, a Íris é copiada para o perfil do usuário, recebe um atalho no Menu Iniciar e **abre automaticamente após a instalação** em modo mascote, sem depender do servidor.

Se desejar inicializar a cada login, ative **Iniciar com o Windows** pelo menu da Íris após a instalação; não há persistência silenciosa. Também é possível chamar manualmente o script PowerShell com o parâmetro StartWithWindows, mas só deve ser usado com autorização do usuário.

O instalador atua somente no diretório LOCALAPPDATA/Programs/GenesisIris, sem pedir acesso administrativo. O binário portátil continua utilizável sem instalação. O caminho de inicialização é Genesis.exe --mascot-only. A janela principal normal continua disponível ao abrir Genesis.exe sem esse parâmetro. Primeiro lançamento normal mostra o mascote por padrão, salvo se o usuário o tiver escondido.

Validação em Windows: os workflows executam a interface real, o novo modo independente e uma checagem segura do instalador sem alterações no computador do runner. O executável permanece **não assinado** (o SmartScreen pode pedir confirmação). A execução no computador final e integração com janelas de terceiros dependem de testes físicos.
