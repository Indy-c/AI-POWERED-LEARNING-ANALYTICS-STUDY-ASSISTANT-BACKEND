# Create a simple temporary summary from extracted document text
def generate_basic_summary(document_text: str) -> str:
    cleaned_text = " ".join(document_text.split())
    return cleaned_text[:1000]