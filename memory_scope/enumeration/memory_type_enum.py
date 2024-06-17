from enum import Enum


class MemoryTypeEnum(str, Enum):
    CONVERSATION = "conversation"

    OBSERVATION = "observation"

    INSIGHT = "insight"

    PROFILE = "profile"

    OBS_CUSTOMIZED = "obs_customized"

    PROFILE_CUSTOMIZED = "profile_customized"
