from datetime import datetime

from pydantic import BaseModel 

# Data returned by the API for an uploaded document
class DocumentRead(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    content_type: str 
    processing_status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}