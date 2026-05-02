from collections import Counter
import pymupdf
import json
import re

# Assign the text # or ## according to the text size
def create_header_mapping(all_font_sizes: list) -> tuple[dict,float]:
    if not all_font_sizes:
        return {},0.0
    
    size_counts = Counter(all_font_sizes)
    baseline_size = size_counts.most_common(1)[0][0]

    larger_sizes = set([size for size in all_font_sizes if size>baseline_size])

    #Keep only the sizes that appear frequently to eliminate once appearing titles causing h1 context freeze
    valid_header_sizes = set()
    title_sizes = set()
    for size in larger_sizes:
        if size_counts[size]>2:
            valid_header_sizes.add(size)
        else:
            title_sizes.add(size)

    sorted_header_sizes = sorted(list(valid_header_sizes),reverse=True)

    header_mapping = {}
    for rank,size in enumerate(sorted_header_sizes):
        markdown_hashes = "#" * min(rank+1,6)
        header_mapping[size] = markdown_hashes

    sorted_title_sizes = sorted(list(title_sizes), reverse=True)
    if sorted_title_sizes:
        header_mapping[sorted_title_sizes[0]] = "#"

    return header_mapping, baseline_size

#Updates the context by looking at # and ##
def extract_markdown(document_elemts:list)->list:
    if not document_elemts:
        return []
    
    all_font_sizes = [el["size"] for el in document_elemts]
    header_mapping, baseline_size = create_header_mapping(all_font_sizes)

    markdown_blocks = []

    for element in document_elemts:
        if element.get("is_table"):
            markdown_blocks.append(element)
            continue
            
        size = element["size"]
        text = element["text"]

        is_bold = element.get("is_bold",False)
        is_upper = element.get("is_upper",False)
        
        base_block = {
            "type": "text",
            "bbox": element.get("bbox", (0,0,0,0)),
            "page_number": element.get("page_number", 0)
        }
        
        if size in header_mapping:
            markdown_tag = header_mapping[size]
            base_block["text"] = f"{markdown_tag} {text}"
            markdown_blocks.append(base_block)
        elif size == baseline_size and (is_bold or is_upper):
            if len(text) > 80 or text.endswith(('.',':',';',',')):
                base_block["text"] = text
                markdown_blocks.append(base_block)
            elif is_bold and is_upper:
                base_block["text"] = f'# {text}'
                markdown_blocks.append(base_block)
            else:
                base_block["text"] = f'## {text}'
                markdown_blocks.append(base_block)
        else:
            base_block["text"] = text
            markdown_blocks.append(base_block)

    return markdown_blocks

#Extra check for checking column headers in a table
def check_column_header(text:str) -> bool:
    text = text.strip()

    if len(text)>80:
        return False
    if text.endswith('.'):
        return False
    
    return True

def get_chunk_type(chunk_text:str) -> str:
    chunk_text = chunk_text.strip()
    if not chunk_text:
        return "text"
        
    lines = [l.strip() for l in chunk_text.split('\n') if l.strip()]
    if not lines:
        return "text"

    # Check for table
    table_rows = [l for l in lines if '|' in l]
    # Even a single table row with multiple pipes is a strong indicator of a table chunk
    if len(table_rows) >= 1 and chunk_text.count('|') >= 3:
        return "table"
        
    # Check for caption
    first_line_lower = lines[0].lower()
    if first_line_lower.startswith("fig.") or first_line_lower.startswith("figure") or first_line_lower.startswith("table"):
        if len(chunk_text) < 400: # Captions are usually short
            return "caption"
            
    # Check for list
    list_lines = [l for l in lines if l.startswith(('-', '*', '•')) or re.match(r'^\d+\.', l)]
    if len(list_lines) >= 3 or (len(list_lines) > 0 and len(list_lines) >= len(lines) * 0.3):
        return "list"
        
    # Check for heading
    if lines[0].startswith("#"):
        # If the chunk is relatively short and starts with a heading
        if len(lines) <= 3:
            return "heading"
            
    return "text"

