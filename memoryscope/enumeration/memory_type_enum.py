from enum import Enum


class MemoryTypeEnum(str, Enum):
    """
    Defines an enumeration for different types of memory categories.
    
    Each member represents a distinct type of memory content:
    - CONVERSATION: Represents conversation-based memories.
    - OBSERVATION: Denotes observational memories.
    - INSIGHT: Indicates insightful memories derived from analysis.
    - OBS_CUSTOMIZED: Customized observational memories.
    """
    CONVERSATION = "conversation"

    OBSERVATION = "observation"

    INSIGHT = "insight"

    OBS_CUSTOMIZED = "obs_customized"
