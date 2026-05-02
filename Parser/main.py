import json
from bleeder import extract_without_bleeds
from tree import construct_semantic_tree, flatten_tree_to_chunks
from validation import process_chunks_validation

def process_pdf_to_database(pdf_path:str, output_json_path:str):
    print(f"Starting pdf pipeline for {pdf_path}")

    print("Step 1: Extracting elements and filtering the bleeds...")
    clean_elements = extract_without_bleeds(pdf_path)

    print("Step 2: Processing images (Multimodal Pass)...")
    from image_processor import ImageCaptioner
    captioner = ImageCaptioner()
    for el in clean_elements:
        if el.get("is_image"):
            el["text"] = captioner.describe_image(el.get("image_bytes"))
            if "image_bytes" in el:
                del el["image_bytes"]

    print("Step 3: Constructing Hierarchical Semantic Tree...")
    document_tree = construct_semantic_tree(clean_elements)

    print("Step 4: Flattening Semantic Tree into Contextual Chunks...")
    final_chunks = flatten_tree_to_chunks(document_tree, max_chars=1200)

    print("Step 5: Running post-processing validation layer on chunks...")
    validated_chunks = process_chunks_validation(final_chunks)

    print(f"Step 6: Saving {len(validated_chunks)} chunks to {output_json_path}...")
    with open(output_json_path, "w", encoding="utf8") as f:
        json.dump(validated_chunks, f, indent=4, ensure_ascii=False)

    print("--- Pipeline Completed ---")

if __name__ == "__main__":
    pdf_file = "Sample_PDFs/research2.pdf"
    json_output = "final_database_chunks.json"
    
    process_pdf_to_database(pdf_file, json_output)