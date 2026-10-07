# Ponto 4 — Documentos e Ingestão Estruturada

**Status:** implementação em `dev`  
**Objetivo:** substituir extração binária improvisada por parsing real, preservar o conteúdo integral e preparar documentos para memória/RAG sem inventar texto.

## Arquitetura

```text
arquivo
  |
  +--> TXT/código/JSON/CSV -> parser nativo leve
  |
  +--> PDF/DOCX/XLSX/PPTX/EPUB/HTML/... -> Docling
  |                                         |
  |                                         +--> Markdown
  |                                         +--> texto
  |                                         +--> estrutura
  |                                         +--> tabelas
  |
  v
conteúdo verificável
  |
  +--> SHA-256 da fonte
  +--> .md auditável
  +--> manifesto JSON
  +--> chunks persistentes SQLite
  +--> resumo/catalogação existente
```

## 1. Parser principal: Docling

Docling foi escolhido como backend estrutural principal porque:
- é open source sob licença MIT;
- roda em Windows, Linux e macOS;
- possui parser unificado para múltiplos formatos;
- suporta PDF, DOCX, XLSX, PPTX, formatos Office legados, EPUB, HTML, Markdown, CSV, imagens e outros formatos;
- exporta Markdown, JSON, texto e outras representações;
- possui estrutura de tabelas e OCR para documentos que exigem percepção visual;
- pode operar completamente offline quando os artefatos de modelos são pré-provisionados.

Referências primárias:
- https://github.com/docling-project/docling
- https://github.com/docling-project/docling/blob/main/docs/usage/supported_formats.md
- https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md

## 2. Política local-first

O JARVIS não permite downloads silenciosos por padrão:

```env
JARVIS_DOCLING_ALLOW_MODEL_DOWNLOAD=false
JARVIS_DOCLING_ENABLE_REMOTE_SERVICES=false
```

Documentos Office como DOCX/PPTX/XLSX podem ser processados sem os pesos do pipeline de PDF.

Para PDF offline, os modelos devem ser baixados previamente:

```powershell
docling-tools models download --output-dir C:\modelos\docling
```

Depois:

```env
JARVIS_DOCUMENT_PARSER_ENABLED=true
JARVIS_DOCLING_ARTIFACTS_PATH=C:\modelos\docling
```

O adapter passa `artifacts_path` ao pipeline de PDF e mantém serviços remotos desligados.

## 3. Preservação integral

Antes deste ponto, o fluxo era:

```text
documento -> texto -> primeiras 5 linhas -> SQLite
```

Mesmo que o parser fosse perfeito, quase todo o documento desapareceria.

Agora existem duas camadas:

### Catálogo/resumo
A tabela `knowledge_items` continua servindo para catálogo e resumo compacto.

### Conteúdo completo
A nova tabela `document_chunks` preserva:
- `item_id`;
- índice do chunk;
- conteúdo;
- tamanho;
- caminho da fonte;
- SHA-256;
- momento da ingestão.

Isso permite recuperar uma frase que aparece no final de um documento sem depender do resumo.

## 4. Artefatos auditáveis

Cada ingestão bem-sucedida gera em `data/knowledge_base/documents/`:

- `<arquivo>_<hash>.md` — representação textual/Markdown usada pelo JARVIS;
- `<arquivo>_<hash>.json` — manifesto com parser, hash, tamanho, chunks, tabelas e estado de truncamento.

O arquivo binário original não é duplicado automaticamente.

## 5. Chunking

O ponto 4 adiciona chunking determinístico e leve:
- padrão: 4000 caracteres;
- overlap: 400 caracteres;
- preserva parágrafos quando possível;
- não exige tokenizer/modelo residente.

Configuração:

```env
JARVIS_DOCUMENT_CHUNK_CHARS=4000
JARVIS_DOCUMENT_CHUNK_OVERLAP_CHARS=400
```

No futuro, o Twin pode comparar esse chunker contra chunkers semânticos/híbridos do Docling e do sistema de embeddings.

## 6. Integridade epistemológica

A implementação antiga fazia, para PDF/EPUB/DOCX:

```text
arquivo binário -> regex de bytes imprimíveis -> "texto extraído"
```

E, quando tudo falhava, podia até retornar uma frase genérica como se conteúdo tivesse sido extraído.

Isso foi removido.

Contrato atual:

```text
parser executou e produziu conteúdo -> sucesso
parser ausente -> indisponível
parser falhou -> erro
formato desconhecido/binário -> rejeitado explicitamente
```

Nunca existe fallback para strings arbitrárias de bytes.

## 7. Parsers nativos

Formatos simples não precisam pagar o custo do Docling:
- TXT/Markdown/código: UTF-8 estrito;
- JSON: parser JSON real;
- CSV: parser CSV real.

UTF-8 inválido não é silenciosamente destruído com `errors=ignore`.

## 8. Dependências

```powershell
pip install -r requirements-documents.txt
```

O pacote fica fora de `requirements.txt` para que o runtime principal continue leve.

## 9. Relação com o ponto 3

Imagem/documento visual simples:
- PP-OCRv6 pode ler texto.

Documento estrutural:
- Docling entende organização, páginas e tabelas.

Documento visual extremamente difícil:
- PaddleOCR-VL continua disponível sob demanda.

Essas capacidades são complementares, não duplicações.

## 10. Challenger

Marker continua como challenger para documentos difíceis e conversão para Markdown, mas não entra no core neste ponto. Ele deverá vencer o Docling em corpus real do JARVIS antes de qualquer substituição.

## 11. Estado de validação

O código do adapter, fallback, chunking, persistência e integridade é coberto pela suíte automatizada.

A inferência/parsing com modelos Docling reais depende do provisionamento opcional e será medida no hardware alvo antes de ser classificada como backend operacional.
