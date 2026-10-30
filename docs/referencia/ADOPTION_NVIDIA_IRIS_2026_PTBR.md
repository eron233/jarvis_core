# Íris: segurança de agentes e avaliação NVIDIA (29/10/2026)

**Estado:** decisão arquitetural e código em PR de revisão. **Não representa integração homologada.**

## 1. Correção prévia obrigatória: autorizações P0

O PR #32 propõe, sem alterar `dev` ou produção:

- Tarefa sem aprovação explícita nunca é aprovada automaticamente pela fila, pelo validador ou pela API.
- `POST /api/tarefas` recusa `approved=true`; cliente de API não pode aprovar a própria solicitação.
- A aprovação administrativa de uma tarefa **já enfileirada** requer `POST /api/tarefas/{task_id}/aprovar` com corpo `{"senha_admin":"..."}`, autenticação do dispositivo, proteção anti-replay e, quando instâncias estiverem ativas, credenciais da Íris Original.
- O runtime preserva um registro **somente em memória**, vinculado ao conteúdo material completo da tarefa; expira após 300 segundos e é consumido na primeira tentativa de execução. Alterações invalidam o vínculo. Não guarda senha no registro.
- Nenhuma flag `approved` arbitrária dentro do JSON de uma tarefa deve autorizar efeitos sensíveis pelo caminho do runtime.

### Limites

- O canal antigo da API exige token/dispositivo confiável; para essa ação sensível a senha administrativa é uma segunda barreira. **Exigir HTTPS ou loopback confiável:** senha não pode trafegar em HTTP exposto na rede.
- Aprovações não sobrevivem ao reinício por decisão de segurança; ações antigas precisam ser reconfirmadas.
- Módulos que ignoram `InternalAgentRuntime` e chamam workers, serviços ou métodos de privilégio diretamente exigem auditoria individual. Isto não prova isolamento global.
- `ConstitutionalPolicy` é classificação, não execução blindada; o caminho decisório autoritativo passa por `InternalAgentRuntime`.
- Revisão contra elevação de privilégio, mutação concorrente, injeção de prompts, manipulação da fila, falha de relógio, repetição de requisição e desvio por endpoints alternativos continua necessária.
- Os testes adicionados **não foram executados neste ambiente**. Não fazer merge sem teste real.

## 2. NVIDIA OpenShell: P1, somente opt-in

Referências oficiais:

- https://docs.nvidia.com/openshell/latest/about/installation/
- https://docs.nvidia.com/openshell/latest/sandboxes/manage-sandboxes
- https://docs.nvidia.com/openshell/latest/sdk/python

Decisão: **não instalar automaticamente** e **não trocar** os executores existentes sem homologação.

Proposta de integração:

1. Executor experimental separado com `enabled=false` por padrão, somente em Linux controlado.
2. Exigir gateway local explicitamente autorizado, versão fixa, runtime suportado e políticas de filesystem/processo/rede explícitas.
3. Criar sandbox por tarefa, copiar apenas arquivos necessários, sem credenciais da Original, sem diretórios pessoais, tokens ou sockets administrativos.
4. Executar tarefas com limitações de CPU, memória e duração, coletar resultados, logs e evidências de conclusão.
5. Eliminar sandbox em `finally`, registrar falhas como falhas e bloquear qualquer fallback para host sem nova aprovação humana.
6. Validar exfiltração, escape de diretórios, comportamento após timeout e queda do gateway, conexão indevida e isolamento entre instâncias antes de habilitar em uso real.
7. Windows nativo MXC ainda em desenvolvimento; WSL2 experimental. Nada de fingir que a integração está pronta no Windows.

O OpenShell complementa o `security/container_executor.py`; não substitui autenticação e controle de privilégios.

## 3. Nemotron 3.5 Transcribe: P2, opcional

Referências oficiais:

- https://research.nvidia.com/labs/nemotron/NVIDIA-Nemotron-3.5-Transcribe/
- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B

O modelo é de **aproximadamente 34 bilhões de parâmetros totais e 4,3 bilhões ativos**, licença **OpenMDW-1.1**; é um modelo **offline para gravações**, não um substituto pronto para escuta de baixa latência.

- Preservar `faster-whisper` + VAD para STT local leve no fluxo interativo.
- Experimento Nemotron somente por adapter `batch_transcription` **desabilitado** por padrão: transcrição contextual, long-form, identificação de falantes, tradução e revisão de reuniões.
- Benchmark local com áudios em pt-BR, sotaques e ruído: WER/CER, diarização, tradução, latência, RAM/VRAM, custo e ausência de vazamento. Comparar com a pilha atual.
- Respeitar limitações de GPU e licença antes de baixar ou redistribuir pesos. BF16 é descrito pela NVIDIA para H100 80 GB; variantes otimizadas e GGUF possuem requisitos e resultados diferentes. A RTX 5090 **não está homologada** para a Íris por esta análise.
- Nenhum download, instalação ou gasto sem decisão operacional explícita.

## 4. Próxima decisão objetiva

**P0:** executar localmente `python -m pytest tests/test_constitutional_policy.py tests/test_api.py tests/test_planner.py -q`; auditar todos os pontos de execução de operações sensíveis. Testar especialmente que:
1. Uma tarefa sensível enfileirada sem aprovação fica bloqueada.
2. Uma `approved=true` forjada não libera execução.
3. Senha inválida não aprova; senha válida dá concessão por tarefa por cinco minutos.
4. Alteração de qualquer parâmetro material invalida a aprovação.
5. Após uma tentativa ou reinício, a concessão deixa de valer.
6. Tarefas internas de baixo risco continuam executáveis.
7. Código desconhecido não é executado fora do sandbox sem autorização.
8. O fluxo de instância residente/delegada nunca consegue aprovar tarefas da Original.

**P1:** protótipo isolado e mensurável OpenShell após P0 homologado.

**P2:** comparar Nemotron com faster-whisper usando gravações reais e hardware disponível; somente adotar se houver vantagem comprovada.

**Regra de release:** branch de trabalho → testes locais → revisão → `dev`; nunca `staging` ou produção por este PR. **Sem GitHub Actions.**
