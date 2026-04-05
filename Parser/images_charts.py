import pymupdf

def extract_tables(page):
    tables = page.find_tables()
    table_elements = []

    for table in tables:
        extracted_data = table.extract()
        if not extracted_data:
            continue

        md_table = "\n"
        for i,row in enumerate(extracted_data):
            clean_row = [str(cell).replace("\n"," ").strip() if cell else "" for cell in row]
            md_table += "| " + " | ".join(clean_row) + " |\n"

        if i == 0:
            md_table += "|" + "|".join(["---"] * len(row)) + "|\n"
    
        table_elements.append({
            "text": md_table + "\n",
            "size": 0,
            "bbox": table.bbox,
            "is_table": True
        })

    return table_elements