import datetime
from typing import Dict, List
from uuid import uuid4

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    memory_id: str = Field(str(uuid4()), description="unique id for memory")

    user_name: str = Field("", description="the user who owns the memory")

    target_name: str = Field("", description="target name described by the memory")

    meta_data: Dict[str, str] = Field({}, description="meta data infos")

    content: str = Field("", description="memory content")

    key: str = Field("", description="memory key")

    value: str = Field("", description="memory value")

    score_similar: float = Field(0, description="es similar score")

    score_rank: float = Field(0, description="rank model score")

    score_rerank: float = Field(0, description="rerank score")

    memory_type: str = Field("", description="conversation/observation/insight...")

    status: str = Field("active", description="db status: active / expired; modification_status: "
                                              "new / content_modified / modified / active / expired")

    vector: List[float] = Field([], description="content embedding result, return empty")

    timestamp: int = Field(int(datetime.datetime.now().timestamp()), description="timestamp of the memory node")

    dt: str = Field("", description="dt of the memory node")

    obs_reflected: bool = Field(False, description="if the observation is reflected")

    obs_updated: bool = Field(False, description="if the observation has updated user profile or insight")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dt = datetime.datetime.fromtimestamp(self.timestamp).strftime("%Y%m%d")

    @property
    def node_keys(self):
        return list(self.model_json_schema()["properties"].keys())

    def __getitem__(self, key: str):
        return self.model_dump().get(key)
