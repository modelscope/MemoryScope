import json
from typing import Generator, List, Dict, Any

from pydantic import BaseModel, Field

from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.scheme.message import Message


class ModelResponse(BaseModel):
    message: Message | None = Field(None, description="generation model result")

    delta: str = Field("", description="New text that just streamed in (only used when streaming)")

    embedding_results: List[List[float]] | List[float] = Field([], description="embedding vector")

    rank_scores: Dict[int, float] = Field({}, description="The rank scores of each documents. "
                                                          "key: index, value: rank score")

    m_type: ModelEnum = Field(ModelEnum.GENERATION_MODEL, description="One of LLM, EMB, RANK.")

    status: bool = Field(True, description="Indicates whether the model call was successful.")

    details: str = Field("", description="The details information for model call, "
                                         "usually for storage of raw response or failure messages.")

    raw: Any = Field("", description="Raw response from model call")

    def __str__(self, max_size=100, **kwargs):
        result = {}
        # noinspection PyBroadException
        try:
            all_dict = self.model_dump()
        except Exception:
            all_dict = self.dict()

        for key, value in all_dict.items():
            if key == "raw" or not value:
                continue

            if isinstance(value, str):
                result[key] = value
            elif isinstance(value, list | dict):
                result[key] = f"{str(value)[:max_size]}... size={len(value)}"
            elif isinstance(value, ModelEnum):
                result[key] = value.value
        return json.dumps(result, **kwargs)


ModelResponseGen = Generator[ModelResponse, None, None]
