from pydantic import Field, BaseModel


class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")

    content: str = Field(..., description="The body of the message")

    time_created: str = Field("", description="Timestamp when the message was created")

    info_score: str = Field("", description="2 > 1 > 0")
