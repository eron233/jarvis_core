# Visao Geral da Arquitetura

Este documento descreve a estrutura base do scaffold do Sistema Cognitivo JARVIS.

## Nucleo Constitucional

Local: `constitutional_core/`

O Nucleo Constitucional define a identidade do sistema e os principios que governam seu comportamento. No scaffold atual, essa camada e representada por arquivos JSON de configuracao que estabelecem missao, modo de operacao, capacidades e principios de alto nivel, como alinhamento, seguranca, rastreabilidade e adaptacao.

Artefatos principais:

- `constitutional_core/identity.json`
- `constitutional_core/principles.json`

## Planejador Executivo

Local: `executive_planner/`

O Planejador Executivo e responsavel por transformar metas em planos preliminares e manter ordem na execucao das tarefas. Atualmente ele inclui:

- uma fila para entrada de tarefas
- um priorizador para pontuacao ponderada
- um validador para verificacoes estruturais
- um logger de auditoria para rastreabilidade de decisoes
- um planejador para criacao de rascunhos de plano

Espera-se que essa camada evolua para o cerebro de orquestracao que conecta metas, memoria, workers e politica de runtime.

## Camada de Objetivos

Local: `intent_layer/`

A Camada de Objetivos agora possui um `GoalManager` persistente que organiza a direcao do sistema em dois niveis:

- metas estrategicas para orientar o sistema em horizonte mais amplo
- objetivos ativos para execucao operacional e vinculo direto com tarefas

Capacidades atuais:

- leitura e persistencia de `goals.json`
- separacao entre metas estrategicas e objetivos ativos
- prioridade por objetivo
- deadline opcional
- progresso calculado por tarefas vinculadas
- relatorios em pt-BR
- integracao com fila, priorizador e runtime

## Sistema de Memoria

Local: `memory_system/`

O Sistema de Memoria separa o conhecimento armazenado em tres formas distintas:

- memoria episodica para eventos ordenados no tempo e atividade recente
- memoria semantica para fatos e conceitos
- memoria procedural para sequencias de passos reutilizaveis

Essa divisao mantem recuperacao e atualizacao conceitualmente limpas, ao mesmo tempo em que sustenta fluxos futuros de raciocinio e adaptacao.

## Estrutura de Workers

Local: `workers/`

A Estrutura de Workers contem stubs especializados que aceitam tarefas em dominios diferentes. O scaffold atual inclui workers para:

- operacoes de runtime
- financas
- estudio e criacao
- estudo e aprendizado

Cada worker atualmente expoe um metodo `handle` minimo e retorna um payload padronizado de aceitacao. Versoes futuras podem estender esses workers com capacidades, permissoes e integracoes de ferramentas.

## Motor de Runtime

Local: `runtime/`

O Motor de Runtime e a camada de execucao que inicializa o sistema e governa o comportamento autonomo. O scaffold atual inclui:

- `runtime/internal_agent_runtime.py` para inicializacao do runtime
- `runtime/autonomy.py` para regras simples de aprovacao e supervisao

O entrypoint do runtime anuncia dependencias de planejador, memoria e workers como um contrato leve de bootstrap. Conforme a arquitetura evoluir, essa camada deve se tornar o coordenador central de ciclo de vida, despacho de workers, validacao e observabilidade.

## Processo Continuo do Sistema

Local: `main.py`

O processo continuo inicial do JARVIS agora fica concentrado em um entrypoint unico que reaproveita os modulos existentes de runtime, planner, fila e memoria. Essa camada nao recria inteligencia nem duplica componentes; ela apenas coordena o ciclo de vida do sistema.

Capacidades atuais:

- bootstrap do runtime com attachment do planner
- recarga da fila persistente no startup
- recarga da memoria semantica no startup
- loop controlado com `cycle_id`
- logs legiveis por ciclo em pt-BR
- protecao para fila vazia
- encerramento gracioso com persistencia final
- recuperacao segura de reinicio

Essa camada foi mantida propositalmente fina para que futuras interfaces, monitoramento e API controlem o mesmo nucleo sem bifurcar responsabilidades.

## API de Controle

Local: `interface/api/`

A API de controle foi adicionada como uma camada leve em FastAPI sobre o runtime existente. Ela nao cria um novo nucleo; apenas expõe o que o sistema ja sabe fazer por meio de endpoints reutilizaveis.

Capacidades atuais:

- healthcheck publico
- autenticacao minima por token nos endpoints protegidos
- consulta de estado do sistema
- execucao manual de um ciclo do planner
- listagem e criacao de tarefas
- consulta de objetivos
- consulta de memoria recente
- relatorio operacional resumido

Essa camada prepara o terreno para painel mobile, monitoramento e operacao remota sem romper os contratos internos ja estabilizados.
