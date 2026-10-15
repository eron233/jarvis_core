# Ponto 6 — Runtime de Inferência Local do JARVIS

**Status:** implementação em `dev`  
**Objetivo:** preparar o JARVIS para executar modelos locais de forma substituível, mensurável e segura, sem escolher prematuramente o modelo-base.

## Arquitetura

```text
Planner / subagente / capacidade
            |
            v
LocalInferenceRouter
     |              |
     v              v
 llama.cpp        Ollama
 /v1 OpenAI      /v1 OpenAI
 compatible      compatible
     |              |
     +-------+------+
             |
             v
 modelo local configurado
```

## 1. Decisão arquitetural

O modelo **não é o JARVIS**.

O JARVIS é:
- identidade constitucional;
- planner;
- memória;
- ferramentas;
- percepção;
- políticas;
- Twin;
- roteamento;
- interfaces;
- runtimes de inferência.

O modelo é um motor cognitivo substituível.

Por isso, esta etapa implementa o **runtime e o contrato**, não escolhe o modelo vencedor.

## 2. llama.cpp

`llama.cpp` é o runtime de baixo nível principal para hardware limitado.

Vantagens relevantes:
- C/C++;
- GGUF;
- quantização;
- CPU e múltiplos backends de aceleração;
- offload CPU/GPU;
- servidor local;
- API OpenAI-compatible;
- ampla portabilidade.

Exemplo de servidor:

```powershell
llama-server -m C:\modelos\modelo.gguf --host 127.0.0.1 --port 8080
```

O JARVIS aponta para:

```env
JARVIS_LLAMACPP_BASE_URL=http://127.0.0.1:8080/v1
```

Nenhum GGUF específico foi escolhido nesta fase.

## 3. Ollama

Ollama fica como segundo runtime local e camada conveniente de gerenciamento.

O servidor local expõe compatibilidade OpenAI em:

```text
http://localhost:11434/v1
```

Configuração:

```env
JARVIS_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
```

O JARVIS pode tentar:

```text
llamacpp -> ollama
```

ou alterar a ordem via:

```env
JARVIS_INFERENCE_PROVIDER_ORDER=ollama,llamacpp
```

## 4. Nenhum modelo hardcoded

Antes deste ponto, `runtime/corporate_agent_hierarchy.py` continha nomes como:

- `claude-3-5-haiku-local`;
- `claude-3-7-sonnet-supreme`;
- `security-checker-fast`;
- `coder-light-fast`.

Esses modelos não representavam runtimes reais provisionados.

Foram removidos.

Agora os subagentes pedem:
- tier: `light` ou `heavy`;
- capacidade: `general`, `reasoning`, `coding`, etc.

E o roteador resolve somente aliases realmente configurados.

## 5. Aliases

```env
JARVIS_MODEL_LIGHT=
JARVIS_MODEL_HEAVY=
JARVIS_MODEL_GENERAL=
JARVIS_MODEL_CODING=
JARVIS_MODEL_REASONING=
```

Eles ficam vazios até o benchmark no hardware do proprietário.

Se uma tarefa exigir modelo e nenhum alias estiver configurado:

```json
{
  "status": "indisponivel",
  "modelo": null
}
```

Nunca é escolhido um modelo fictício.

## 6. Resolução de modelo

Ordem:

```text
capacidade específica
      ↓
tier light/heavy
      ↓
general
      ↓
indisponível
```

Exemplo futuro:

```env
JARVIS_MODEL_LIGHT=modelo-pequeno-q4
JARVIS_MODEL_HEAVY=modelo-maior-q4
JARVIS_MODEL_CODING=modelo-coder-q4
```

Uma tarefa de código prefere `coding`; se esse alias não existir, usa o tier; depois `general`.

## 7. Fallback de runtime

O mesmo modelo pode ser tentado em mais de um servidor.

