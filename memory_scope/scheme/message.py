import datetime
from typing import Dict

from pydantic import Field, BaseModel


class Message(BaseModel):
    """
    Represents a structured message object with details about the sender, content, and metadata.

    Attributes:
        role (str): The role of the message sender (e.g., 'user', 'assistant', 'system').
        role_name (str): Optional name associated with the role of the message sender.
        content (str): The actual content or text of the message.
        time_created (int): Timestamp indicating when the message was created.
        memorized (bool): Flag to indicate if the message has been saved or remembered.
        meta_data (Dict[str, str]): Additional data or context attached to the message.
    """
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")

    role_name: str = Field("", description="Name describing the role of the message sender")

    content: str = Field(..., description="The primary content of the message")

    time_created: int = Field(default_factory=lambda: int(datetime.datetime.now().timestamp()),
                              description="Timestamp marking the message creation time")

    memorized: bool = Field(False, description="Indicates if the message is flagged for memory retention")

    meta_data: Dict[str, str] = Field({}, description="Supplementary data attached to the message")
