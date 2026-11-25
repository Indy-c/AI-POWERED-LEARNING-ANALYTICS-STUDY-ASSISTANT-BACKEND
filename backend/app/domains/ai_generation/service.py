from google import genai
import json

from app.core.config import settings


class GeminiNotConfigured(ValueError):
    pass


# Create a Gemini API client
def get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("Gemini API key is not configured")
    
    return genai.Client(api_key=settings.gemini_api_key)

#Parse JSON returned by Gemini, even if wrapped in markdown fences
def parse_gemini_json(response_text: str):
    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text.removeprefix("```json").removesuffix("```").strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.removeprefix("```").removesuffix("```").strip()

    return json.loads(cleaned_text)


def _select_study_context(document_text: str) -> str:
    max_chars = 12_000
    if len(document_text) <= max_chars:
        return document_text

    separator = "\n\n[...]\n\n"
    excerpt_size = (max_chars - 2 * len(separator)) // 3
    middle_start = (len(document_text) - excerpt_size) // 2
    return separator.join(
        (
            document_text[:excerpt_size],
            document_text[middle_start : middle_start + excerpt_size],
            document_text[-excerpt_size:],
        )
    )


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
{_select_study_context(document_text)}
"""
    response = client.models.generate_content(
        model=settings.gemini_model, 
        contents=prompt,
    )
    if not (response.text or "").strip():
        raise ValueError("Gemini returned an empty summary")
    return response.text

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
        model=settings.gemini_model,
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
{_select_study_context(document_text)}
"""
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
    )
        response_text = response.text or "[]"

        try:
            return parse_gemini_json(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Gemini returned invalid quiz JSON") from exc
