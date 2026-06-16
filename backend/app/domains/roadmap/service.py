import json 

from google import genai

from app.core.config import settings

from app.domains.roadmap.schemas import RoadmapStep

# Shorten document text before using it to build roadmap steps
def prepare_roadmap_source(document_text: str) -> str:
    cleaned_text = " ".join(document_text.split())
    return cleaned_text[:800] 

# Generate a simple roadmap without calling an AI provider
def generate_basic_roadmap(document_text: str) -> list[RoadmapStep]:
    source = prepare_roadmap_source(document_text)

    return [
        RoadmapStep(
            title="Review the main concept", 
            description=f"Read the main material and identify the core idea: {source[:200]}",
        ),
        RoadmapStep(
            title="Create quick notes",
            description="Write short notes for the most important terms, definitions, and examples.",
        ),
        RoadmapStep(
            title="Practice with flashcards",
            description="Turn key ideas into flashcards and review them until you can answer without looking.",
        ),
        RoadmapStep(
            title="Test your understanding",
            description="Take a quiz, check your mistakes, and review the parts you missed.",
        ),
    ]

# Generate roadmap steps with Gemini
def generate_gemini_roadmap(document_text: str) -> list[RoadmapStep]:
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured")
    
    source = prepare_roadmap_source(document_text)

    prompt = f"""
    Create a 4-steps study roadmap from this study material.
    
    Return only valid JSON in this format:
    [
        {{
        "title": "Step title",
        "description": "Step description"
        }}
    ]
    
    Study material:
    {source}
    """
    
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model = "gemini-2.5-flash",
        contents = prompt,
    )

    raw_text = response.text.strip()
    roadmap_data = json.loads(raw_text)

    return [RoadmapStep(**step) for step in roadmap_data]