```text
llama.cpp falhou
      ↓
Ollama
      ↓
sucesso ou indisponível
```

Cada tentativa é registrada no resultado.

O JARVIS não mascara uma falha de backend.

## 8. Métricas

Cada inferência bem-sucedida registra:
- provider;
- modelo efetivo;
- finish reason;
- uso reportado pelo servidor;
- latência real medida;
- tokens/s estimados quando completion tokens estiver disponível;
- tool calls;
- ID da resposta.

Isso prepara o Experimental Twin para o benchmark de modelos.

## 9. Tool calling e structured output

O contrato passa adiante quando suportado pelo runtime/modelo:
- `tools`;
- `tool_choice`;
- `response_format`;
- parâmetros extras.

O suporte real depende do modelo/template/runtime.

A presença do campo no adapter não significa que todo modelo o suporta.

## 10. Segurança de endpoint

Por padrão, o motor aceita inferência apenas em:
- `localhost`;
- loopback IPv4/IPv6.

Um endpoint remoto é bloqueado.

```env
JARVIS_INFERENCE_ALLOW_REMOTE_ENDPOINTS=false
```

Isso impede que uma alteração de configuração redirecione silenciosamente prompts/contexto do JARVIS para uma máquina externa.

O opt-in remoto existe, mas deve ser decisão explícita.

## 11. API interna

Status:

```text
GET /api/inferencia/status
GET /api/inferencia/status?probe=true
```

O probe chama `/v1/models` dos runtimes configurados.

Inferência:

```text
POST /api/inferencia/chat
```

Corpo:

```json
[
  {"role": "system", "content": "..." },
  {"role": "user", "content": "..." }
]
```

Parâmetros opcionais:
- `tier`;
- `capacidade`;
- `provider`;
- `modelo`.

## 12. LiteLLM

LiteLLM continua candidato para o **próximo nível de gateway multi-provider**.

Ele não foi colocado entre o planner e os runtimes locais nesta fase porque:
- llama.cpp e Ollama já falam um contrato OpenAI-compatible;
- adicionar um proxy agora seria uma camada extra sem benefício obrigatório;
- LiteLLM passa a fazer mais sentido quando o JARVIS precisar rotear entre muitos provedores locais/remotos, aplicar quotas, políticas, observabilidade e failover mais amplo.

Portanto:

```text
Ponto 6 = runtime local
LiteLLM = camada de gateway futura/experimental
```

## 13. Escolha do modelo

Permanece **ADIADA**.

O benchmark futuro deverá medir no PC real:
- TTFT;
- tokens/s;
- RAM;
- VRAM;
- CPU/GPU;
- qualidade pt-BR;
- coding;
- reasoning;
- tool calling;
- structured output;
- aderência à Constituição;
- contexto;
- estabilidade;
- quantização.

O vencedor pode ser diferente por tier/capacidade.

Nada obriga o JARVIS a possuir apenas um modelo.

## 14. Fontes primárias

- https://github.com/ggml-org/llama.cpp
- https://github.com/ollama/ollama
- https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx
- https://github.com/BerriAI/litellm

## 15. Estado de validação

A suíte automatizada valida:
- configuração segura;
- ausência de modelo escolhido por default;
- endpoint remoto bloqueado;
- aliases capability/tier/general;
- fallback entre runtimes;
- runtime integrado ao JARVIS;
- hierarquia corporativa sem modelos fictícios.

A inferência com um modelo real depende do provisionamento no hardware alvo.


## 16. FreeLLMAPI como gateway **opt-in** (13/10/2026)

**Fonte:** https://github.com/tashfeenahmed/freellmapi
**Backend:** `runtime/freellmapi_backend.py`.
**Contrato:** endpoint OpenAI-compatible `/v1/chat/completions` e `/v1/models`, conforme FreeLLMAPI v0.13.x.

