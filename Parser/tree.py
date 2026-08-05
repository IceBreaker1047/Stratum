from collections import Counter


def format_bbox(bbox_tuple, page_number):
    # Turn a rectangle into a simple dictionary for the tree.
    if not bbox_tuple or len(bbox_tuple) < 4:
        return None

    return {
        "page": page_number,
        "x": round(bbox_tuple[0], 2),
        "y": round(bbox_tuple[1], 2),
        "w": round(bbox_tuple[2] - bbox_tuple[0], 2),
        "h": round(bbox_tuple[3] - bbox_tuple[1], 2),
    }


def construct_semantic_tree(document_elements):
    # Build a simple tree of headings and paragraphs.
    text_elements = [el for el in document_elements if not el.get("is_table") and not el.get("is_image")]

    if not text_elements:
        baseline_size = 0
    else:
        sizes = [el.get("size", 0) for el in text_elements]
        size_counts = Counter(sizes)
        baseline_size = size_counts.most_common(1)[0][0]

    root = {"type": "root", "children": []}
    stack = [(0, root)]

    for block in document_elements:
        bbox_dict = format_bbox(block.get("bbox"), block.get("page_number", 0))
        text = block.get("text", "").strip()

        if not text:
            continue

        # Save tables and images as leaf nodes.
        if block.get("is_image") or block.get("is_table"):
            node_type = "image" if block.get("is_image") else "table"
            leaf = {"type": node_type, "bboxes": [bbox_dict] if bbox_dict else []}

            if node_type == "image":
                leaf["description"] = block.get("text", "[IMAGE PENDING]")
                if "base64_image" in block:
                    leaf["base64_image"] = block["base64_image"]
            else:
                leaf["html"] = block.get("html", "")
                leaf["table_data"] = block.get("structured_rows", [])

            stack[-1][1]["children"].append(leaf)
            continue

        # Use font size to decide if a block is a heading.
        size = block.get("size", 0)
        heading_level = 0

        if baseline_size > 0 and size > baseline_size:
            if size >= baseline_size + 1.5:
                heading_level = 1
            elif size >= baseline_size + 0.5:
                heading_level = 2

        if heading_level > 0:
            new_node = {
                "type": "heading",
                "level": heading_level,
                "text": text,
                "bboxes": [bbox_dict] if bbox_dict else [],
                "children": [],
            }

            while stack and stack[-1][0] >= heading_level:
                stack.pop()

            stack[-1][1]["children"].append(new_node)
            stack.append((heading_level, new_node))
            continue

        # Everything else is a simple paragraph.
        leaf = {"type": "paragraph", "text": text, "bboxes": [bbox_dict] if bbox_dict else []}
        stack[-1][1]["children"].append(leaf)

    return root


def compress_bboxes(bboxes):
    # Merge nearby boxes so chunk metadata stays short.
    if not bboxes:
        return []

    pages = {}
    for box in bboxes:
        page = box.get("page")
        if page not in pages:
            pages[page] = []
        pages[page].append(box)

    compressed = []

    for page in sorted(pages.keys(), key=lambda x: (x if x is not None else -1)):
        page_boxes = pages[page]
        if not page_boxes:
            continue

        page_boxes.sort(key=lambda b: (b["y"], b["x"]))
        current_box = page_boxes[0].copy()

        for i in range(1, len(page_boxes)):
            box = page_boxes[i]
            vertical_gap = box["y"] - (current_box["y"] + current_box["h"])
            curr_right = current_box["x"] + current_box["w"]
            box_right = box["x"] + box["w"]
            is_aligned = max(current_box["x"], box["x"]) < min(curr_right, box_right) + 20

            if vertical_gap < 15 and is_aligned:
                new_x = min(current_box["x"], box["x"])
                new_y = min(current_box["y"], box["y"])
                new_w = max(curr_right, box_right) - new_x
                new_h = max(current_box["y"] + current_box["h"], box["y"] + box["h"]) - new_y

                current_box["x"] = round(new_x, 2)
                current_box["y"] = round(new_y, 2)
                current_box["w"] = round(new_w, 2)
                current_box["h"] = round(new_h, 2)
            else:
                compressed.append(current_box)
                current_box = box.copy()

        compressed.append(current_box)

    return compressed


def flatten_tree_to_chunks(node, context_dict=None, current_chunk=None, chunks_list=None, target_size=800, max_chars=1400):
    # Walk the tree and make chunks while keeping heading context.
    if context_dict is None:
        context_dict = {}
    if chunks_list is None:
        chunks_list = []

    node_type = node.get("type")

    if node_type == "heading":
        level = node.get("level", 1)
        keys_to_delete = [k for k in context_dict.keys() if k.startswith("h") and int(k[1]) >= level]
        for k in keys_to_delete:
            del context_dict[k]
        context_dict[f"h{level}_context"] = node.get("text", "")

    def finalize_chunk(chunk):
        # Add the current heading text to the chunk content.
        if not chunk or not chunk.get("content", "").strip():
            return

        ctx_list = [context_dict[f"h{i}_context"] for i in range(1, 4) if f"h{i}_context" in context_dict]
        prefix = f"[{' > '.join(ctx_list)}] " if ctx_list else ""

        if not chunk["content"].startswith("["):
            chunk["content"] = prefix + chunk["content"]

        chunk["bboxes"] = compress_bboxes(chunk["bboxes"])
        chunks_list.append(chunk)

    if node_type == "heading":
        finalize_chunk(current_chunk)
        current_chunk = {
            "type": "heading",
            **context_dict,
            "content": f"# {node.get('text', '')}\n\n",
            "bboxes": node.get("bboxes", []),
        }

    elif node_type == "paragraph":
        text = node.get("text", "")
        if not current_chunk or current_chunk["type"] != "paragraph" or len(current_chunk["content"]) > target_size:
            finalize_chunk(current_chunk)
            current_chunk = {
                "type": "paragraph",
                **context_dict,
                "content": text + "\n\n",
                "bboxes": node.get("bboxes", []),
            }
        else:
            current_chunk["content"] += text + "\n\n"
            current_chunk["bboxes"].extend(node.get("bboxes", []))

    elif node_type == "table":
        finalize_chunk(current_chunk)
        chunks_list.append({
            "type": "table",
            **context_dict,
            "content": node.get("html", ""),
            "bboxes": compress_bboxes(node.get("bboxes", [])),
        })
        current_chunk = None

    elif node_type == "image":
        finalize_chunk(current_chunk)
        img_chunk = {
            "type": "image",
            **context_dict,
            "content": f"Image Description: {node.get('description', '')}",
            "bboxes": compress_bboxes(node.get("bboxes", [])),
        }

        if "base64_image" in node:
            img_chunk["base64_image"] = node["base64_image"]

        chunks_list.append(img_chunk)
        current_chunk = None

    for child in node.get("children", []):
        current_chunk = flatten_tree_to_chunks(child, context_dict.copy(), current_chunk, chunks_list, target_size, max_chars)

    if node_type == "root":
        finalize_chunk(current_chunk)
        return chunks_list

    return current_chunk