def markdown_chunk(markdown_blocks:list, max_chars:int, overlap_chars:int)->list:
    chunks = []
    current_h1 = "Document Start"
    current_h2 = ""
    current_chunk_text = ""
    current_bboxes = []

    header_buffer = []

    for block in markdown_blocks:
        if block.get("is_table"):
            # Flush current chunk text before the table
            if header_buffer:
                current_chunk_text += "\n\n".join([b.get("text", "") for b in header_buffer]) + "\n\n"
                current_bboxes.extend([b["bbox_dict"] for b in header_buffer if "bbox_dict" in b])
                header_buffer = []
                
            if current_chunk_text.strip():
                chunks.append({
                    "type": get_chunk_type(current_chunk_text),
                    "h1_context": current_h1,
                    "h2_context": current_h2,
                    "content": f"{current_h1} - {current_h2} \n {current_chunk_text.strip()}",
                    "bboxes": current_bboxes
                })
                current_chunk_text = ""
                current_bboxes = []

            # Add the structured table as its own dedicated chunk
            bbox = block.get("bbox", (0,0,0,0))
            page = block.get("page_number", 0)
            table_bbox_dict = {"page": page, "x": round(bbox[0],2), "y": round(bbox[1],2), "w": round(bbox[2]-bbox[0],2), "h": round(bbox[3]-bbox[1],2)}
            
            chunks.append({
                "type": "table",
                "h1_context": current_h1,
                "h2_context": current_h2,
                "html": block.get("html", ""),
                "table_data": block.get("structured_rows", []),
                "bboxes": [table_bbox_dict]
            })
            continue

        para = block.get("text", "").strip()
        if not para: continue
        
        bbox = block.get("bbox", (0,0,0,0))
        page = block.get("page_number", 0)
        bbox_dict = {"page": page, "x": round(bbox[0],2), "y": round(bbox[1],2), "w": round(bbox[2]-bbox[0],2), "h": round(bbox[3]-bbox[1],2)}

        if para.startswith("# "):
            current_h1 = para.replace("# ","").strip()
            current_h2 = ""
            current_chunk_text += f"\n\n{para}\n\n"
            current_bboxes.append(bbox_dict)
            continue
        elif para.startswith("## "):
            current_h2 = para.replace("## ","").strip()
            current_chunk_text += f"\n\n{para}\n\n"
            current_bboxes.append(bbox_dict)
            continue

        if check_column_header(para):
            block["bbox_dict"] = bbox_dict
            header_buffer.append(block) 
        else:
            if header_buffer:
                current_chunk_text += "\n\n".join([b.get("text", "") for b in header_buffer]) + "\n\n"
                current_bboxes.extend([b["bbox_dict"] for b in header_buffer if "bbox_dict" in b])
                header_buffer = []
                
            current_chunk_text += f"{para}\n\n"
            current_bboxes.append(bbox_dict)

            if len(current_chunk_text) > max_chars:
                chunks.append({
                    "type": get_chunk_type(current_chunk_text),
                    "h1_context": current_h1,
                    "h2_context": current_h2,
                    "content": f"{current_h1} - {current_h2} \n {current_chunk_text.strip()}",
                    "bboxes": current_bboxes
                })
                
                overlap_text = current_chunk_text[-overlap_chars:]
                overlap_text = overlap_text.split(" ", 1)[-1] if " " in overlap_text else overlap_text
                current_chunk_text = f"...{overlap_text}\n\n"
                current_bboxes = []

    if header_buffer:
        current_chunk_text += "\n\n".join([b.get("text", "") for b in header_buffer]) + "\n\n"
        current_bboxes.extend([b["bbox_dict"] for b in header_buffer if "bbox_dict" in b])
    
    if current_chunk_text.strip():
        chunks.append({
            "type": get_chunk_type(current_chunk_text),
            "h1_context": current_h1,
            "h2_context": current_h2,
            "content": f"{current_h1} - {current_h2}\n{current_chunk_text.strip()}",
            "bboxes": current_bboxes
        })

    return chunks   