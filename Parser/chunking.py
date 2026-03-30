from collections import Counter
import pymupdf
import json

def create_header_mapping(all_font_sizes: list) -> tuple[dict,float]:
    if not all_font_sizes:
        return {},0.0
    
    size_counts = Counter(all_font_sizes)
    baseline_size = size_counts.most_common(1)[0][0]

    larger_sizes = set([size for size in all_font_sizes if size>baseline_size])
    sorted_header_sizes = sorted(list(larger_sizes),reverse=True)

    header_mapping = {}
    for rank,size in enumerate(sorted_header_sizes):
        markdown_hashes = "#" * min(rank+1,6)
        header_mapping[size] = markdown_hashes

    return header_mapping, baseline_size

def extract_markdown(document_elemts:list)->str:
    if not document_elemts:
        return ""
    
    all_font_sizes = [el["size"] for el in document_elemts]
    header_mapping, baseline_size = create_header_mapping(all_font_sizes)

    markdown_lines = []

    for element in document_elemts:
        size = element["size"]
        text = element["text"]
        
        if size in header_mapping:
            markdown_tag = header_mapping[size]
            markdown_lines.append(f"{markdown_tag} {text}")
        else:
            markdown_lines.append(text)

    final_markdown_string = "\n\n".join(markdown_lines)

    return final_markdown_string

#Current chunking is based on font size 
def markdown_chunk(markdown_text:str, max_chars:int, overlap_chars:int)->list:
    raw_paragraphs = markdown_text.split("\n\n")
    chunks = []
    current_h1 = "Document Start"
    current_h2 = ""
    current_chunk_text = ""

    for para in raw_paragraphs:
        para = para.strip()
        if not para: continue

        if para.startswith("# "):
            current_h1 = para.replace("# ","").strip()
            current_h2 = ""
            continue
        elif para.startswith("## "):
            current_h2 = para.replace("## ","").strip()
            continue
        
        if len(current_chunk_text) + len(para) > max_chars and current_chunk_text:
            chunks.append({
                "h1_context": current_h1,
                "h2_context": current_h2,
                "content": f"{current_h1} - {current_h2} \n {current_chunk_text.strip()}"
            })
            overlap_text = current_chunk_text[-overlap_chars:]
            overlap_text = overlap_text.split(" ", 1)[-1] if " " in overlap_text else overlap_text
            current_chunk_text = f"...{overlap_text}\n\n{para}\n\n"
        else:
            current_chunk_text+=f"{para}\n\n"

    if current_chunk_text.strip():
        chunks.append({
            "h1_context": current_h1,
            "h2_context": current_h2,
            "content": f"{current_h1} - {current_h2}\n{current_chunk_text.strip()}"
        })

    return chunks   