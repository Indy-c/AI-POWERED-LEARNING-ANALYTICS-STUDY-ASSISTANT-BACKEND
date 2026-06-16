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