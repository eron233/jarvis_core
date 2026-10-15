# Gênesis / Íris

**Gênesis** é o aplicativo e sistema cognitivo. **Íris** é a assistente visual
pessoal, com identidade de androide de cabelos prateados e olhos azuis.
O identificador interno legado JARVIS foi mantido para preservar compatibilidade
de API, configuração e memória. Zero não é mais a identidade de interface.

## Arquitetura de instâncias (incremento de segurança isolado)

O código experimental em `security/iris_instance_policy.py` cria uma fronteira **separada do token legado JARVIS** para três perfis:

- **Original:** capacidades exclusivas de fundação, como `corridor.list`, `trade.use`, `system.admin` e provisionamento.
- **Residente:** conversa, seu próprio quarto, memória própria (escopo de permissão), diagnóstico e delegação limitada. **Não** recebe Trade, administração nem corredor central.
- **Delegada:** recebe apenas um subconjunto explícito das permissões do agente que a criou, com prazo de expiração e revogação em cascata.

A política é verificada no backend: menus ocultos não são proteção. As rotas opcionais `/api/iris/instancia`, `/api/iris/quarto`, `/api/iris/corredor`, `/api/iris/preferencias`, `/api/iris/feedback/sinal` e `/api/iris/feedback/resumo` exigem credencial de instância própria e **ficam indisponíveis (503) enquanto a autoridade não for injetada explicitamente no servidor**.

O corredor retorna apenas metadados de instalações cuja visibilidade foi autorizada, nunca arquivos, memórias ou conversas. Sinais de melhoria só são aceitos após opt-in da residente, usando códigos técnicos predefinidos e relatórios agrupados a partir de cinco instalações distintas. Revogar o consentimento retira a contribuição do agregado em memória. A coleta de textos de conversas não existe nesse módulo.

**Limitações e proibições para release:** esta etapa implementa regras e gates, **não uma plataforma SaaS pronta**. A autoridade guarda estado somente em memória; as credenciais de provisionamento ainda não passam por um onboarding independente de usuário; a memória legada, API global e demais recursos do Jarvis continuam pessoais e **não são multi-tenant**. Não distribuir o `JARVIS_TOKEN` pessoal a clientes nem conectar essas rotas a armazenamento compartilhado sem revisão de isolamento, credenciais, consentimento, revogação, persistência e testes E2E. Não há instalação em redes, controle de Bluetooth ou dispositivos externos neste incremento.

## Malha de dispositivos da mesma Íris (fundação experimental)

A Íris **não é replicada como uma pessoa diferente por dispositivo**: vários nós podem pertencer à **mesma identidade de instância** e fornecer presença, áudio, leitura de estado ou computação, conforme autorização e compatibilidade.

**Diferença entre morar e controlar:** computadores Windows/Linux/macOS/Android podem executar um agente com o aplicativo voluntariamente instalado. iOS e televisores usam um cliente de interface quando o sistema permite. Switches, roteadores, cafeteiras, patinetes e outros equipamentos restritos normalmente **não executam nosso runtime**; nesses casos a integração depende de **um gateway/adaptador oficial ou autorizado**. Um aparelho desconhecido não será desbloqueado nem receberá software sem autorização do proprietário.

`device/iris_mesh.py` implementa nesta etapa:
- oferta de pareamento com validade de 5 minutos, aprovação local **declarada** por um cliente confiável, confirmação pelo titular da instância e credencial distinta de cada nó;
- sessão `integrated` como padrão, `visit` apenas por seleção explícita e com tempo máximo; ao sair as credenciais são revogadas e a **limpeza no SO ainda depende do cliente local**;
- inventário isolado por instância, heartbeat (90 s), perda de conectividade, seleção determinística de nó e indicadores de continuidade;
- restrições de superfícies por plataforma: gateway IoT apenas leitura compatível, não execução arbitrária; menus e permissões nunca substituem a autenticação;
- **adaptação por observação técnica**: CPU, memória livre, bateria e latência reportadas por cada cliente autenticado, usadas para escolher nós menos sobrecarregados. Os perfis são **declarativos, não benchmarks independentes**, não contêm conversa, tela, áudio nem dados de terceiros.

