# Ponto 3 — Visão e OCR do JARVIS

**Status:** implementação em `dev`  
**Objetivo:** substituir a pseudo-visão baseada em strings binárias por percepção visual real, modular e compatível com hardware limitado.

## Arquitetura

```text
imagem / print / foto
        |
        +--> metadados reais (Pillow)
        |
        +--> OCR leve: PP-OCRv6 small/tiny
        |
        +--> documento complexo: PaddleOCR-VL (sob demanda)
        |
        +--> visão geral: Moondream local/Station (opcional)
        |
        v
contexto visual auditável
```

## 1. OCR padrão: PP-OCRv6

O JARVIS usa PP-OCRv6 como backend de OCR primário.

Configuração padrão para PC limitado:
- dispositivo: CPU;
- tier: `small`;
- detector: `PP-OCRv6_small_det`;
- reconhecedor: `PP-OCRv6_small_rec`;
- download automático: desligado;
- score mínimo: 0.35.

O tier `tiny` pode ser selecionado para reduzir ainda mais custo:

```env
JARVIS_OCR_DETECTION_MODEL=PP-OCRv6_tiny_det
JARVIS_OCR_RECOGNITION_MODEL=PP-OCRv6_tiny_rec
```

O resultado guarda:
- texto;
- confiança real de cada linha;
- confiança média;
- caixas/posições;
- modelos usados.

Nenhuma confiança é inventada.

## 2. Documentos difíceis: PaddleOCR-VL

PaddleOCR-VL fica desligado por padrão por ser mais pesado.

Ele é destinado a:
- layouts complexos;
- tabelas;
- fórmulas;
- gráficos;
- documentos fotografados, tortos ou degradados.

O método `parse_complex_document()` é explícito e não é executado em toda imagem.

Por segurança operacional, o runtime não habilita download do modelo automaticamente.

## 3. Visão geral: Moondream

OCR responde "qual texto existe aqui?". Isso não responde:
- o que está acontecendo na imagem;
- que objetos aparecem;
- qual erro visual está na tela;
- qual botão ou componente existe;
- relações espaciais.

Por isso existe um backend separado de visão geral.

O JARVIS pode conectar-se a um endpoint local Moondream/Station:

```env
JARVIS_GENERAL_VISION_ENABLED=true
JARVIS_GENERAL_VISION_ENDPOINT=http://localhost:2020/v1
```

Essa camada é opcional e substituível. O JARVIS não depende de Moondream para funcionar.

## 4. Integridade epistemológica

A implementação antiga fazia:

```text
imagem -> bytes -> regex de caracteres imprimíveis -> "OCR"
```

Isso não era OCR.

Um PNG poderia conter strings em metadados, chunks ou dados comprimidos e o JARVIS poderia apresentá-las como texto visto na tela.

O novo contrato é:

```text
backend visual real executou -> resultado
backend ausente -> indisponível
backend falhou -> erro
```

Nunca existe fallback de "ler strings dos bytes".

## 5. Downloads e rede

Por padrão:

```env
JARVIS_OCR_ALLOW_MODEL_DOWNLOAD=false
JARVIS_DOCUMENT_VL_ALLOW_MODEL_DOWNLOAD=false
```

Para produção local, recomenda-se provisionar os pesos previamente e apontar:

```env
JARVIS_OCR_DETECTION_MODEL_DIR=C:\modelos\PP-OCRv6_small_det
JARVIS_OCR_RECOGNITION_MODEL_DIR=C:\modelos\PP-OCRv6_small_rec
```

Downloads podem ser liberados explicitamente durante o provisionamento.

## 6. Dependências

```powershell
pip install -r requirements-vision.txt
```

As dependências permanecem fora de `requirements.txt`, portanto o núcleo do Jarvis continua leve.

## 7. Seleção por custo

### Caminho normal
PP-OCRv6 small.

### Economia extrema
PP-OCRv6 tiny.

### Documento difícil
PaddleOCR-VL sob demanda.

### Cena / objetos / compreensão visual
Moondream ou futuro VLM que vencer o benchmark do Twin.

A estratégia evita carregar um VLM pesado para simplesmente ler um texto de tela.

## 8. Challenger futuro

A Constituição Tecnológica mantém espaço para:
- novos PaddleOCR-VL;
- HPD-Parsing;
- novos VLMs compactos;
- um modelo multimodal escolhido futuramente no benchmark de hardware.

Nenhum deles substitui o backend atual apenas por ser novo. Precisa vencer no JARVIS Experimental Twin.
