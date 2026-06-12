from pathlib import Path

import fitz

# Extract plain text from a PDF file
def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("PDF file was not found")
    
    text_parts: list[str] = []
    with fitz.open(path) as pdf_document: 
        for page in pdf_document:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()