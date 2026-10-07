# Ponto 2 — Stack de Voz Local do JARVIS

**Status:** implementado em `dev`, dependencias pesadas opcionais  
**Objetivo:** voz local real, pt-BR, modular, mensuravel e adequada a hardware limitado.

## Arquitetura

```text
Microfone real (sounddevice)
        |
        v
captura PCM 16 kHz
        |
        +--> wake word opcional (openWakeWord)
        |
        v
enhancement opcional (DeepFilterNet)
        |
        v
STT (faster-whisper)
        |
        +--> Silero VAD integrado
        |
        v
texto / planner / resposta
        |
        v
TTS leve (Kokoro ONNX pt-BR)
        |
        v
audio local
```

## Decisoes

### STT
**faster-whisper** foi adotado como backend principal desta fase porque:
- usa CTranslate2;
- suporta CPU INT8;
- possui Silero VAD integrado;
- permite trocar o tamanho do modelo sem trocar a arquitetura.

Padrao atual:
- modelo: `small`;
- device: `cpu`;
- compute: `int8`;
- idioma: `pt`;
- VAD: ligado;
- download automatico: desligado.

O modelo pode ser alterado por ambiente e devera ser benchmarkado no hardware real.

### TTS
O backend leve e **Kokoro ONNX**:
- modelo pequeno em relacao a TTS grandes;
- ONNX;
- suporte pt-BR;
- vozes portugues brasileiro como `pm_alex` e `pf_dora`;
- arquivos de modelo precisam ser configurados localmente;
- nao existe download silencioso no runtime.

O TTS nativo do sistema continua como fallback.

### Wake word
**openWakeWord** e suportado de forma opcional. O runtime exige um arquivo de modelo local e retorna score/threshold reais. Nenhum wake word e declarado detectado sem inferencia.

### Enhancement
**DeepFilterNet** e opcional. Pode ser carregado pelo pacote Python ou, preferencialmente, por CLI/ambiente isolado. Isso evita acoplar conflitos de dependencias ao runtime principal.

### Microfone
`AudioProcessingEngine` so declara `gravando` quando um `sounddevice.InputStream` real abriu com sucesso.

Se nao houver pacote ou dispositivo:
- status nao vira sucesso;
- nenhum WAV artificial e gerado;
- nenhuma captura inexistente e apresentada como real.

## Integridade das metricas

A implementacao anterior estimava "melhoria de SNR" usando uma formula fixa. Isso foi removido.

O fallback DSP agora:
- executa noise gate real;
- mede apenas mudanca RMS;
- retorna `snr_improvement_db = null` porque nao existe referencia limpa suficiente para calcular SNR de forma honesta.

## Instalacao

```powershell
pip install -r requirements-voice.txt
```

Os pesos Kokoro devem ser baixados/configurados fora do runtime:

```env
JARVIS_VOICE_ADVANCED_ENABLED=true
JARVIS_KOKORO_MODEL_PATH=C:\modelos\kokoro-v1.0.int8.onnx
JARVIS_KOKORO_VOICES_PATH=C:\modelos\voices-v1.0.bin
```

Para permitir que faster-whisper baixe um modelo quando ainda nao existe cache:

```env
JARVIS_VOICE_ALLOW_MODEL_DOWNLOAD=true
```

Depois do primeiro provisionamento, recomenda-se voltar a `false` para evitar rede implicita no runtime.

## DeepFilterNet isolado

Quando DeepFilterNet estiver em outro venv/ambiente:

```env
JARVIS_AUDIO_ENHANCEMENT_ENABLED=true
JARVIS_DEEPFILTER_COMMAND=C:\caminho\venv-deepfilter\Scripts\deepFilter.exe
```

## Configuracao completa

Consulte `.env.example`.

## Futuros challengers

Nao foram hard-coded como vencedores:
- Qwen3-TTS 0.6B/1.7B: candidato de maior qualidade/expressividade, mais pesado;
- Parakeet multilingual: candidato STT para benchmark;
- outros TTS pt-BR futuros.

Esses candidatos devem vencer o stack atual no JARVIS Experimental Twin antes de substituir o backend principal.

## Regra operacional

A voz e uma capacidade substituivel. O JARVIS nao depende da identidade de um modelo de STT/TTS especifico.
