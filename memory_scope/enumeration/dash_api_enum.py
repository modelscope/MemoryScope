from enum import Enum


class DashApiEnum(str, Enum):
    GENERATION = "generation"

    EMBEDDING = "embedding"

    RERANK = "rerank"