API isolada opcional, configurada por `iris_instance_authority` + `iris_device_mesh`: `GET /api/iris/dispositivos`, `GET /api/iris/continuidade`, `GET /api/iris/roteamento?recurso=...`, `GET /api/iris/perfis-tecnicos`, `POST /api/iris/dispositivo/heartbeat` e `POST /api/iris/dispositivo/estado`. Essas rotas **não** expõem o cadastro/pareamento publicamente nem executam comandos remotos.

**Ainda não é uma malha distribuída autônoma em computadores reais.** Não existe transporte seguro P2P, drivers para todos os aparelhos, execução remota, memória criptografada replicada, consenso/eleição entre processos reais, reconexão automática, onboarding comercial autenticado ou recuperação garantida sem servidor. A presença lógica continua existindo no registro quando um nó cai, mas só fica operacional se houver outro runtime compatível e o estado necessário estiver disponível. Os testes simulam perda de nós e decisões, **não provam failover real de uma IA**.

A plataforma multiusuário só deve utilizar essa malha após autenticação de contas, isolamento persistente por tenant, pareamento com consentimento verificável, integração dos adaptadores certificados e homologação de segurança em ambientes reais.

## Persistência cifrada e retomada de sessão (experimental)

Há três componentes opcionais, separados do banco e dos endpoints globais do JARVIS antigo:

- `security/iris_instance_persistence.py`: persiste identidades e **hashes de credenciais** em arquivo autenticado e cifrado por AES-256-GCM; permissões, revogações, visibilidade e opt-in sobrevivem ao reinício.
- `device/iris_mesh_persistence.py`: registra os nós já pareados e seus hashes de tokens em arquivo cifrado. Após reiniciar, **todos aparecem offline** até que cada aparelho envie um novo heartbeat autenticado. O modo visita não é estendido após a expiração.
- `memory_system/iris_state_store.py`: estado JSON cifrado com AES-256-GCM, SQLite WAL transacional, chave separada por instância via HKDF, controle de versão CAS, erros `409` para escritas concorrentes e backup SQLite consistente. A API opcional `/api/iris/memoria/{document_id}` usa exclusivamente autenticação de instância, nunca a credencial global JARVIS. A escrita aceita até 64 KiB por documento e exige `expected_revision`.

Cada componente precisa de **segredos aleatórios próprios de 32 bytes** vindos de um serviço seguro externo ao Git, com backup e procedimento de recuperação. Os arquivos e backups devem permanecer privados; perder as chaves significa perder acesso ao estado cifrado. Os stores de identidade e malha são apropriados apenas a **um processo escritor por arquivo** neste estágio; o futuro serviço multiusuário precisa de banco central com transações, revogação em múltiplos workers e autenticação dos instaladores.

Os testes exercitam um reinício completo dos três stores em processo de teste, com reautenticação de aparelho e continuidade da memória da mesma Íris. Isso **não equivale** a failover transparente entre computadores: os dispositivos ainda não trocam dados diretamente por rede, o servidor da API não configura os componentes por padrão e modelos locais não são migrados. Os arquivos cifrados possibilitam recuperação no mesmo volume ou por backup transportado de forma segura, não disponibilidade garantida independente de servidor.

## Trabalho distribuído entre PCs autorizados (protocolo funcional restrito)

Além do inventário de aparelhos, há um **broker de tarefas** para que dois computadores pareados executem trabalho simultaneamente para a mesma Íris:

- `device/iris_task_broker.py`: fila por instância, lease temporária de 45 segundos, rejeição de acesso entre residentes, reentrega após lease perdida, limites de tamanho e número de jobs. Nenhum comando arbitrário é aceito.
- `device/iris_node_worker.py`: cliente de processamento iniciado voluntariamente pelo proprietário, que faz `POST /api/iris/no/tarefa/claim` e `POST /api/iris/no/tarefa/complete` e só sabe executar `text.word_count`, `math.sum` e `hash.sha256`. Não acessa SO, arquivos, Bluetooth, jogos nem instala programas. Requer HTTPS fora do localhost e bloqueia redirects para não encaminhar tokens.
- `device/iris_task_persistence.py`: broker opcional com snapshots AES-256-GCM, para recuperar filas e reexecutar leases abandonadas após reinício de um coordenador. **Sem exatamente uma execução (at-least-once)**: qualquer tarefa futura com efeitos externos exigirá idempotência e tratamento específico. Continua single-process.
- Rotas opcionais `/api/iris/tarefas`, `/api/iris/tarefas/{job_id}`, `/api/iris/no/tarefa/claim` e `/api/iris/no/tarefa/complete`; somente o dono da instância envia/consulta seus trabalhos, somente o nó nativo pareado integrado recolhe/conclui. Os retornos dos nós são **não verificados**, não prova de que um modelo real tenha executado.

