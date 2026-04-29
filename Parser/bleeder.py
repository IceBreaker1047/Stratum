import pymupdf
import re
from table import extract_tables

def get_page_elements(page):
    elements = []

    tables = extract_tables(page)
    elements.extend(tables)

    page_dict = page.get_text("dict") 
    
    for block in page_dict["blocks"]:
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
                text = span["text"].strip()
                if not text: continue
                
                font_size = round(span["size"], 1)
                line_text += text + " "
                if font_size > max_font_size: 
                    max_font_size = font_size
                
                #Check if the font is bold for parsing context
                font_name = span.get("font","").lower()
                if(span["flags"]&16) or "bold" in font_name or "heavy" in font_name:
                    is_bold = True
                    
            line_text = line_text.strip()
            if line_text:
                elements.append({
                    "text": line_text,
                    "size": max_font_size,
                    "is_bold": is_bold,
                    "is_upper": line_text.isupper() and len(line_text)>4,
                    "y0": line["bbox"][1], # Use LINE coordinates, not block
                    "y1": line["bbox"][3],
                    "is_table": False
                })
            
    elements.sort(key=lambda el: el.get("y0", el.get("bbox", [0,0])[1]))
    
    return elements

def extract_without_bleeds(pdf_path):
    doc = pymupdf.open(pdf_path)
    num_pages = len(doc)
    frequency_threshold = max(2, int(num_pages * 0.3))

    # --- PASS 1: The Bleed Blacklist ---
    margin_text_stats = {}
    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page) 
        
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
        elements = get_page_elements(page) 
        
        for el in elements:
            if el.get("is_table"):
                document_elements.append({
                    "text": el["text"],
                    "size": el["size"],
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
            document_elements.append({
                "text": clean_text,
                "size": el["size"],
                "is_bold": el.get("is_bold",False),
                "is_upper": el.get("is_upper",False)
            })

    print(f"Bleeder: Blacklisted {len(bleed_blacklist)} items & filtered page numbers. Extracted {len(document_elements)} clean blocks.")
    return document_elements