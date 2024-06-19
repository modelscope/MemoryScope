from typing import Generator, List, Dict

from pydantic import BaseModel, Field


class ModelResponse(BaseModel):
    text: str = Field("", description="")

    embedding_results: Dict[int, List[float]] | List[float] = Field([], description="")

    rank_scores: List[float] = Field([], description="")

    status: bool = Field(True, description="")

    details: str = Field("", description="")


ModelResponseGen = Generator[ModelResponse, None, None]
