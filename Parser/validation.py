import re

def check_intersection(box1, box2):
    """Check if two bounding boxes intersect and return the intersection area."""
    if box1["page"] != box2["page"]:
        return 0.0
        
    x_left = max(box1["x"], box2["x"])
    y_top = max(box1["y"], box2["y"])
    x_right = min(box1["x"] + box1["w"], box2["x"] + box2["w"])
    y_bottom = min(box1["y"] + box1["h"], box2["y"] + box2["h"])
    
    if x_right < x_left or y_bottom < y_top:
        return 0.0
        
    return (x_right - x_left) * (y_bottom - y_top)

def calculate_structural_integrity(bboxes, text_length):
    score = 1.0
    
    if not bboxes:
        return score
        
    # Overlap Check
    total_area = 0.0
    overlap_area = 0.0
    
    for i, box1 in enumerate(bboxes):
        area1 = box1["w"] * box1["h"]
        total_area += area1
        for j, box2 in enumerate(bboxes[i+1:], start=i+1):
            overlap_area += check_intersection(box1, box2)
            
    if total_area > 0:
        overlap_ratio = overlap_area / total_area
        # Deduct up to 0.4 points for severe overlap
        score -= min(0.4, overlap_ratio)
        
    # Fragmentation Check
    if len(bboxes) > 1 and text_length > 0:
        chars_per_box = text_length / len(bboxes)
        if chars_per_box < 30: # Heavily fragmented (less than 30 chars per box)
            score -= 0.3
        elif chars_per_box < 60:
            score -= 0.1
            
    return max(0.0, score)

def calculate_entity_density(text):
    if not text:
        return 0.0
        
    words = text.split()
    if not words:
        return 0.0
        
    # Regex heuristics for entities
    # 1. Capitalized multi-word sequences (e.g., John Doe, United Nations)
    proper_nouns = len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text))
    
    # 2. Acronyms (2 or more uppercase letters)
    acronyms = len(re.findall(r'\b[A-Z]{2,}\b', text))
    
    # 3. Numeric values (dates, metrics)
    numerics = len(re.findall(r'\b\d+(?:\.\d+)?\b', text))
    
    total_entities = proper_nouns + acronyms + numerics
    
    # Calculate density (entities per 100 words)
    density = (total_entities / len(words)) * 100
    
    # Normalize score: Assume 15 entities per 100 words is excellent (1.0)
    normalized_score = min(1.0, density / 15.0)
    return normalized_score

def compute_rag_score(chunk):
    text_content = chunk.get("content", "")
    # Tables and text now both use 'content', so no special table extraction needed.
        
    bboxes = chunk.get("bboxes", [])
    
    integrity = calculate_structural_integrity(bboxes, len(text_content))
    density = calculate_entity_density(text_content)
    
    # Weighting: 40% Integrity, 60% Entity Density
    rag_score = (integrity * 0.4) + (density * 0.6)
    
    return {
        "score": round(rag_score, 3),
        "integrity": round(integrity, 3),
        "density": round(density, 3)
    }

def process_chunks_validation(chunks):
    for chunk in chunks:
        metrics = compute_rag_score(chunk)
        chunk["rag_score"] = metrics["score"]
        chunk["rag_metrics"] = metrics
    return chunks
