from pydantic import BaseModel

class Audio(BaseModel):
    audio: str
    
class Text(BaseModel):
    text: str