O processo da Íris deve receber explicitamente objetos `IrisInstanceAuthority`, `IrisDeviceMesh`, `IrisTaskBroker` e os stores opcionais em `create_app()`. A inicialização padrão do Jarvis permanece sem essas rotas ativas: **não** habilitar o serviço para clientes comerciais ou pela internet antes de onboarding, TLS real, identidade das instalações, isolamento por tenant e auditoria de segurança. Credenciais nunca devem ir para Git, logs ou linhas de comando compartilhadas.

Isso já valida **computação repartida de tarefas fechadas**, inclusive pelo contrato HTTP no TestClient, mas **não** significa que os modelos cognitivos, memórias de sessão ou decisões da Íris sejam migrados entre computadores. Não há execução de comandos genéricos, failover offline P2P ou operação de aparelhos IoT neste protocolo.

## Replicação de estado e continuidade entre nós (experimental)

O módulo `device/iris_state_replication.py` implementa um protocolo **pull de replicação automática opt-in**. Um computador pareado com a superfície `memory.sync` (permitida somente a agentes nativos integrados) consulta um manifesto e recebe envelopes AES-256-GCM autenticados pelo token exclusivo do nó. O receptor grava os documentos em seu próprio banco SQLite cifrado, com chaves diferentes do computador de origem. O polling recupera falhas transitórias de rede por backoff e encerra diante de alterações suspeitas, revogação ou conflitos de versão. Na API, `GET /api/iris/replication/manifest` e `GET /api/iris/replication/documents/{document_id}` permanecem **desligados por padrão** e exigem injeção de `IrisReplicaSource` mais malha/estado da mesma autoridade.

- A réplica é **somente leitura em relação a um escritor principal**. O checkpoint HMAC detecta se um registro foi editado localmente, impedindo sobrescrita silenciosa. O cliente nunca replica dados de outra instância e jamais usa o corredor administrativo como fonte de memória privada.
- Testes exercitam envio criptografado, diferenças de versão, recuperação após reiniciar SQLite, dados adulterados, revogação, divergência de histórico e transporte HTTP por **dois processos separados no loopback**. Loopback não equivale a homologação com dois PCs físicos.
- `runtime/iris_cognitive_checkpoint.py` integra snapshots pequenos das memórias reais semântica, procedural, episódica e do histórico evolutivo ao banco cifrado por instância. Um documento `cognitive.checkpoint` (até 64 KiB) pode ser replicado e restaurado. É obrigatório criar os componentes de memória **por cliente**; não utilizar os stores globais do JARVIS. Pesos de LLM, cache de contexto interno, ações em andamento e processos não são migrados.
- `device/iris_local_failover.py` oferece um **protótipo de troca de escritor entre processos no mesmo host e banco SQLite**. O holder recebe lease com época monotônica; após expiração, outro nó nativo pareado pode adquirir a liderança. Uma escrita de estado protegida deve enviar `fence_node_id` e `fence_epoch`; o banco valida a lease na mesma transação. Um token de época vencido não pode escrever mesmo após mudança de processo. O `IrisReplicaSink` se recusa a escrever diretamente sobre banco com lease de escritor, evitando contornar o fencing.

**Limites incontornáveis nesta etapa:** não há consenso/quorum entre máquinas físicas, acesso confiável a SQLite por rede, eleição automática distribuída do núcleo de IA, sincronização offline multi-escritor, migração de inferência LLM nem pareamento real validado pela interface/SO do proprietário. Não usar SQLite compartilhado em NFS/SMB como protocolo de consenso. A continuidade demonstrada é de **dados e processos locais autorizados**, e não uma garantia de que a Íris continue raciocinando após desligar qualquer servidor. Um operador precisa configurar as chaves, a origem confiável, os clientes e o polling; nada disso é ativado automaticamente para usuários.

