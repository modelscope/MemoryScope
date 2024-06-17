from enum import Enum


class MessageRoleEnum(str, Enum):
    USER = "user"

    ASSISTANT = "assistant"

    SYSTEM = "system"
