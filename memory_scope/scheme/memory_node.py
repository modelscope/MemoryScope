from typing import Dict, List

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    id: str = Field("", description="uuid64")

    content: str = Field("", description="memory content")

    memory_id: str = Field("", description="unique memory id")

    score_similar: float = Field(0, description="es similar score")

    score_rank: float = Field(0, description="rank model score")

    score_rerank: float = Field(0, description="rerank score")

    memory_type: str = Field("", description="conversation/observation/insight...")

    meta_data: Dict[str, str] = Field({}, description="other data infos")

    status: str = Field("active", description="active or expired")

    vector: List[float] = Field([], description="content embedding result, return empty")