## Núcleo cognitivo distribuído: inferência em nó autorizado (prévia de desenvolvimento)

A Íris agora consegue encaminhar uma tarefa **real de conversação** (`inference.chat`) pelo mesmo broker da malha para um computador pareado com a superfície `compute.infer`. O código de `device/iris_inference_tasks.py` chama o roteador de inferência local já existente (`runtime.inference_stack.LocalInferenceRouter`, compatível com llama.cpp/Ollama). O agente `device/iris_node_worker.py` executa a inferência apenas **no computador em que foi iniciado**, com motor local explícito, e retorna a resposta ao titular da instância. A resposta **não é fabricada** quando o modelo não estiver provisionado.

Para limitar exposição de dados e execução indevida: cada tarefa permite apenas mensagens de texto (`user`/`assistant`, até 8), máximo de 256 tokens gerados, sem ferramentas nem parâmetros arbitrários de modelo; `offline_mode=True` e `allow_remote_endpoints=False` são obrigatórios no nó, e `allow_external=False` é passado em cada inferência. Não há envio automático a APIs externas, acesso ao shell ou leitura do PC do vizinho. Uma instalação só pode executar inferência se tiver sido pareada e autorizada para `compute.infer`. A credencial da Íris é distinta da credencial individual de cada nó.

`runtime/iris_dialogue_service.py` oferece uma conversa persistente por usuário em `IrisEncryptedStateStore`: `start` enfileira a pergunta, `finish` confirma a resposta do worker e grava o turno criptografado; `history` recupera o contexto daquele próprio cliente. O serviço reduz o histórico enviado à inferência, bloqueia turnos concorrentes na mesma sessão e mantém os dados isolados por instância. Rotas opcionais:

- `POST /api/iris/dialogue/turn`: `{"conversation_id":"conversa-001","text":"Oi, Íris"}` com os cabeçalhos de autenticação da instância.
- `GET /api/iris/dialogue/conversa-001/finish`: retorna a resposta quando o nó confirmar a execução.
- `GET /api/iris/dialogue/conversa-001/history`: retorna histórico privado da mesma instância.
- As rotas existentes `POST /api/iris/no/tarefa/claim` e `POST /api/iris/no/tarefa/complete` fazem o processamento autenticado pelo token **do dispositivo**, nunca pelo token da Original.

`runtime/iris_distributed_bootstrap.py` reúne os stores cifrados persistentes, a malha, o broker, o replicador e o diálogo por `create_local_iris_stack(diretorio, environ=...)`, com `stack.api_options()` para integração opcional a `interface.api.app.create_app`. Ele exige `IRIS_OWNER_TOKEN` forte, quatro chaves independentes de 32 bytes em hexadecimal (`IRIS_IDENTITY_KEY_HEX`, `IRIS_MESH_KEY_HEX`, `IRIS_STATE_KEY_HEX`, `IRIS_BROKER_KEY_HEX`), `IRIS_SOURCE_ID` persistente e diretório privado. Gerencie esses valores em um cofre de segredos, nunca no Git. O bootstrap não inicia automaticamente processos, pareamento, nó executor, câmera, microfone ou modelo. Feche o store com `stack.close()`.

**Limitações verificadas:** os testes unitários/HTTP de inferência usam um `FakeRouter`, não um modelo grande instalado; a aplicação só produzirá texto de IA após configurar e iniciar um modelo local real e habilitar explicitamente o stack. A conversa mantém checkpoints cifrados, mas **não migra o KV-cache do modelo, não fornece quorum entre PCs físicos e não garante failover da inferência quando nenhum nó estiver operacional**. Ainda faltam instalador/pareamento reais, homologação Windows e comunicação autônoma independente do serviço central. O resultado já é um protocolo executável e testável de conversação distribuída, não um produto SaaS ou demonstração física pronta.

## Íris no Windows

A branch dev gera o executável portátil no
[workflow Windows](.github/workflows/genesis-windows-build.yml).
Abra a execução aprovada e baixe o artefato
**Genesis-Iris-Windows-portatil**. Extraia a pasta completa, não apenas o EXE.

