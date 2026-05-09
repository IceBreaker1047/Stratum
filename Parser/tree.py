import re

def is_list_item(text):
    # Check if the text is a list item using regex.
    text = text.strip()
    unordered_match = re.match(r'^[\-\*\•]\s+(.*)', text)
    if unordered_match:
        return True, unordered_match.group(1), "unordered"
        
    ordered_match = re.match(r'^(\d+)\.\s+(.*)', text)
    if ordered_match:
        return True, ordered_match.group(2), "ordered"
        
    return False, text, None

def get_markdown_heading_level(text):
    # Determine the heading level of a string (e.g., '### Text' -> 3).
    text = text.strip()
    match = re.match(r'^(#+)\s+', text)
    if match:
        return len(match.group(1))
    return 0

def format_bbox(bbox_tuple, page_number):
    # Convert (x0, y0, x1, y1) to dictionary format.
    if not bbox_tuple or len(bbox_tuple) < 4:
        return None
    return {
        "page": page_number,
        "x": round(bbox_tuple[0], 2),
        "y": round(bbox_tuple[1], 2),
        "w": round(bbox_tuple[2] - bbox_tuple[0], 2),
        "h": round(bbox_tuple[3] - bbox_tuple[1], 2)
    }

from collections import Counter

def construct_semantic_tree(document_elements: list) -> dict:
    # Construct a hierarchical semantic tree using spatial and font heuristics.
    # Pass 1: Global Statistics for Generalization
    text_elements = [el for el in document_elements if not el.get("is_table") and not el.get("is_image")]
    if not text_elements:
        baseline_size = 0
        large_fonts = []
    else:
        all_sizes = [el["size"] for el in text_elements]
        size_counts = Counter(all_sizes)
        baseline_size = size_counts.most_common(1)[0][0]
        # Unique sizes larger than baseline, sorted descending
        large_fonts = sorted([s for s in size_counts.keys() if s >= baseline_size + 0.5], reverse=True)

    root = {
        "type": "root",
        "children": []
    }
    
    active_stack = [(0, root)] 
    active_list_stack = []

    # Common structural heading patterns
    patterns = {
        1: [r'^[IVXLC]+\.\s+[A-Z]', r'^SECTION\s+[IVXLC]+', r'^\d+\.\s+[A-Z]'], # I. Title, SECTION I, 1. Title
        2: [r'^[A-Z]\.\s+[A-Z]', r'^\d+\.\d+\.?\s+', r'^Chapter\s+\d+'],        # A. Heading, 1.1 Heading
        3: [r'^\d+\)\s+', r'^[a-z]\)\s+', r'^\([a-z]\)\s+']                     # 1) Subheading, a) Subheading
    }

    for block in document_elements:
        bbox_dict = format_bbox(block.get("bbox"), block.get("page_number", 0))
        text = block.get("text", "").strip()
        if not text: continue
            
        # 1. Handle Non-Text
        if block.get("is_image") or block.get("is_table"):
            active_list_stack = []
            node_type = "image" if block.get("is_image") else "table"
            leaf = {
                "type": node_type,
                "bboxes": [bbox_dict] if bbox_dict else []
            }
            if node_type == "image":
                leaf["description"] = block.get("text", "[IMAGE PENDING]")
                if "base64_image" in block:
                    leaf["base64_image"] = block["base64_image"]
            else:
                leaf["html"] = block.get("html", "")
                leaf["table_data"] = block.get("structured_rows", [])
            
            active_stack[-1][1]["children"].append(leaf)
            continue
            
        # 2. Advanced Heading Detection
        size = block.get("size", 0)
        is_bold = block.get("is_bold", False)
        is_upper = block.get("is_upper", False)
        
        # Calculate centering
        is_centered = False
        if block.get("page_width"):
            mid_el = (block.get("x0", 0) + block.get("x1", 0)) / 2
            mid_page = block["page_width"] / 2
            if abs(mid_el - mid_page) < 25: # Centered within 25px margin
                is_centered = True

        heading_level = 0
        
        # Clean text for accurate length and pattern matching
        clean_text = re.sub(r'\*+|<[^>]+>', '', text).strip()
        
        # Short headings only; > 150 chars is likely a paragraph.
        if len(clean_text) < 150 and len(clean_text) > 2:
            # Ignore bold prefixes (e.g., "**Keywords:** ...")
            has_bold_prefix_only = text.startswith("**") and not text.endswith("**") and ("**" in text[2:])
            
            # Ignore common false positives (Keywords, Abstract)
            
            if not has_bold_prefix_only and not is_false_positive:
                # Heuristic A: Font Hierarchy
                if size in large_fonts:
                    # Map top sizes to levels 1 and 2
                    heading_level = 1 if size == large_fonts[0] else 2
                    
                # Heuristic B: Pattern Matching
                for level, regexes in patterns.items():
                    if any(re.match(p, clean_text) for p in regexes):
                        heading_level = max(heading_level, level)
                        break
                
                # Heuristic C: Centering + Bold (Common for Level 1)
                if is_centered and (size >= baseline_size) and (is_bold or is_upper):
                    heading_level = max(heading_level, 1 if size > baseline_size else 2)

                # Heuristic D: Baseline Bold (Level 3)
                if heading_level == 0 and size == baseline_size and is_bold:
                    # Standalone line check: short and no terminal punctuation
                    if len(clean_text) < 80 and not clean_text.endswith(('.', ':', ';', ',')):
                        # If it has multiple commas, it's likely a list/sentence rather than a heading
                        if clean_text.count(',') <= 1:
                            heading_level = 3
                
        if heading_level > 0:
            active_list_stack = []
            new_node = {
                "type": "heading",
                "level": heading_level,
                "text": text,
                "bboxes": [bbox_dict] if bbox_dict else [],
                "children": []
            }
            while active_stack and active_stack[-1][0] >= heading_level:
                active_stack.pop()
            active_stack[-1][1]["children"].append(new_node)
            active_stack.append((heading_level, new_node))
            continue
            
        # 4. Handle Lists
        is_list, clean_list_text, list_type = is_list_item(text)
        if is_list:
            x_coord = bbox_dict["x"] if bbox_dict else 0
            
            new_list_item = {
                "type": "list_item",
                "list_type": list_type,
                "text": clean_list_text,
                "bboxes": [bbox_dict] if bbox_dict else [],
                "children": []
            }
            
            while active_list_stack and active_list_stack[-1][0] > x_coord + 5:
                active_list_stack.pop()
                
            if active_list_stack and abs(active_list_stack[-1][0] - x_coord) <= 15:
                active_list_stack[-1][2].append(new_list_item)
            else:
                if active_list_stack:
                    active_list_stack[-1][1]["children"].append(new_list_item)
                    active_list_stack[-1][2].append(new_list_item)
                else:
                    active_stack[-1][1]["children"].append(new_list_item)
                    
                sibling_list = [new_list_item]
                active_list_stack.append((x_coord, new_list_item, sibling_list))
            continue
            
        # 5. Handle discrete paragraphs (NO MERGING!)
        active_list_stack = []
        node_type = "paragraph"
        # Detect if it's a caption (starts with Fig. or Table)
        if text.lower().startswith(("fig.", "figure", "table", "chart")):
            node_type = "caption"

        leaf = {
            "type": node_type,
            "text": text,
            "bboxes": [bbox_dict] if bbox_dict else []
        }
        active_stack[-1][1]["children"].append(leaf)

    return root

