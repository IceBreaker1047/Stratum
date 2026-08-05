# Stratum — PDF Parsing Pipeline

Stratum is a high-fidelity PDF parsing pipeline designed for ML engineers building RAG pipelines. It extracts structured, semantically-chunked content from complex documents — including multi-column layouts, tables, images, and nested headings — and returns clean, context-aware chunks ready for vector embedding.
---

```json
{ "status": "ok", "message": "PDF Parser API is running." }
```

### `POST /parse-pdf`

Upload a PDF and receive structured, scored chunks.

**Request:** `multipart/form-data` with a `file` field containing a `.pdf` file.

**Response:**

```json
{
  "filename": "apple_10k.pdf",
  "chunks_extracted": 312,
  "chunks": [
    {
      "type": "text",
      "h1_context": "Risk Factors",
      "h2_context": "Macroeconomic Conditions",
      "content": "[Risk Factors > Macroeconomic Conditions] The Company's operations are exposed to...",
      "html": "",
      "table_data": [],
      "image_bytes": null,
      "base64_image": null,
      "bboxes": [
        { "page": 14, "x": 72.0, "y": 134.5, "w": 468.0, "h": 48.2 }
      ],
      "rag_score": 0.742,
      "rag_metrics": {
        "score": 0.742,
        "integrity": 0.95,
        "density": 0.61
      }
    },
    {
      "type": "table",
      "h1_context": "Financial Statements",
      "h2_context": "Consolidated Balance Sheet",
      "content": "[Financial Statements > Consolidated Balance Sheet] ...",
      "html": "<table><tr><th>Assets</th>...</tr></table>",
      "table_data": [ [{ "text": "Assets", "rowspan": 1, "colspan": 2 }] ],
      "image_bytes": null,
      "base64_image": null,
      "bboxes": [{ "page": 38, "x": 72.0, "y": 210.0, "w": 468.0, "h": 320.0 }],
      "rag_score": 0.881,
      "rag_metrics": {
        "score": 0.881,
        "integrity": 1.0,
        "density": 0.80
      }
    }
  ]
}
```

**Chunk types:** `text`, `table`, `image`, `heading`, `caption`, `captioned_table`, `captioned_image`, `list_item`

---

## RAG Score

Every chunk in the response includes a `rag_score` (0.0–1.0) and a `rag_metrics` breakdown. This score is intended as a pre-indexing quality signal — chunks with low scores may be fragmented, spatially incoherent, or content-sparse.

| Field | Weight | What it measures |
|---|---|---|
| `integrity` | 40% | Spatial coherence of the chunk's bounding boxes — penalises bbox overlap and heavy fragmentation (< 30 chars/box) |
| `density` | 60% | Entity richness of the content — counts proper nouns, acronyms, and numeric values per 100 words, normalised against a baseline of 15 entities/100 words |

```
rag_score = (integrity × 0.4) + (density × 0.6)
```

A common use pattern is to filter out chunks below a threshold before sending to your vector store:

```python
good_chunks = [c for c in chunks if c["rag_score"] >= 0.4]
```

---

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/your-org/stratum.git
cd stratum
pip install -r Parser/requirements.txt
```

> **Note:** The image captioning model (`nlpconnect/vit-gpt2-image-captioning`) is downloaded automatically from Hugging Face on first run and cached locally. It runs on CPU if no GPU is available, which will be slower on documents with many images.

---

## Running the Pipeline

Run the main pipeline script on a sample PDF:

```bash
python Parser/main.py
```

This runs the `process_pdf_to_database()` pipeline and writes `final_database_chunks.json` by default.

---

## Module Reference

| File | Responsibility |
|---|---|
| `main.py` | Top-level `process_pdf_to_database()` orchestrator |
| `extractor.py` | `extract_without_bleeds()`, `get_page_elements()`, layout detection |
| `table.py` | `extract_tables()` — rowspan/colspan-aware table parser |
| `tree.py` | `construct_semantic_tree()`, `flatten_tree_to_chunks()` — semantic chunking pipeline |
| `captioner.py` | `ImageCaptioner` singleton — on-device ViT-GPT2 image captioning |
| `scorer.py` | `process_chunks_validation()`, `compute_rag_score()` — RAG quality scoring |

---

## Design Notes

**Bleed detection**

Repeated elements (headers, footers, page numbers) are identified in a first pass by normalizing all numbers to `<NUM>` tokens (`Page 3 of 10` → `Page <NUM> of <NUM>`) and counting occurrences across pages. Any normalized string appearing on more than 30% of pages within the top or bottom 12% of the page height is blacklisted and silently dropped in the second pass.

**Heading detection**

The semantic tree uses four layered heuristics to assign heading levels:

1. **Font hierarchy** — sizes larger than the document baseline are ranked and mapped to `h1`, `h2`, etc.
2. **Structural patterns** — regex matching for common patterns like `1.2 Heading`, `A. Section`, `SECTION IV`
3. **Centering + bold** — centered bold text at or above baseline is promoted to at least `h2`
4. **Baseline bold** — short, unpunctuated bold lines at body size are assigned `h3`

**Table cell merging**

`None` values in PyMuPDF's `table.extract()` output signal merged cells. The extractor walks right (colspan) and down (rowspan) from each non-`None` anchor cell, marks covered positions, and emits the correct `rowspan`/`colspan` attributes in both the HTML and structured JSON outputs.

**Image captioning**

`ImageCaptioner` is implemented as a singleton to avoid reloading the ViT-GPT2 weights on every request. The model runs inference at `float32` for broad hardware compatibility. Captions are capped at 20 tokens with beam search (`num_beams=4`). If the model fails to load or inference errors, a descriptive fallback string is returned rather than crashing the parse.

**Caption bonding**

When a `caption` node (text starting with `Fig.`, `Figure`, `Table`, or `Chart`) immediately precedes a `table` or `image` node in the tree, `flatten_tree_to_chunks` merges them into a single `captioned_table` or `captioned_image` chunk. This keeps the label and its content together in the vector store rather than splitting them into separate retrievable units.

---

## License

MIT