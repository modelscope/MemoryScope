from typing import Generator, List, Dict, Any

from pydantic import BaseModel, Field


class ModelResponse(BaseModel):
    text: str = Field("", description="")

    embedding_results:  List[List[float]] = Field([], description="")

    #rank_scores: Dict[int, float] = Field({}, description="The rank scores of each documents.")
    rank_scores: List[Dict[str, Any]] = Field({}, description="The rank scores of each documents.")
    # [{"document": "xxx", "score": 0.5}, {{"document": "yyy", "score": 0.3}}]
    model_type: str = Field("", description="One of LLM, EMB, RANK.")

    status: bool = Field(True, description="Indicates whether the model call was successful.")

    details: str = Field("", description=("The details information for model call, \
                         usually for storage of raw response or failure messages."))

    raw: Any = Field("", description=("raw response from model call"))
ModelResponseGen = Generator[ModelResponse, None, None]
