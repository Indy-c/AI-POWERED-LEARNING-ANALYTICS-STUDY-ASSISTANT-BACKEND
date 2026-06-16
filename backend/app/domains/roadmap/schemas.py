from pydantic import BaseModel

# One step in a generated study roadmap
class RoadmapStep(BaseModel):
    title: str
    description: str

# Study roadmap returned by the API
class RoadmapResponse(BaseModel):
    document_id: int
    steps: list[RoadmapStep]
    provider: str