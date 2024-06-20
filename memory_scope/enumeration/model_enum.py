from enum import Enum


class ModelEnum(str, Enum):
    GENERATION_MODEL = "generation_model"

    EMBEDDING_MODEL = "embedding_model"

    RANK_MODEL = "rank_model"
