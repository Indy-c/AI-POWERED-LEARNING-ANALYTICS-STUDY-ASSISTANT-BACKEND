from google import genai
import json

from app.core.config import settings

# Create a Gemini API client
def get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured")
    
    return genai.Client(api_key=settings.gemini_api_key)

#Parse JSON returned by Gemini, even if wrapped in markdown fences
def parse_gemini_json(response_text: str):
    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text.removeprefix("```json").removesuffix("```").strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.removeprefix("```").removesuffix("```").strip()

    return json.loads(cleaned_text)

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

# Create simple temporary flashcards from document text
def generate_basic_flashcards(document_text: str) -> list[dict[str, str]]:
    cleaned_text = " ".join(document_text.split())
    preview = cleaned_text[:300]

    return [
        {
            "question": "What is the main idea of this document?",
            "answer": preview,
        }
    ]

# Create simple temporary quiz questions from document text
def generate_basic_quiz(document_text: str) -> list[dict[str, object]]:
    cleaned_text = " ".join(document_text.split())
    preview = cleaned_text[:200]

    return [
        {
            "question": "What is this study material mainly about?",
            "choices": [
                preview,
                "A random unrelated topic",
                "A user authentication system only",
                "A database migration tool only",
            ],
            "correct_answer": preview,
        }
    ]

# Generate study flashcards using Gemini
def generate_gemini_flashcards(document_text: str) -> list[dict[str, str]]:
    client = get_gemini_client()

    prompt = f"""
You are an academic study assistant.

Create 5 flashcards from the study material below.
Return only valid JSON in this exact format:
[
  {{"question": "question text", "answer": "answer text"}}
]

Study material:
{document_text[:12000]}
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )   
    response_text = response.text or "[]"
    
    try: 
        return parse_gemini_json(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned invalid flashcard JSON") from exc
    
# Generate quiz questions using Gemini
def generate_gemini_quiz(document_text: str) -> list[dict[str, object]]:
        client = get_gemini_client()

        prompt = f"""
You are an academic quiz generator.

Create 5 multiple-choice quiz questions from the study material below.
Return only valid JSON in this exact format:
[
  {{
    "question": "question text",
    "choices": ["A", "B", "C", "D"],
    "correct_answer": "correct choice text"
  }}
]

Study material:
{document_text[:12000]}
"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
    )
        response_text = response.text or "[]"

        try:
            return parse_gemini_json(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Gemini returned invalid quiz JSON") from exc