from enum import Enum


class MemoryRecallType(str, Enum):
    SIMILAR = "similar"

    KEYWORD = "keyword"

    PROFILE = "profile"
