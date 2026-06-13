from pydantic import BaseModel

# Summary returned for a study document
class SummaryResponse(BaseModel):
    document_id: int
    summary: str
    provider: str