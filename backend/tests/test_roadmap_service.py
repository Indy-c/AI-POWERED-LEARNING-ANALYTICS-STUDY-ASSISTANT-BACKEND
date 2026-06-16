from app.domains.roadmap.service import generate_basic_roadmap, prepare_roadmap_source

def test_prepare_roadmap_source_cleans_whitespace():
    text = """
    Photosynthesis

    helps plants
    make food.
    """
    
    result = prepare_roadmap_source(text)

    assert result == "Photosynthesis helps plants make food."

def test_prepare_roadmap_source_limits_text_length():
    text = "a" * 1000
    
    result = prepare_roadmap_source(text)

    assert len(result) == 800

def test_generate_basic_roadmap_returns_study_steps():
    steps = generate_basic_roadmap("Photosynthesis helps plants make food.")

    assert len(steps) == 4
    assert steps[0].title == "Review the main concept"
    assert "Photosynthesis" in steps[0].description