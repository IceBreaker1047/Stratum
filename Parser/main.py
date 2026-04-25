import json
from bleeder import extract_without_bleeds
from chunking import extract_markdown,markdown_chunk

def process_pdf_to_database(pdf_path:str, output_json_path:str):
    print(f"Starting pdf pipeline for {pdf_path}")

    print("Step 1: Extracting elements and filtering the bleeds...")
    clean_elements = extract_without_bleeds(pdf_path)

    print("Step 2: Generating semantic markdowns...")
    markdown_string = extract_markdown(clean_elements)

    print("Step 3: Slicing into context based chunks...")
    final_chunks = markdown_chunk(markdown_string,max_chars=1200,overlap_chars=200)

    print(f"Step 4: Saving {len(final_chunks)} chunks to {output_json_path}...")
    with open(output_json_path, "w", encoding="utf8") as f:
        json.dump(final_chunks,f,indent=4,ensure_ascii=False)

    print("--- Pipeline Completed ---")

if __name__ == "__main__":
    pdf_file = "Sample_PDFs/Financial_Statement.pdf"
    json_output = "final_database_chunks.json"
    
    process_pdf_to_database(pdf_file, json_output)