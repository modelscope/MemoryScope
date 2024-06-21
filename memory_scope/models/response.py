from typing import Generator, List, Dict

from pydantic import BaseModel, Field


class ModelResponse(BaseModel):
    text: str = Field("", description="")

    embedding_results: Dict[int, List[float]] | List[float] = Field([], description="")

    rank_scores: Dict[int, float] = Field({}, description="The rank scores of each documents.")

    model_type: str = Field("", description="One of LLM, EMB, RANK.")

    status: bool = Field(True, description="Indicates whether the model call was successful.")

    details: str = Field("", description=("The details information for model call, \
                         usually for storage of raw response or failure messages."))


ModelResponseGen = Generator[ModelResponse, None, None]
