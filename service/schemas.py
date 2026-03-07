from datetime import datetime
from pydantic import BaseModel


# pydantic class to validate our inputs
class PredictRequest(BaseModel):
    
    pass
    

# class to validate our outputs
class PredictResponse(BaseModel):
    pass