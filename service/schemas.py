from datetime import datetime, timezone
from pydantic import BaseModel, Field


# pydantic class to validate our inputs
class PredictRequest(BaseModel):
    symbol: str
    time: datetime = Field(default_factory = lambda: datetime.now(tz=timezone.utc))
    

# class to validate our outputs
class PredictResponse(BaseModel):
    risk_label: str
    risk_score: float = Field(ge=0, le=1)
    top_signals: list[str]
    computed_at: datetime
    window_start: datetime
    window_end: datetime
    latency_ms: float
    model_version: str # gives model version for debugging purposes
    
