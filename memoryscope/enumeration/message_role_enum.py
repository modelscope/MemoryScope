from enum import Enum


class MessageRoleEnum(str, Enum):
    """
    Enumeration for different message roles within a conversation context.
    
    This enumeration includes predefined roles such as User, Assistant, and System,
    which can be used to categorize messages in chat interfaces, AI interactions, or 
    any system that involves distinct participant roles.
    """
    USER = "user"  # Represents a message sent by the user.

    ASSISTANT = "assistant"  # Represents a response or action performed by an assistant.

    SYSTEM = "system"  # Represents system-level messages or actions.