FreeLLMAPI e um roteador que roda localmente, mas **pode enviar prompts,
chaves e contexto a provedores externos**. Nao transforma servicos de nuvem
em inferencia offline. Tiers gratuitos sao volateis; `auto:cheap` nao
garante que nenhuma chave paga/customizada seja usada pelo gateway.

A integracao NUNCA instala FreeLLMAPI, cria contas, obtem chaves, altera
seu catalogo ou envia prompts na inicializacao do JARVIS.

### Configuracao consciente

```env
# Ative inferencia somente depois de instalar um modelo local.
JARVIS_INFERENCE_ENABLED=true
JARVIS_INFERENCE_PROVIDER_ORDER=llamacpp,ollama,freellmapi

# Modos diferentes: offline domina todas as outras permissoes.
JARVIS_INFERENCE_OFFLINE_MODE=false
JARVIS_FREELLMAPI_ENABLED=true
JARVIS_FREELLMAPI_BASE_URL=http://127.0.0.1:3001/v1
JARVIS_FREELLMAPI_API_KEY=chave-unificada-real-criada-no-roteador
JARVIS_FREELLMAPI_MODEL=auto:cheap
```

As configuracoes acima sao **exemplo de opt-in**, nao valores padrao.
Nao grave chaves reais no repositorio.

O modelo local ainda precisa ser escolhido no hardware alvo por
`JARVIS_MODEL_GENERAL` e/ou aliases light/heavy/coding/reasoning.
Sem modelo local, o JARVIS nao se torna offline so por adicionar FreeLLMAPI.

### Restricoes obrigatorias por requisicao

Mesmo com todas as variaveis configuradas, chamadas externas exigem
`allow_external=True` e `data_classification="public"`; na API:

```text
POST /api/inferencia/chat?provider=freellmapi&permitir_externo=true&classificacao=public&modelo=auto:cheap
```

O corpo continua sendo a lista JSON de mensagens original.
O endpoint `/api/inferencia/benchmark` aplica as mesmas restricoes.

**A classificacao public e afirmacao explicita do operador** e nao e
comprovada por um scanner de segredos; nao a utilize para anexar memoria
privada, credenciais, codigo proprietario, arquivos pessoais ou output
de ferramentas internas. Chamadas sem permissao, offline ou sem chave
retornam `bloqueado`/`indisponivel`, nunca sucesso inventado.
O servidor deve permanecer em loopback e com token de acesso.

`GET /api/inferencia/status?probe=true` so consulta modelos locais.
Consultar o catalogo do FreeLLMAPI exige o opt-in adicional
`consultar_externo=true`, alem de `JARVIS_FREELLMAPI_ENABLED=true` e
`JARVIS_INFERENCE_OFFLINE_MODE=false`.

O client FreeLLMAPI nao herda proxies do ambiente, recusa redirects,
endpoints nao-loopback, URLs com credenciais ou parametros, respostas
acima de 2 MiB e prompts HTTP acima de 512 KiB. Nao expõe chaves em
relatorios de status. Fallback automatico so envolve FreeLLMAPI se
explicitamente incluido em `JARVIS_INFERENCE_PROVIDER_ORDER`, e mesmo
assim depende da autorizacao por requisicao.

**Limite operacional:** o modo offline do JARVIS barra rotas remotas
reconhecidas e o FreeLLMAPI, mas nao consegue provar se algum daemon
local (por exemplo, Ollama com modelos cloud habilitados) encaminha
dados por conta propria. Offline verificavel requer modelos estritamente
locais e um teste de rede em ambiente real.

### Validacao

`tests/test_freellmapi_integration.py` cobre opt-in, status,
modo offline, fallback, autenticacao de dispositivo, respostas
incompatíveis, nao-redirect e protocolo HTTP real com **servidor de teste
local**, usando chave falsa. O teste nao valida cota real, disponibilidade
da nuvem, contrato de privacidade dos fornecedores, ausencia de cobranca
nem capacidade dos modelos comerciais.
