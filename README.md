# Stratum — PDF Parsing API

Stratum is a high-fidelity PDF parsing API designed for ML engineers building RAG pipelines. It extracts structured, semantically-chunked content from complex documents — including multi-column layouts, tables, images, and nested headings — and returns clean, context-aware chunks ready for vector embedding.

---

## Features

- **Layout-aware extraction** — Detects single vs. multi-column layouts and sorts elements accordingly
- **Bleed/header filtering** — Automatically detects and strips repeated headers, footers, and page numbers across the document
- **Table extraction** — Parses tables with rowspan/colspan support; outputs HTML, structured JSON rows, and Markdown
- **Image passthrough** — Captures image bytes per block for downstream multimodal processing
- **Hierarchical chunking** — Two chunking strategies available: flat Markdown chunking and semantic tree construction
- **Context injection** — Every chunk carries `h1_context` / `h2_context` so retrievers know where in the document a chunk came from
- **Unified chunk schema** — All chunk types (text, table, image, caption) share the same output fields
- **Configurable overlap** — Sliding overlap between text chunks with heading-safe carry-over
- **REST API** — FastAPI server with a single `/parse-pdf` endpoint

---

## Architecture

```
PDF File
   │
   ▼
extract_without_bleeds()       # pymupdf — extracts text, images, tables; strips repeated margin content
   │
   ▼
get_page_elements()            # Per-page: detects tables, images, text lines; applies bold/italic/superscript markers
   │
   ▼
   ├── extract_markdown()      # Flat pipeline: maps font sizes → heading levels, produces Markdown blocks
   │       │
   │       └── markdown_chunk()   # Splits into chunks with overlap; flushes on heading boundaries
   │
   └── construct_semantic_tree()  # Tree pipeline: builds heading hierarchy, bonds captions to tables/images
           │
           └── flatten_tree_to_chunks()   # Merges adjacent nodes, injects context prefixes, enforces target size
```

Both pipelines produce the same output schema. The semantic tree pipeline is better suited for documents with consistent heading hierarchies (research papers, reports); the flat Markdown pipeline is more robust for noisy or irregular layouts (financial filings, scanned documents).

---

## API

### `GET /`

Health check.

```json
{ "status": "ok", "message": "PDF Parser API is running." }
```

### `POST /parse-pdf`

Upload a PDF file and receive structured chunks.

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
      "content": "Risk Factors - Macroeconomic Conditions\nThe Company's operations are exposed to...",
      "html": "",
      "table_data": [],
      "image_bytes": null,
      "base64_image": null,
      "bboxes": [
        { "page": 14, "x": 72.0, "y": 134.5, "w": 468.0, "h": 48.2 }
      ]
    },
    {
      "type": "table",
      "h1_context": "Financial Statements",
      "h2_context": "Consolidated Balance Sheet",
      "content": "Financial Statements - Consolidated Balance Sheet\n...",
      "html": "<table>...</table>",
      "table_data": [ [{ "text": "Assets", "rowspan": 1, "colspan": 2 }], ... ],
      "image_bytes": null,
      "base64_image": null,
      "bboxes": [{ "page": 38, "x": 72.0, "y": 210.0, "w": 468.0, "h": 320.0 }]
    }
  ]
}
```

**Chunk types:** `text`, `table`, `image`, `heading`, `caption`, `captioned_table`, `captioned_image`, `list`

---

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/your-org/stratum.git
cd stratum
pip install -r requirements.txt
```

**`requirements.txt`**
```
fastapi
uvicorn
pymupdf
torch
transformers
pillow
python-multipart
torchvision
```

---

## Running the Server

```bash
python api.py
```

The server starts at `http://0.0.0.0:7860`.

To run with hot reload during development:

```bash
uvicorn api:app --host 0.0.0.0 --port 7860 --reload
```

---

## Module Reference

| File | Responsibility |
|---|---|
| `api.py` | FastAPI app, `/parse-pdf` endpoint, temp file handling |
| `main.py` | Top-level `process_pdf_to_database()` orchestrator |
| `extractor.py` | `extract_without_bleeds()`, `get_page_elements()`, layout detection |
| `table.py` | `extract_tables()` — rowspan/colspan-aware table parser |
| `markdown.py` | `extract_markdown()`, `markdown_chunk()` — flat chunking pipeline |
| `tree.py` | `construct_semantic_tree()`, `flatten_tree_to_chunks()` — hierarchical pipeline |

---

## Design Notes

**Why two pipelines?**

The flat Markdown pipeline is fast and robust — it works well on documents where font-size hierarchy reliably encodes structure (most financial and technical PDFs). The semantic tree pipeline is better for academic or report-style documents with nested sections, where caption-to-figure bonding and hierarchical context matter more.

**Bleed detection**

Repeated elements (headers, footers, page numbers) are identified in a first pass by normalizing numbers (`Page 3 of 10` → `Page <NUM> of <NUM>`) and counting occurrences across pages. Anything appearing on more than 30% of pages in the top or bottom 12% of the page is blacklisted.

**Overlap design**

When a text chunk exceeds `max_chars`, the tail of the previous chunk is carried into the next with heading markers stripped. This prevents stale section context from bleeding across chunk boundaries in the vector store.

**Table cell handling**

`None` values in PyMuPDF's `table.extract()` output are used to detect merged cells. The extractor walks right (colspan) and down (rowspan) from each non-None cell, marking cells as covered, then emits the correct `rowspan`/`colspan` attributes in both HTML and structured JSON.

---

## License

MIT