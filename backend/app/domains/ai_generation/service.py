from google import genai

from app.core.config import settings

# Create a Gemini API client
def get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured")
    
    return genai.Client(api_key=settings.gemini_api_key)

# Generate a study summary using Gemini
def generate_gemini_summary(document_text: str) -> str:
    client = get_gemini_client()

    prompt = f"""
You are an academic study assistant.

Summarize the following study material in beginner-friendly language.
Focus on: 
- key concepts
- important definitions
- practical examples
- exam revision points

Study material:
{document_text[:12000]}
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents=prompt,
    )
    return response.text or "No summary was generated."

# Create a simple temporary summary from extracted document text
def generate_basic_summary(document_text: str) -> str:
    cleaned_text = " ".join(document_text.split())
    return cleaned_text[:1000]