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
