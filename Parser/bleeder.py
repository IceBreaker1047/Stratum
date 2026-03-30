import pymupdf
import re

def get_page_elements(page):
    """Helper function to ensure Pass 1 and Pass 2 extract text identically."""
    elements = []
    page_dict = page.get_text("dict") 
    for block in page_dict["blocks"]:
        if block["type"] != 0: continue
        
        block_text = ""
        max_font_size = 0
        
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text: continue
                
                font_size = round(span["size"], 1)
                block_text += text + " "
                if font_size > max_font_size: 
                    max_font_size = font_size
                    
        block_text = block_text.strip()
        if block_text:
            y0, y1 = block["bbox"][1], block["bbox"][3]
            elements.append({
                "text": block_text,
                "size": max_font_size,
                "y0": y0,
                "y1": y1
            })
    return elements

def extract_without_bleeds(pdf_path):
    doc = pymupdf.open(pdf_path)
    num_pages = len(doc)
    frequency_threshold = max(2, int(num_pages * 0.3))

    # --- PASS 1: The Bleed Blacklist ---
    margin_text_stats = {}
    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page) # Use helper
        
        for el in elements:
            normalized_text = re.sub(r'\d+', '<NUM>', el["text"]).strip()
            
            is_top_margin = el["y1"] < (page_height * 0.12)  # Top 12%
            is_bottom_margin = el["y0"] > (page_height * 0.88) # Bottom 12%

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
    
    for page in doc:
        page_height = page.rect.height
        elements = get_page_elements(page) # Use helper
        
        for el in elements:
            normalized_text = re.sub(r'\d+', '<NUM>', el["text"]).strip()
            is_top_margin = el["y1"] < (page_height * 0.12)
            is_bottom_margin = el["y0"] > (page_height * 0.88)

            # Apply the filter
            if normalized_text in bleed_blacklist and (is_top_margin or is_bottom_margin):
                continue 
            
            # Send clean data to the chunker
            document_elements.append({
                "text": el["text"],
                "size": el["size"]
            })

    print(f"Bleeder: Blacklisted {len(bleed_blacklist)} items. Extracted {len(document_elements)} clean blocks.")
    return document_elements