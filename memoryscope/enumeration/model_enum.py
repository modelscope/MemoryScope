from enum import Enum


class ModelEnum(str, Enum):
    """
    An enumeration representing different types of models used within the system.

    Members:
        GENERATION_MODEL: Represents a model responsible for generating content.
        EMBEDDING_MODEL: Represents a model tasked with creating embeddings, typically used for transforming data into a
            numerical form suitable for machine learning tasks.
        RANK_MODEL: Denotes a model that specializes in ranking, often used to order items based on relevance.
    """
    GENERATION_MODEL = "generation_model"

    EMBEDDING_MODEL = "embedding_model"

    RANK_MODEL = "rank_model"
