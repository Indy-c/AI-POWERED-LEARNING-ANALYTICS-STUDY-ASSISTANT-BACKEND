from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# One step in a generated study roadmap
class RoadmapStep(BaseModel):
    title: NonEmptyText
    description: NonEmptyText

# Study roadmap returned by the API
class RoadmapResponse(BaseModel):
    document_id: int
    steps: list[RoadmapStep] = Field(min_length=1)
    provider: str