def compress_bboxes(bboxes):
    # Compress a list of bounding boxes by merging spatially adjacent ones.
    if not bboxes:
        return []
    
    # Group by page
    pages = {}
    for box in bboxes:
        p = box.get("page")
        if p not in pages:
            pages[p] = []
        pages[p].append(box)
    
    compressed = []
    for p in sorted(pages.keys(), key=lambda x: (x if x is not None else -1)):
        page_boxes = pages[p]
        if not page_boxes:
            continue
            
        # Sort by y then x
        page_boxes.sort(key=lambda b: (b["y"], b["x"]))
        
        current_macro = page_boxes[0].copy()
        
        for i in range(1, len(page_boxes)):
            box = page_boxes[i]
            
            # Merge if vertically adjacent within 15px
            vertical_gap = box["y"] - (current_macro["y"] + current_macro["h"])
            
            # Check for horizontal overlap or close proximity
            curr_right = current_macro["x"] + current_macro["w"]
            box_right = box["x"] + box["w"]
            
            is_horizontally_aligned = (
                max(current_macro["x"], box["x"]) < min(curr_right, box_right) + 20 
            )
            
            if vertical_gap < 15 and is_horizontally_aligned:
                # Merge
                new_x = min(current_macro["x"], box["x"])
                new_y = min(current_macro["y"], box["y"])
                new_w = max(curr_right, box_right) - new_x
                new_h = max(current_macro["y"] + current_macro["h"], box["y"] + box["h"]) - new_y
                
                current_macro["x"] = round(new_x, 2)
                current_macro["y"] = round(new_y, 2)
                current_macro["w"] = round(new_w, 2)
                current_macro["h"] = round(new_h, 2)
            else:
                compressed.append(current_macro)
                current_macro = box.copy()
        
        compressed.append(current_macro)
        
    return compressed

