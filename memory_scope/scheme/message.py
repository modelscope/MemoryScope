import datetime

from pydantic import Field, BaseModel


class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")

    content: str = Field(..., description="The body of the message")

    time_created: int = Field(int(datetime.datetime.now().timestamp()),
                              description="Timestamp when the message was created")

    memorized: bool = Field(False, description="indicate whether message is memorized")
