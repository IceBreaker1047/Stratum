import pymupdf
import re
from table import extract_tables


def detect_multicolumn(doc):
    multicolumn_pages = 0

    for page_idx in range(min(5, len(doc))):
        page = doc[page_idx]
        blocks = [b for b in page.get_text("dict", sort=False)["blocks"] if b["type"] == 0]

        page_height = page.rect.height
        body_blocks = [
            b for b in blocks
            if b["bbox"][1] > page_height * 0.1 and b["bbox"][3] < page_height * 0.9
        ]

        is_multi = False
        for bi in range(len(body_blocks)):
            for bj in range(bi + 1, len(body_blocks)):
                b1 = body_blocks[bi]["bbox"]
                b2 = body_blocks[bj]["bbox"]

                y_overlap = max(0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
                if y_overlap > 15:
                    x_dist = max(b1[0], b2[0]) - min(b1[2], b2[2])
                    if x_dist > 10:
                        is_multi = True
                        break
            if is_multi:
                break

        if is_multi:
            multicolumn_pages += 1

    return multicolumn_pages > 0


def get_page_elements(page, is_multicolumn=False):
    elements = []
    page_width = page.rect.width

    tables = extract_tables(page, page_number=page.number)
    elements.extend(tables)

    page_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_IMAGES)

    for block in page_dict["blocks"]:
        if block["type"] == 1:
            img_bytes = block.get("image")
            if not img_bytes:
                try:
                    pix = page.get_pixmap(clip=block["bbox"], matrix=pymupdf.Matrix(2, 2))
                    img_bytes = pix.tobytes("png")
                except Exception:
                    img_bytes = None

            bbox = block["bbox"]
            elements.append({
                "is_image": True,
                "image_bytes": img_bytes,
                "text": "[IMAGE MULTIMODAL DESCRIPTION PENDING]",
                "size": 0,
                "is_bold": False,
                "is_upper": False,
                "bbox": (bbox[0], bbox[1], bbox[2], bbox[3]),
                "page_number": page.number,
                "page_width": page_width,
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
            })
            continue

        if block["type"] != 0:
            continue

        for line in block["lines"]:
            line_bbox = line["bbox"]
            is_inside_table = False

            for t in tables:
                t_box = t["bbox"]
                if (
                    line_bbox[0] >= t_box[0] - 5
                    and line_bbox[1] >= t_box[1] - 5
                    and line_bbox[2] <= t_box[2] + 5
                    and line_bbox[3] <= t_box[3] + 5
                ):
                    is_inside_table = True
                    break

            if is_inside_table:
                continue

            line_text = ""
            max_font_size = 0
            is_bold = False

            for span in line["spans"]:
                text = span["text"]
                if not text.strip():
                    line_text += text
                    continue

                font_size = round(span["size"], 1)
                if font_size > max_font_size:
                    max_font_size = font_size

                font_name = span.get("font", "").lower()
                span_is_bold = (span["flags"] & 16) or "bold" in font_name or "heavy" in font_name
                span_is_italic = (span["flags"] & 2) or "italic" in font_name or "oblique" in font_name
                span_is_super = (span["flags"] & 1) or "sup" in font_name

                if (
                    not span_is_super
                    and font_size < (max_font_size * 0.85)
                    and span["bbox"][1] < line["bbox"][1] + (line["bbox"][3] - line["bbox"][1]) * 0.3
                ):
                    span_is_super = True

                stripped_text = text.strip()
                prefix_spaces = text[: len(text) - len(text.lstrip())]
                suffix_spaces = text[len(text.rstrip()):]

                formatted_text = stripped_text
                if span_is_bold:
                    formatted_text = f"**{formatted_text}**"
                    is_bold = True
                if span_is_italic:
                    formatted_text = f"*{formatted_text}*"
                if span_is_super:
                    formatted_text = f"<sup>{formatted_text}</sup>"

                line_text += prefix_spaces + formatted_text + suffix_spaces

            line_text = line_text.strip()
            if line_text:
                elements.append({
                    "text": line_text,
                    "size": max_font_size,
                    "is_bold": is_bold,
                    "is_upper": line_text.isupper() and len(line_text) > 4,
                    "bbox": (line_bbox[0], line_bbox[1], line_bbox[2], line_bbox[3]),
                    "page_number": page.number,
                    "page_width": page_width,
                    "x0": line_bbox[0],
                    "y0": line_bbox[1],
                    "x1": line_bbox[2],
                    "y1": line_bbox[3],
                })

    if not is_multicolumn:
        elements.sort(key=lambda el: el.get("y0", el.get("bbox", [0, 0])[1]))
    else:
        page_midpoint = page.rect.width / 2

        def multi_col_sort_key(el):
            y0 = el.get("y0", el.get("bbox", [0, 0])[1])
            x0 = el.get("x0", el.get("bbox", [0, 0])[0])
            col_rank = 0 if x0 < page_midpoint - 20 else 1
            return (col_rank, y0)

        elements.sort(key=multi_col_sort_key)

    return elements


