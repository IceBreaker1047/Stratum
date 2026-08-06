# Stratum — PDF Parsing Pipeline

Stratum is a PDF parsing pipeline that extracts structured, semantically chunked content from complex documents and prepares it for downstream retrieval or embedding. The current pipeline is file-based and runs end to end from a local script.

---

## RAG Score

Every chunk in the final JSON includes a `rag_score` (0.0–1.0) and a `rag_metrics` breakdown. This score is intended as a pre-indexing quality signal — chunks with low scores may be short, fragmented, or content-sparse.

| Field | Weight | What it measures |
|---|---|---|
| `integrity` | 40% | A lightweight text-length heuristic used to down-weight very short chunks |
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

> **Note:** The pipeline only depends on the parsing and scoring code in `Parser/`; there is no separate image-captioning model download in the current version.

---

## Running the Pipeline

Run the main pipeline script on the bundled sample PDF:

```bash
python Parser/main.py
```

This runs `process_pdf_to_database()` and writes `final_database_chunks.json` by default.

### Pipeline Stages

1. `extract_without_bleeds()` removes repeated headers, footers, and page artifacts.
2. `construct_semantic_tree()` builds a hierarchical tree of headings, paragraphs, tables, and images.
3. `flatten_tree_to_chunks()` converts the tree into linear chunks while preserving heading context.
4. `process_chunks_validation()` adds `rag_score` and `rag_metrics` to each chunk.

### Output Shape

The final JSON contains a list of chunks with fields such as:

- `type`
- `h1_context`, `h2_context`, `h3_context`
- `content`
- `html` and `table_data` for table chunks
- `base64_image` for image chunks when available
- `rag_score`
- `rag_metrics`

The pipeline no longer emits `bboxes` or `page`, and chunk `content` is normalized so it does not carry embedded newline markers.

---

## Module Reference

| File | Responsibility |
|---|---|
| `Parser/main.py` | Top-level `process_pdf_to_database()` orchestrator and JSON writer |
| `Parser/bleeder.py` | `extract_without_bleeds()` for layout extraction and bleed filtering |
| `Parser/table.py` | Table extraction and structured row parsing |
| `Parser/tree.py` | `construct_semantic_tree()` and `flatten_tree_to_chunks()` |
| `Parser/validation.py` | `process_chunks_validation()` and RAG scoring helpers |

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

**Image handling**

Image chunks are preserved with their description text and any available `base64_image` payload. The pipeline does not attach generated captions or extra image-model metadata.

**Chunk normalization**

The flattening step normalizes chunk text so the final output stays single-line and consistent. This keeps the serialized JSON compact and avoids embedding newline markers in the stored content.

---

## License

MIT