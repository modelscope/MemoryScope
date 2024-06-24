from typing import Generator, List, Dict, Any

from pydantic import BaseModel, Field

from memory_scope.enumeration.model_enum import ModelEnum


class ModelResponse(BaseModel):
    text: str = Field("", description="generation model result")

    embedding_results: List[List[float]] | List[float] = Field([], description="embedding vector")

    rank_scores: List[Dict[int, float]] = Field([], description="The rank scores of each documents. "
                                                                "key: index, value: rank score")

    model_type: ModelEnum = Field(ModelEnum.GENERATION_MODEL, description="One of LLM, EMB, RANK.")

    status: bool = Field(True, description="Indicates whether the model call was successful.")

    details: str = Field("", description="The details information for model call, "
                                         "usually for storage of raw response or failure messages.")

    raw: Any = Field("", description="raw response from model call")


ModelResponseGen = Generator[ModelResponse, None, None]