def flatten_tree_to_chunks(node, context_dict=None, current_chunk=None, chunks_list=None, target_size=800, max_chars=1400):
    # Flatten tree: merge adjacent same-type elements and inject context.
    if context_dict is None: context_dict = {}
    if chunks_list is None: chunks_list = []
        
    node_type = node.get("type")
    
    # 1. Update Hierarchical Context
    if node_type == "heading":
        level = node.get("level", 1)
        keys_to_delete = [k for k in context_dict.keys() if k.startswith("h") and int(k[1]) >= level]
        for k in keys_to_delete: del context_dict[k]
        context_dict[f"h{level}_context"] = node.get("text", "")

    # 2. Helper to finalize a chunk
    def finalize_chunk(chunk):
        if not chunk or not chunk.get("content", "").strip():
            return
        # Add context prefix to content if not already there
        ctx_list = [context_dict[f"h{i}_context"] for i in range(1, 4) if f"h{i}_context" in context_dict]
        prefix = f"[{' > '.join(ctx_list)}] " if ctx_list else ""
        if not chunk["content"].startswith("["):
            chunk["content"] = prefix + chunk["content"]
        
        chunk["bboxes"] = compress_bboxes(chunk["bboxes"])
        chunks_list.append(chunk)

    # 3. Process Node
    if node_type == "heading":
        finalize_chunk(current_chunk)
        # Headings are special: we start a chunk WITH the heading
        current_chunk = {
            "type": "heading",
            **context_dict,
            "content": f"# {node.get('text', '')}\n\n",
            "bboxes": node.get("bboxes", [])
        }
    
    elif node_type in ["paragraph", "list_item", "caption"]:
        text = node.get("text", "")
        if node_type == "list_item": text = f"* {text}"
        
        should_start_new = False
        if not current_chunk:
            should_start_new = True
        elif current_chunk["type"] == "caption":
            # Captions often have a second line (title). If the next element is a short paragraph, merge it.
            if node_type == "paragraph" and len(text) < 200:
                pass # Keep merging into caption
            elif node_type in ["table", "image"]:
                pass # Bonding will happen in the table/image blocks
            else:
                should_start_new = True
        elif current_chunk["type"] != node_type:
            should_start_new = True
        elif len(current_chunk["content"]) > target_size:
            should_start_new = True
            
        if should_start_new:
            finalize_chunk(current_chunk)
            current_chunk = {
                "type": node_type,
                **context_dict,
                "content": text + "\n\n",
                "bboxes": node.get("bboxes", [])
            }
        else:
            current_chunk["content"] += text + "\n\n"
            current_chunk["bboxes"].extend(node.get("bboxes", []))

    elif node_type == "table":
        # Caption bonding logic
        if current_chunk and current_chunk["type"] == "caption":
            current_chunk["type"] = "captioned_table"
            current_chunk["content"] += "\n" + node.get("html", "")
            current_chunk["bboxes"].extend(node.get("bboxes", []))
            finalize_chunk(current_chunk)
            current_chunk = None
        else:
            finalize_chunk(current_chunk)
            chunks_list.append({
                "type": "table",
                **context_dict,
                "content": node.get("html", ""),
                "bboxes": compress_bboxes(node.get("bboxes", []))
            })
            current_chunk = None

    elif node_type == "image":
        desc = f"Image Description: {node.get('description', '')}"
        # Caption bonding logic
        if current_chunk and current_chunk["type"] == "caption":
            current_chunk["type"] = "captioned_image"
            current_chunk["content"] += "\n" + desc
            current_chunk["bboxes"].extend(node.get("bboxes", []))
            if "base64_image" in node:
                current_chunk["base64_image"] = node["base64_image"]
            finalize_chunk(current_chunk)
            current_chunk = None
        else:
            finalize_chunk(current_chunk)
            img_chunk = {
                "type": "image",
                **context_dict,
                "content": desc,
                "bboxes": compress_bboxes(node.get("bboxes", []))
            }
            if "base64_image" in node:
                img_chunk["base64_image"] = node["base64_image"]
            chunks_list.append(img_chunk)
            current_chunk = None

    # 4. Recurse
    for child in node.get("children", []):
        current_chunk = flatten_tree_to_chunks(child, context_dict.copy(), current_chunk, chunks_list, target_size, max_chars)
        
    # 5. Root Cleanup
    if node_type == "root":
        finalize_chunk(current_chunk)
        return chunks_list
        
    return current_chunk
