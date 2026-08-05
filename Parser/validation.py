import re


def check_intersection(box1, box2):
    # Check if two boxes overlap on the same page.
    if box1["page"] != box2["page"]:
        return 0.0

    left = max(box1["x"], box2["x"])
    top = max(box1["y"], box2["y"])
    right = min(box1["x"] + box1["w"], box2["x"] + box2["w"])
    bottom = min(box1["y"] + box1["h"], box2["y"] + box2["h"])

    if right < left or bottom < top:
        return 0.0

    return (right - left) * (bottom - top)


def calculate_structural_integrity(bboxes, text_length):
    # Start with a full score and lower it if the layout looks messy.
    score = 1.0

    if not bboxes:
        return score

    total_area = 0.0
    overlap_area = 0.0

    for i, box1 in enumerate(bboxes):
        total_area += box1["w"] * box1["h"]
        for box2 in bboxes[i + 1:]:
            overlap_area += check_intersection(box1, box2)

    if total_area > 0:
        overlap_ratio = overlap_area / total_area
        score -= min(0.4, overlap_ratio)

    if len(bboxes) > 1 and text_length > 0:
        chars_per_box = text_length / len(bboxes)
        if chars_per_box < 30:
            score -= 0.3
        elif chars_per_box < 60:
            score -= 0.1

    return max(0.0, score)


def calculate_entity_density(text):
    # Give a higher score when the text has more useful named values.
    if not text:
        return 0.0

    words = text.split()
    if not words:
        return 0.0

    proper_nouns = len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text))
    acronyms = len(re.findall(r'\b[A-Z]{2,}\b', text))
    numerics = len(re.findall(r'\b\d+(?:\.\d+)?\b', text))

    total_entities = proper_nouns + acronyms + numerics
    density = (total_entities / len(words)) * 100

    return min(1.0, density / 15.0)


def compute_rag_score(chunk):
    # Combine layout quality and content richness into one score.
    text_content = chunk.get("content", "")
    bboxes = chunk.get("bboxes", [])

    integrity = calculate_structural_integrity(bboxes, len(text_content))
    density = calculate_entity_density(text_content)
    rag_score = (integrity * 0.4) + (density * 0.6)

    return {
        "score": round(rag_score, 3),
        "integrity": round(integrity, 3),
        "density": round(density, 3),
    }


def process_chunks_validation(chunks):
    # Add the score to each chunk.
    for chunk in chunks:
        metrics = compute_rag_score(chunk)
        chunk["rag_score"] = metrics["score"]
        chunk["rag_metrics"] = metrics

    return chunks