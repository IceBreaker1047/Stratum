import pymupdf
import re
from table import extract_tables

#Checks the y axis overlapping to detect multicolumn layouts
def detect_multicolumn(doc):
    multicolumn_pages = 0
    
    for i in range(min(5, len(doc))): # Only check first few pages
        page = doc[i]
        blocks = [b for b in page.get_text("dict", sort=False)["blocks"] if b['type'] == 0]
        
        page_height = page.rect.height
        body_blocks = [b for b in blocks if b['bbox'][1] > page_height * 0.1 and b['bbox'][3] < page_height * 0.9]
        
        is_multi = False
        for i in range(len(body_blocks)):
            for j in range(i + 1, len(body_blocks)):
                b1 = body_blocks[i]['bbox']
                b2 = body_blocks[j]['bbox']
                
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
                # Robust fallback: Render the bounding box area
                try:
                    pix = page.get_pixmap(clip=block["bbox"], matrix=pymupdf.Matrix(2, 2))
                    img_bytes = pix.tobytes("png")
                except:
                    img_bytes = None

            elements.append({
                "is_image": True,
                "image_bytes": img_bytes,
                "text": "[IMAGE MULTIMODAL DESCRIPTION PENDING]",
                "size": 0,
                "is_bold": False,
                "is_upper": False,
                "bbox": (block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3]),
                "page_number": page.number,
                "x0": block["bbox"][0],
                "y0": block["bbox"][1],
                "x1": block["bbox"][2],
                "y1": block["bbox"][3],
                "page_width": page_width
            })
            continue
            
        if block["type"] != 0: continue 
        
        # We still check if the overall block/line is in a table
        for line in block["lines"]:
            line_bbox = line["bbox"]
            is_inside_table = False
            
            for t in tables:
                t_box = t["bbox"]
                if (line_bbox[0] >= t_box[0] - 5 and line_bbox[1] >= t_box[1] - 5 and 
                    line_bbox[2] <= t_box[2] + 5 and line_bbox[3] <= t_box[3] + 5):
                    is_inside_table = True
                    break
                    
            if is_inside_table:
                continue

            line_text = ""
            max_font_size = 0

            is_bold = False
            
            # Process span by span, but append at the LINE level
            for span in line["spans"]:
                text = span["text"]
                if not text.strip(): 
                    line_text += text
                    continue
                
                font_size = round(span["size"], 1)
                if font_size > max_font_size: 
                    max_font_size = font_size
                
                font_name = span.get("font","").lower()
                span_is_bold = (span["flags"] & 16) or "bold" in font_name or "heavy" in font_name
                span_is_italic = (span["flags"] & 2) or "italic" in font_name or "oblique" in font_name
                span_is_super = (span["flags"] & 1) or "sup" in font_name
                
                # Check for relative superscript if flag misses it
                if not span_is_super and font_size < (max_font_size * 0.85) and span["bbox"][1] < line["bbox"][1] + (line["bbox"][3]-line["bbox"][1])*0.3:
                    span_is_super = True

                stripped_text = text.strip()
                prefix_spaces = text[:len(text) - len(text.lstrip())]
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
            line_text = line_text.strip()
            if line_text:
                elements.append({
                    "text": line_text,
                    "size": max_font_size,
                    "is_bold": is_bold,
                    "is_upper": line_text.isupper() and len(line_text)>4,
                    "y1": line["bbox"][3],
                    "x0": line["bbox"][0],
                    "x1": line["bbox"][2],
                    "bbox": (line["bbox"][0], line["bbox"][1], line["bbox"][2], line["bbox"][3]),
                    "page_number": page.number,
                    "page_width": page_width,
                    "y0": line["bbox"][1],
                    "y1": line["bbox"][3],
                    "x0": line["bbox"][0],
                    "x1": line["bbox"][2]
                })
            
    if not is_multicolumn:
        elements.sort(key=lambda el: el.get("y0", el.get("bbox", [0,0])[1]))
    else:
        page_midpoint = page.rect.width / 2
        def multi_col_sort_key(el):
            y0 = el.get("y0", el.get("bbox", [0,0])[1])
            x0 = el.get("x0", el.get("bbox", [0,0])[0])
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

    # --- PASS 1: The Bleed Blacklist ---
    margin_text_stats = {}
    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page, is_multicolumn) 
        
        for el in elements:
            if el.get("is_table"): 
                continue 
                
            normalized_text = re.sub(r'\d+', '<NUM>', el["text"]).strip()
            
            is_top_margin = el["y1"] < (page_height * 0.12)  
            is_bottom_margin = el["y0"] > (page_height * 0.88) 

            if is_top_margin or is_bottom_margin:
                if normalized_text not in margin_text_stats:
                    margin_text_stats[normalized_text] = {'count': 0, 'pages_seen': set()}
                if page.number not in margin_text_stats[normalized_text]['pages_seen']:
                    margin_text_stats[normalized_text]['count'] += 1
                    margin_text_stats[normalized_text]['pages_seen'].add(page.number)
        
    bleed_blacklist = set()
    for text_key, stats in margin_text_stats.items():
        if stats['count'] >= frequency_threshold:
            bleed_blacklist.add(text_key)

    # --- PASS 2: Extract Clean Data ---
    document_elements = []
    
    # NEW: Regex pattern to catch page numbers ("2", "Page 2", "- 2 -", "2 of 10")
    page_pattern = re.compile(r'^(page\s*)?-?\s*\d+\s*(of\s*\d+)?\s*-?$', re.IGNORECASE)
    
    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page, is_multicolumn) 
        
        for el in elements:
            if el.get("is_table"):
                document_elements.append({
                    "is_table": True,
                    "html": el.get("html", ""),
                    "structured_rows": el.get("structured_rows", []),
                    "text": el["text"],
                    "size": el["size"],
                    "bbox": el.get("bbox", (0,0,0,0)),
                    "page_number": el.get("page_number", 0),
                    "is_bold": el.get("is_bold",False),
                    "is_upper": el.get("is_upper",False)
                })
                continue
                
            if el.get("is_image"):
                document_elements.append({
                    "is_image": True,
                    "image_bytes": el.get("image_bytes"),
                    "text": el["text"],
                    "size": el["size"],
                    "bbox": el.get("bbox", (0,0,0,0)),
                    "page_number": el.get("page_number", 0),
                    "is_bold": el.get("is_bold",False),
                    "is_upper": el.get("is_upper",False)
                })
                continue

            clean_text = el["text"].strip()
            normalized_text = re.sub(r'\d+', '<NUM>', clean_text)
            
            is_top_margin = el["y1"] < (page_height * 0.12)
            is_bottom_margin = el["y0"] > (page_height * 0.88)

            # --- THE COMBINED FILTER ---
            if is_top_margin or is_bottom_margin:
                # 1. Check if it's a repeating header/footer
                if normalized_text in bleed_blacklist:
                    continue 
                # 2. Check if it's an isolated page number
                if page_pattern.match(clean_text):
                    continue
            
            # Send clean data to the chunker
            el_to_add = el.copy()
            el_to_add["text"] = clean_text
            document_elements.append(el_to_add)

    print(f"Bleeder: Blacklisted {len(bleed_blacklist)} items & filtered page numbers. Extracted {len(document_elements)} clean blocks.")
    return document_elements