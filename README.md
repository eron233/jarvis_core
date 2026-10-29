# Gênesis / Íris

**Íris** é uma assistente pessoal de IA em desenvolvimento. **Gênesis** é o aplicativo que reúne a interface desktop, o runtime, a memória, a segurança e os serviços locais. Parte do código mantém o nome interno `JARVIS` para preservar compatibilidade, mas a identidade visual e o produto são **Íris / Gênesis**.

> **Estado:** projeto experimental. Há módulos funcionais e testes automatizados, mas não existe homologação de autonomia distribuída, instalação universal em dispositivos ou execução garantida de um LLM offline em qualquer computador.

## Começar

Pré-requisitos para rodar pelo código: **Python 3.11**, ambiente virtual e dependências do projeto. Para a interface gráfica é necessário um ambiente compatível com **PySide6**.

```bash
git clone https://github.com/eron233/jarvis_core.git
cd jarvis_core
python -m venv .venv
# Ative .venv no seu sistema e instale:
python -m pip install -r requirements.txt
python genesis_launcher.py
```

No **Windows**, também é possível iniciar com `INICIAR_GENESIS.cmd`. Para iniciar somente o mascote, sem executar o servidor, memória ou microfone:

```bash
python genesis_launcher.py --mascot-only
```

O projeto também oferece um servidor local:

```bash
python runtime/server.py --check-config
python runtime/server.py
```

Use `.env.example` apenas como **referência de configuração**. Nunca reutilize tokens ou senhas de exemplo em produção. A API legada deve permanecer acessível apenas em ambiente controlado até ser revisada para uso multiusuário.

### Instalação no Windows

O repositório inclui o fluxo de build de **Genesis.exe** em `.github/workflows/genesis-windows-build.yml`. O instalador `installation/Instalar-Iris.ps1` exige que o executável e seus arquivos internos já estejam extraídos. A opção de iniciar com o Windows é **voluntária**. O repositório-fonte, sozinho, não contém um `Genesis.exe` pronto.

## O que existe no código

| Área | Implementação | Situação |
| --- | --- | --- |
| Conversação | Runtime Python, FastAPI e roteador de inferência local | Integração existente; requer modelo/configuração adequados |
| Consultas com ferramentas | Documentos com fontes, grafo de código, impacto e web opcional no ciclo do modelo local | Use `consultar:` na conversa; exige modelo com suporte a ferramentas |
| Memória | Episódica, semântica, procedural e estado SQLite cifrado por instância | Testes automatizados |
| Planejamento e segurança | Fila de tarefas, validação, auditoria e permissões | Em desenvolvimento |
| Interface | Cliente desktop PySide6, avatar e mascote Íris | Requer validação visual em Windows físico |
| Malha da **Íris Original** | Inventário de nós, autorização, heartbeat, roteamento e modos Integrado/Visita | Fundação experimental |
| Replicação da **Íris Original** | Cópias AES-GCM de estado, controle de revisão e checkpoints cognitivos | Testes HTTP entre processos; **não** consenso entre PCs |
| Computação da **Íris Original** | Broker e worker para operações fechadas e tarefas de inferência local | Testado com modelos simulados; modelo real depende de provisionamento |
| Recuperação | Persistência, reentrada de nós e fencing de escritor SQLite | Testes locais; **não** failover universal |

### Exclusividade da Íris Original

A identidade **`iris-original`** é a **única** autorizada a parear e integrar dispositivos, replicar estado, distribuir tarefas cognitivas entre aparelhos e utilizar a infraestrutura experimental de continuidade. Essa restrição é aplicada no backend pela capacidade `device.local`, pelo papel da instância e pela autenticação dos nós.

Uma **Íris Residente** mantém seus recursos locais autorizados, como conversar e armazenar sua memória privada, mas **não recebe** a malha nem a replicação. Uma **Delegada** não consegue obter tais privilégios. Snapshots de permissões antigas são migrados para retirar a capacidade proibida.

**Não distribua** os segredos, os tokens de nós ou os componentes privados da Original em versões comerciais. A aplicação antiga baseada em `JARVIS_TOKEN` ainda não deve ser considerada uma plataforma SaaS multiusuário segura.

### Dispositivos sem aplicativos

Uma TV, um roteador, um switch ou um aparelho IoT **não precisa necessariamente executar a Íris**. A integração futura deverá aproveitar protocolos e interfaces autorizados que o equipamento já oferece, por meio de adaptadores. Isso não significa que uma TV execute um modelo de IA ou que qualquer roteador permita controle externo. Não há descoberta invasiva, instalação silenciosa nem desbloqueio de dispositivos.

## Testes

```bash
python -m pip install pytest
python -m pytest tests/ -q
```

O fluxo principal de testes é `.github/workflows/tests.yml`. Há testes separados de memória cifrada, isolamento de instâncias, sincronização, HTTP entre processos, recuperação e interface. **Testes com processos em loopback ou modelos falsos não substituem testes em dois computadores físicos com um LLM instalado.**

## Estrutura do repositório

| Diretório | Responsabilidade |
| --- | --- |
| `runtime/` | Ciclo de execução, inferência, servidor e orquestração da Íris |
| `memory_system/` | Memórias e armazenamento cifrado |
| `security/` | Políticas, validações, autenticação e proteção |
| `device/` | Perfil de dispositivos, malha, replicação e tarefas |
| `interface/` | API, dashboard, aplicativo e avatar |
| `executive_planner/`, `intent_layer/` | Tarefas, metas e planejamento |
| `learning/`, `workers/` | Capacidades auxiliares e execução por domínio |
| `installation/`, `service/` | Instalação e serviço Windows |
| `tests/` | Regressão automatizada |
| `docs/` | Guias técnicos e histórico mantido |

### Documentação técnica

- [Arquitetura](docs/referencia/ARCHITECTURE.md)
- [API](docs/referencia/API_PTBR.md)
- [Inferência](docs/referencia/INFERENCE_STACK_PTBR.md)
- [Consultas com ferramentas](docs/referencia/ESSENTIAL_TOOLS_PTBR.md)
- [Memória](docs/referencia/MEMORY_STACK_PTBR.md)
- [Interface da Íris](docs/guias/IRIS_INTERFACE_PTBR.md)
- [Deploy](docs/referencia/DEPLOY_PTBR.md)
- [Histórico de mudanças](docs/referencia/CHANGELOG.md)

Os relatórios históricos gerados durante ciclos antigos não fazem parte da documentação operacional vigente. O histórico de commits preserva as versões removidas na limpeza do repositório.

## Limites e próximos marcos

Ainda é necessário comprovar: funcionamento com um **modelo local real**, pareamento físico consentido, sincronização entre **dois computadores independentes**, recuperação do núcleo cognitivo após falha de um deles, interface e voz no Windows, segurança do pacote comercial e adaptadores específicos para equipamentos externos.

**Fluxo de trabalho:** desenvolver em branch isolada → testar → revisar → integrar em `dev`. `validado`, `staging` e **produção** só devem receber mudanças após homologação explícita. Não confundir metas de arquitetura com funcionalidades já entregues.
