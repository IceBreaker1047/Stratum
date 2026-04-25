def extract_tables(page, page_number=None):
    tables = page.find_tables()
    table_elements = []

    for table in tables:
        extracted_data = table.extract()
        
        if not extracted_data:
            continue
        
        all_empty = all(
            not cell or str(cell).strip() == ""
            for row in extracted_data
            for cell in row
        )
        if all_empty:
            continue

        def clean_cell(cell):
            if cell is None:
                return ""
            cleaned = str(cell).replace("\n", " ").strip()
            return "" if cleaned.lower() == "none" else cleaned

        md_table = "\n"
        for i, row in enumerate(extracted_data):
            clean_row = [clean_cell(cell) for cell in row]
            md_table += "| " + " | ".join(clean_row) + " |\n"

        table_elements.append({
            "text": md_table + "\n",
            "size": 0,
            "bbox": table.bbox,
            "is_table": True,
            "page_number": page_number,
            "row_count": len(extracted_data),
            "col_count": len(extracted_data[0]) if extracted_data else 0
        })

    return table_elements