**Instalação para usuário final:** depois de extrair, execute
**Instalar-Iris.cmd** voluntariamente. O instalador copia o aplicativo para
%LOCALAPPDATA%/Programs/GenesisIris, cria atalho no Menu Iniciar e **abre a Íris
assim que a instalação termina**, em modo mascote. Não requer privilégios
administrativos nem Python instalado. Um download, por si só, não executa
programas, por segurança do Windows.

**Iniciar a cada login (opcional):** clique com o botão direito no mascote e
selecione **Iniciar com o Windows**. O padrão é desligado; a própria opção
também desliga o recurso. Somente a chave do usuário atual é alterada.

**Abrir só o mascote:** execute Genesis.exe --mascot-only (não precisa
inicializar o runtime cognitivo ou o microfone).
**Abrir o Gênesis completo:** execute Genesis.exe. O mascote aparece junto
com o app por padrão, exceto se foi desativado pelo usuário.

### Identidade visual e interações

A Íris possui um corpo 2D chibi articulado (não uma fotografia dentro de
uma janela), olhos expressivos com piscar e acompanhamento horizontal do
cursor, cabelo animado, braços/pernas e cinco dedos que fecham ao agarrar.
A personagem pode andar, sentar, abrir uma passagem para seu laboratório
visual e agarrar a borda de janelas compatíveis no Windows sob ação direta
do usuário. Aplicativos elevados e abas de terceiros não são controlados
universalmente.

Pelo menu de contexto, alterne **mini, normal, grande ou escala personalizada**
(40% a 215%, ajustável por controle deslizante), além de aparências desenhadas **mais fofinha, clássica e elegante**.
São variações gráficas, não alteração real de idade. As escolhas são preservadas
entre execuções, e o modo de movimentação reduzida está disponível por
IRIS_REDUCED_MOTION=1.

O pipeline faz dez capturas reais do aplicativo e valida o EXE, os testes
nativos e o instalador em modo de verificação, sem instalá-lo no runner.
O pacote publicado **não inclui credenciais, tokens, logs ou relatórios gerados**
no ambiente de testes; cada instalação gera seus próprios dados locais.
A interface e o pacote ainda precisam de QA no Windows físico do proprietário,
e o binário não está assinado. A voz fica para a última etapa.

O pacote leve não inclui QtWebEngine/Chromium. Modelos de IA offline precisam
ser instalados e configurados separadamente.

Desenvolvimento sem pacote:


~~~powershell
.\INICIAR_GENESIS.cmd
# ou
python genesis_launcher.py
~~~


---

## Histórico técnico: Sistema Cognitivo JARVIS (nome interno legado)

O JARVIS e um sistema cognitivo modular em construcao, orientado por planejamento deterministico, memoria persistente, objetivos, API de controle, painel mobile-first, auditoria, operacao supervisionada, autodefesa interna e um cerebro cognitivo evolutivo para introspeccao historica. Nesta etapa, o projeto ja consegue subir como servico HTTP, manter fila e memoria entre reinicios, proteger acesso por token + dispositivo confiavel, ser preparado para deploy em VPS simples com Docker e manter um nucleo defensivo de conhecimento para diagnostico de risco do proprio sistema.

Idioma padrao da camada visivel: `pt-BR`

## Visao Geral da Arquitetura

- `constitutional_core/`: identidade e principios do sistema
- `executive_planner/`: fila, priorizacao, validacao, auditoria e ciclo do planner
- `intent_layer/`: metas estrategicas e objetivos ativos
- `memory_system/`: memoria episodica, semantica e procedural, com camada avancada opcional Qdrant/Qwen3/Mem0
- `workers/`: workers por dominio
- `runtime/`: bootstrap do runtime, autonomia, configuracao e servidor
- `security/`: politica de acesso, autodefesa e motores defensivos
- `device/`: registro de dispositivos autorizados
- `interface/api/`: API FastAPI integrada ao nucleo
- `interface/dashboard/`: painel web mobile-first servido pela API
- `interface/brain_avatar/`: renderizacao modular do cerebro cognitivo evolutivo
- `interface/native_client/`: cliente leve para comandos textuais
- `service/`: servico leve do Windows para manter o Jarvis vivo
- `learning/`: base inicial de autoaperfeicoamento estrutural
- `data/`, `logs/`, `reports/`: paths padrao de persistencia e observabilidade
- `tests/`: suite automatizada de regressao

