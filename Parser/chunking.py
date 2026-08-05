from collections import Counter
import re


def create_header_mapping(all_font_sizes: list) -> tuple[dict, float]:
    if not all_font_sizes:
        return {}, 0.0

    size_counts = Counter(all_font_sizes)
    baseline_size = size_counts.most_common(1)[0][0]

    larger_sizes = sorted(
        {size for size in all_font_sizes if size > baseline_size},
        reverse=True,
    )

    header_mapping = {}
    for rank, size in enumerate(larger_sizes):
        header_mapping[size] = "#" * min(rank + 1, 6)

    return header_mapping, baseline_size


def extract_markdown(document_elements: list) -> list:
    if not document_elements:
        return []

    # Fix: exclude images and tables from font-size corpus.
    all_font_sizes = [
        el["size"]
        for el in document_elements
        if not el.get("is_image") and not el.get("is_table") and el["size"] > 0
    ]
    header_mapping, baseline_size = create_header_mapping(all_font_sizes)

    markdown_blocks = []

    for element in document_elements:
        # Fix: handle images and tables separately.
        if element.get("is_image") or element.get("is_table"):
            markdown_blocks.append(element)
            continue

        size = element["size"]
        text = element["text"]
        is_bold = element.get("is_bold", False)
        is_upper = element.get("is_upper", False)

        base_block = {
            "type": "text",
            "bbox": element.get("bbox", (0, 0, 0, 0)),
            "page_number": element.get("page_number", 0),
        }

        if size in header_mapping:
            markdown_tag = header_mapping[size]
            base_block["text"] = f"{markdown_tag} {text}"
        elif size == baseline_size and (is_bold or is_upper):
            if len(text) > 80 or text.endswith((".", ":", ";", ",")):
                base_block["text"] = text
            elif is_bold and is_upper:
                base_block["text"] = f"# {text}"
            else:
                base_block["text"] = f"## {text}"
        else:
            base_block["text"] = text

        markdown_blocks.append(base_block)

    return markdown_blocks


def get_chunk_type(chunk_text: str) -> str:
    chunk_text = chunk_text.strip()
    if not chunk_text:
        return "text"

    lines = [l.strip() for l in chunk_text.split("\n") if l.strip()]
    if not lines:
        return "text"

    table_rows = [l for l in lines if "|" in l]
    if len(table_rows) >= 1 and chunk_text.count("|") >= 3:
        return "table"

    first_line_lower = lines[0].lower()
    if first_line_lower.startswith(("fig.", "figure", "table")):
        if len(chunk_text) < 400:
            return "caption"

    list_lines = [
        l for l in lines
        if l.startswith(("-", "*", "•")) or re.match(r"^\d+\.", l)
    ]
    if len(list_lines) >= 3 or (
        len(list_lines) > 0 and len(list_lines) >= len(lines) * 0.3
    ):
        return "list"

    if lines[0].startswith("#") and len(lines) <= 3:
        return "heading"

    return "text"

def markdown_chunk(markdown_blocks: list, max_chars: int, overlap_chars: int) -> list:
    chunks = []
    current_h1 = "Document Start"
    current_h2 = ""
    current_chunk_text = ""

    def flush_text_chunk():
        nonlocal current_chunk_text
        text = current_chunk_text.strip()
        if not text:
            return
        chunk = {
            "type": get_chunk_type(text),
            "h1_context": current_h1,
            "h2_context": current_h2,
            "content": f"{current_h1} - {current_h2}\n{text}",
        }
        chunks.append(chunk)
        current_chunk_text = ""

    for block in markdown_blocks:
        # Table processing
        if block.get("is_table"):
            flush_text_chunk()
            table_text = block.get("text", "")
            chunk = {
                "type": "table",
                "h1_context": current_h1,
                "h2_context": current_h2,
                "content": f"{current_h1} - {current_h2}\n{table_text}",
            }
            chunks.append(chunk)
            continue

        if block.get("is_image"):
            flush_text_chunk()
            img_text = block.get("text", "")
            chunk = {
                "type": "image",
                "h1_context": current_h1,
                "h2_context": current_h2,
                "content": f"{current_h1} - {current_h2}\n{img_text}",
            }
            if "image_bytes" in block:
                chunk["image_bytes"] = block.get("image_bytes")
            if "base64_image" in block:
                chunk["base64_image"] = block.get("base64_image")
            chunks.append(chunk)
            continue

        # Text / Heading processing
        para = block.get("text", "").strip()
        if not para:
            continue
        
        # Fix: headings update context but aren't written to body text.
        if para.startswith("# "):
            flush_text_chunk()          # section boundary → always flush first
            current_h1 = para[2:].strip()
            current_h2 = ""
            continue

        if para.startswith("## "):
            current_h2 = para[3:].strip()
            continue

        # Para content addition.
        current_chunk_text += f"{para}\n\n"

        if len(current_chunk_text) > max_chars:
            flush_text_chunk()

            # Fix: overlap text shouldn't contain heading markers.
            overlap_raw = current_chunk_text[-overlap_chars:] if current_chunk_text else ""
            # Trim to word boundary
            if " " in overlap_raw:
                overlap_raw = overlap_raw.split(" ", 1)[-1]
            # Strip any residual heading lines from the carry-over text
            overlap_lines = [
                l for l in overlap_raw.split("\n") if not l.strip().startswith("#")
            ]
            current_chunk_text = "..." + "\n".join(overlap_lines).lstrip("\n") + "\n\n"

    # Flush whatever remains
    flush_text_chunk()

    return chunks