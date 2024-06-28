from typing import Dict, List

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    user_id: str = Field("", description="unique memory id for user")

    memory_id: str = Field("", description="unique id for memory item")

    content: str = Field("", description="memory content")

    score_similar: float = Field(0, description="es similar score")

    score_rank: float = Field(0, description="rank model score")

    score_rerank: float = Field(0, description="rerank score")

    memory_type: str = Field("", description="conversation/observation/insight...")

    meta_data: Dict[str, str] = Field({}, description="other data infos")

    status: str = Field("active", description="active or expired")

    vector: List[float] = Field([], description="content embedding result, return empty")

    @property
    def node_keys(self):
        return list(self.model_json_schema()["properties"].keys())

    def __getitem__(self, key: str):
        return self.model_dump().get(key)