## Entrypoints

- Runtime interno: `runtime/internal_agent_runtime.py`
- Loop continuo local e standalone: `main.py`
- Servidor HTTP/API oficial para deploy e operacao local: `runtime/server.py`
- Launcher tecnico oficial no Windows atual: `jarvis.cmd`
- Atalho UX local para subir o servidor oficial: `jarvis_run.cmd`
- App nativo real: `interface/native_app/main.py`
- Wrapper tecnico sem console do app nativo: `jarvis_native.pyw`
- Cliente leve: `interface/native_client/jarvis_client.py`
- Servico leve do Windows: `service/jarvis_windows_service.py`

## O que o sistema ja faz

- bootstrap do runtime com planner acoplado
- constitutional core carregado como politica viva de validator e runtime
- fila persistente em JSON
- memoria semantica persistente em JSON com busca hibrida opcional Qdrant + Qwen3 Embedding/Reranker
- memoria episodica persistente entre reinicios
- memoria conversacional opcional via Mem0 OSS + Ollama
- memoria procedural persistente com heuristicas reutilizaveis
- objetivos persistentes com progresso
- loop continuo com encerramento gracioso
- API protegida por token e dispositivo confiavel
- painel web para uso em celular
- workers uteis por dominio com resposta estruturada e evidencia
- endpoint textual `/api/comando` com resposta do runtime
- controle de acesso inicial por token, dispositivo confiavel, senha administrativa segura e voz especial para wake phrase
- registro persistente de dispositivos confiaveis
- autodiagnostico de seguranca com gemeo, validacao e remediacao segura
- mapa evolutivo cognitivo persistente em `data/cognitive_evolution_history.json`
- painel com cerebro visual para crescimento historico e analise cognitiva
- endpoints de evolucao cognitiva em `/api/cognicao/evolucao` e `/api/cognicao/evolucao/analise`
- relatorios operacionais completos
- healthcheck publico de deploy em `/health`
- configuracao central por variaveis de ambiente
- preparacao para container e `docker-compose`
- nucleo de conhecimento defensivo para autodefesa interna
- motor de modelagem de ameaca sobre o proprio estado do sistema
- gemeo de seguranca isolado com snapshots sanitizados
- validacao interna controlada apenas sobre o gemeo autorizado
- remediacao hibrida com autoaplicacao limitada a correcoes seguras

## Politica Constitucional Viva

O constitutional core agora deixa de ser apenas configuracional e passa a governar o sistema por meio de `constitutional_core/policy.py`.

Capacidades atuais:

- carregar identidade e principios como politica ativa
- marcar tarefas proibidas por politica constitucional
- exigir aprovacao humana para escopos sensiveis
- orientar o gate de autonomia do runtime
- expor um resumo seguro da politica ativa nos relatorios operacionais

## Memoria Procedural

O JARVIS agora registra padroes de execucao reutilizaveis em `memory_system/procedural_memory.py`.

Capacidades atuais:

- armazenar procedimentos estruturados por dominio e tipo de tarefa
- persistir heuristicas em JSON configuravel
- buscar procedimentos por texto, dominio, tipo e sucesso
- registrar padroes apos execucao real do runtime
- reaproveitar guidance procedural em tarefas semelhantes

## Workers Uteis por Dominio

Os workers deixaram de ser apenas cascas e agora devolvem saidas deterministicas e estruturadas.

Capacidades atuais:

- `worker_runtime`: diagnostico operacional resumido e relatorio tecnico
- `worker_study`: resumo de estudo, topicos e proximos passos
- `worker_studio`: briefing criativo e checklist de producao
- `worker_finance`: observacoes estruturadas e sintese analitica sem automacao financeira real

## Execucao Local

Loop continuo puro:

```powershell
python main.py --max-cycles 1 --stop-when-idle
```

No Windows atual, se `python` nao estiver no `PATH`, use o launcher tecnico oficial:

```powershell
.\jarvis.cmd loop --max-cycles 1 --stop-when-idle
```

Servidor HTTP/API oficial:

```powershell
set JARVIS_ENV=development
set JARVIS_TOKEN=seu_token_seguro
set JARVIS_TRUSTED_DEVICE_ID=eron-celular-principal
python runtime\server.py
```

