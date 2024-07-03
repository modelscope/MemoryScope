from enum import Enum


class MemoryTypeEnum(str, Enum):
    CONVERSATION = "conversation"

    OBSERVATION = "observation"

    INSIGHT = "insight"

    OBS_CUSTOMIZED = "obs_customized"