def extract_without_bleeds(pdf_path):
    doc = pymupdf.open(pdf_path)
    num_pages = len(doc)
    frequency_threshold = max(2, int(num_pages * 0.3))

    is_multicolumn = detect_multicolumn(doc)
    print(f"Layout detection: {'Multi-column' if is_multicolumn else 'Single-column'}")

    # Single-pass extraction: collect non-margin items immediately, buffer margin candidates
    margin_word_stats = {}
    margin_buffer = {}  # normalized_text -> list of (page_number, element)
    document_elements = []

    # Common page-number patterns to filter later
    page_pattern = re.compile(r"^(page\s*)?-?\s*\d+\s*([/of]\s*\d+)?\s*-?$", re.IGNORECASE)
    margin_cutoff = 0.15

    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page, is_multicolumn)

        for el in elements:
            # Tables and images are preserved immediately
            if el.get("is_table"):
                document_elements.append({
                    "is_table": True,
                    "text": el.get("text", ""),
                    "size": el.get("size", 0),
                    "bbox": el.get("bbox", (0, 0, 0, 0)),
                    "page_number": el.get("page_number", 0),
                    "is_bold": el.get("is_bold", False),
                    "is_upper": el.get("is_upper", False),
                })
                continue

            if el.get("is_image"):
                document_elements.append({
                    "is_image": True,
                    "image_bytes": el.get("image_bytes"),
                    "text": el.get("text", ""),
                    "size": el.get("size", 0),
                    "bbox": el.get("bbox", (0, 0, 0, 0)),
                    "page_number": el.get("page_number", 0),
                    "is_bold": el.get("is_bold", False),
                    "is_upper": el.get("is_upper", False),
                })
                continue

            # Text lines: decide whether to buffer (candidate bleed) or keep
            clean_text = el["text"].strip()
            normalized_text = re.sub(r"\d+", "<NUM>", clean_text)
            is_top_margin = el["y1"] < (page_height * margin_cutoff)
            is_bottom_margin = el["y0"] > (page_height * (1 - margin_cutoff))

            if is_top_margin or is_bottom_margin:
                # Tokenize into words, ignore short tokens
                words = [w.lower() for w in re.findall(r"\w+", normalized_text) if len(w) > 1]
                unique_words = set(words)
                for w in unique_words:
                    stats = margin_word_stats.setdefault(w, {"count": 0, "pages_seen": set()})
                    if page.number not in stats["pages_seen"]:
                        stats["count"] += 1
                        stats["pages_seen"].add(page.number)

                margin_buffer.setdefault(normalized_text, []).append((page.number, el))
            else:
                el_to_add = el.copy()
                el_to_add["text"] = clean_text
                document_elements.append(el_to_add)

    # Finalize bleed words and flush buffered margin items that are NOT bleeds
    bleed_words = {w for w, v in margin_word_stats.items() if v["count"] >= frequency_threshold}

    # Flush buffered margin candidates if they don't match bleed-word ratio or page-number patterns
    for normalized_text, occurrences in margin_buffer.items():
        words = [w.lower() for w in re.findall(r"\w+", normalized_text) if len(w) > 1]
        if not words:
            # nothing meaningful to keep
            continue
        bleed_ratio = sum(1 for w in words if w in bleed_words) / len(words)

        for _page_num, el in occurrences:
            clean_text = el["text"].strip()
            if page_pattern.match(clean_text):
                continue
            # Drop if majority of words are bleed words
            if bleed_ratio >= 0.5:
                continue
            el_to_add = el.copy()
            el_to_add["text"] = clean_text
            document_elements.append(el_to_add)

    print(
        f"Bleeder: Blacklisted {len(bleed_words)} words & filtered page numbers. "
        f"Extracted {len(document_elements)} clean blocks."
    )
    return document_elements