Opcao equivalente e oficial no ambiente local atual:

```powershell
.\jarvis.cmd server
```

Wrapper UX local para uso humano no Windows:

```powershell
.\jarvis_run.cmd
```

Aplicativo nativo real:

```powershell
python interface\native_app\main.py
```

Wrapper tecnico sem console do aplicativo nativo:

```powershell
pythonw jarvis_native.pyw
```

Cliente leve nativo:

```powershell
python interface\native_client\jarvis_client.py --texto "status do sistema" --token seu_token_seguro --device-id eron-celular-principal
```

Observacao:

- o cliente nativo agora envia automaticamente `nonce` e `timestamp`, ficando compativel com a protecao anti-replay atual da API
- `jarvis.cmd` e a unica fonte de verdade para launchers no Windows; `jarvis_run.cmd` e um atalho UX opcional e `jarvis_native.pyw` e apenas o wrapper tecnico do app nativo
- o launcher nao expoe mais o modo legado `api-direct`

Servico Windows leve:

```powershell
python service\jarvis_windows_service.py install
python service\jarvis_windows_service.py start
```

Observacao:

- a instalacao do servico Windows exige terminal com privilegio administrativo
- o servico Windows e a operacao com Docker ficam fora do nucleo local validado automaticamente nesta sessao; eles permanecem auxiliares ate validacao operacional no host alvo
- o acesso administrativo por comando aceita `voz_identificada=eron` como contexto especial e senha administrativa segura configurada por ambiente ou bootstrap
- a frase especial `Jarvis ta ai` responde `Sim, Sr. Maciel.` apenas quando a voz reconhecida e `eron`

Para iniciar o Jarvis como aplicativo no Windows, aperte a tecla Windows e digite `J`.

Validacao rapida da configuracao sem subir a API:

```powershell
.\jarvis.cmd check-config
```

## Execucao com Docker

Build:

```powershell
docker build -t jarvis-core .
```

Subida com compose:

```powershell
copy .env.example .env
docker compose up --build -d
```

Healthcheck:

```powershell
curl http://localhost:8000/health
```

Painel:

```text
http://localhost:8000/painel
```

## Variaveis de Ambiente Principais

- `JARVIS_TOKEN`
- `JARVIS_TRUSTED_DEVICE_ID`
- `JARVIS_API_HOST`
- `JARVIS_API_PORT`
- `JARVIS_LOOP_INTERVAL_SECONDS`
- `JARVIS_ENV`
- `JARVIS_DATA_DIR`
- `JARVIS_LOG_LEVEL`
- `JARVIS_ENABLE_RUNTIME_LOOP`
- `JARVIS_ENABLE_DASHBOARD`
- `JARVIS_EPISODIC_STORAGE_PATH`
- `JARVIS_PROCEDURAL_STORAGE_PATH`
- `JARVIS_ADVANCED_MEMORY_ENABLED`
- `JARVIS_QDRANT_PATH`
- `JARVIS_EMBEDDING_MODEL`
- `JARVIS_RERANKER_MODEL`
- `JARVIS_MEM0_ENABLED`
- `JARVIS_DEVICE_REGISTRY_PATH`
- `JARVIS_AUDIT_STORAGE_PATH`
- `JARVIS_SELF_DEFENSE_REPORT_PATH`
- `JARVIS_ADMIN_PASSWORD`

O arquivo base fica em `.env.example`.

Se `JARVIS_TOKEN`, `JARVIS_TRUSTED_DEVICE_ID` ou `JARVIS_ADMIN_PASSWORD` nao forem informados com valores fortes, o Jarvis cria um bootstrap seguro em `data/jarvis_access_bootstrap.json` e grava orientacao operacional em `reports/JARVIS_ADMIN_BOOTSTRAP_CREDENTIAL_PTBR.txt`.

Observacoes operacionais importantes:

- o valor legado `jarvis-dispositivo-local` deixou de ser aceito como dispositivo confiavel e e removido automaticamente do registro persistente quando encontrado
- a operacao normal do runtime agora usa apenas stores vivos em `data/` e nao deve mais sujar o Git com estado operacional
- residuos antigos em `tests/_tmp/` podem continuar presos pelo Windows em alguns hosts; eles ficam fora do caminho principal e ignorados pelo Git

