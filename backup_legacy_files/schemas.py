from pydantic import BaseModel, Field
from typing import Optional

class PromptRequest(BaseModel):
    text: Optional[str] = Field(None, description="User text input")
    image_base64: Optional[str] = Field(None, description="Base64-encoded image input")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation context")

class PromptResponse(BaseModel):
    text: Optional[str] = Field(None, description="LLM-generated text response")
    image_base64: Optional[str] = Field(None, description="LLM-generated image output (base64)")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation context") 