## Persistencia

Por padrao, o modo de servidor usa:

- `data/task_queue_store.json`
- `data/semantic_memory_store.json`
- `data/episodic_memory_store.json`
- `data/procedural_memory_store.json`
- `data/qdrant/` quando a memoria vetorial local estiver habilitada
- `data/goals.json`
- `data/device_registry.json`
- `data/runtime_audit_store.json`
- `data/jarvis_access_bootstrap.json`
- `logs/jarvis.log`
- `reports/environment_report.json`
- `reports/shutdown_report.json`
- `reports/self_defense_latest.json`

Esses caminhos podem ser trocados por variaveis de ambiente.

## Autodefesa Interna

O projeto agora inclui `security/security_knowledge_core.py`, que organiza conhecimento defensivo sobre:

- identidade e acesso
- aplicacao
- infraestrutura
- continuidade
- observabilidade

Essa base foi feita para apoiar diagnostico, modelagem de risco e propostas futuras de endurecimento sem executar qualquer acao externa nao autorizada.

O modulo `security/threat_model_engine.py` complementa essa base transformando o estado atual do JARVIS em:

- inventario de ativos protegidos
- mapa de superficies de contato
- classificacao de risco em baixo, medio, alto e critico
- dependencias criticas do sistema

O modulo `security/security_twin.py` amplia a autodefesa criando um espelho isolado do estado atual do JARVIS com:

- snapshot sanitizado de configuracao, fila, memoria e objetivos
- resumo operacional seguro do runtime
- metadados de API e seguranca sem expor segredos
- persistencia isolada em `security/twin_state/`
- validacao de integridade do espelho antes de qualquer simulacao defensiva

O modulo `security/security_validation_engine.py` executa cenarios defensivos controlados somente sobre esse espelho para verificar:

- autenticacao e identidade
- configuracao e startup
- persistencia
- observabilidade
- continuidade
- integridade operacional

O modulo `security/remediation_engine.py` transforma fraquezas detectadas em:

- solucao imediata
- solucao estrutural
- mitigacao operacional

Quando o risco e baixo e a correcao e reversivel, o proprio sistema pode aplicar automaticamente apenas a parte segura, mantendo auditoria e sem tocar em autenticacao estrutural ou no constitutional core.

## Fluxo de Desenvolvimento

1. Implementar apenas o delta faltante do bloco atual.
2. Cobrir comportamento novo com testes em `tests/`.
3. Atualizar `docs/referencia/ARCHITECTURE.md`, `docs/referencia/system_capabilities_index.md` e os relatorios obrigatorios.
4. Registrar a mudanca em `docs/referencia/CHANGELOG.md`.
5. Rodar `python -m unittest discover -s tests -v`.
6. Criar checkpoint git ao final de cada ciclo.

## Notas de Portabilidade

- `main.py` e `runtime/server.py` agora se bootstrapam de forma explicita para localizar a raiz do projeto em ambientes Python isolados
- o modo servidor nao depende do executavel `uvicorn` no `PATH`
- neste ambiente, a forma oficial e confiavel de subir o servidor e `python runtime/server.py` ou `.\jarvis.cmd server`
- `runtime/server.py --check-config` valida ambiente e paths sem prender o terminal com o servidor

## Integridade Operacional

- a versao em execucao agora pode ser verificada em `/api/runtime/identidade`
- o runtime expoe commit, boot, entrypoint, PID e configuracao relevante para evitar deriva silenciosa entre processo vivo e repositorio
- a fila persistente passou a usar commit atomico no planner, reduzindo risco de perda entre leitura e persistencia
- a auditoria operacional agora persiste em disco por padrao no path configuravel `JARVIS_AUDIT_STORAGE_PATH`
- chamadas mutantes da API passaram a exigir `X-Jarvis-Nonce` e `X-Jarvis-Timestamp` para mitigacao inicial de replay

## Documentacao Relacionada

- `docs/referencia/ARCHITECTURE.md`
- `docs/referencia/API_PTBR.md`
- `docs/referencia/DEPLOY_PTBR.md`
- `docs/referencia/system_capabilities_index.md`
- `reports/relatorios_txt/SYSTEM_MATURITY_REPORT_PTBR.txt`
