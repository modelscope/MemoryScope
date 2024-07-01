import datetime
from typing import Dict, List

from pydantic import Field, BaseModel

from memory_scope.utils.tool_functions import md5_hash


class MemoryNode(BaseModel):
    memory_id: str = Field("", description="unique id for memory item")

    user_id: str = Field("", description="unique memory id for user")

    meta_data: Dict[str, str] = Field({}, description="other data infos")

    content: str = Field("", description="memory content")

    score_similar: float = Field(0, description="es similar score")

    score_rank: float = Field(0, description="rank model score")

    score_rerank: float = Field(0, description="rerank score")

    memory_type: str = Field("", description="conversation/observation/insight...")

    status: str = Field("active", description="active or expired")

    vector: List[float] = Field([], description="content embedding result, return empty")

    timestamp: int = Field(int(datetime.datetime.now().timestamp()), description="timestamp of the memory node")

    obs_dt: str = Field("", description="dt of the observation")

    obs_reflected: bool = Field(False, description="if the observation is reflected")

    obs_profile_updated: bool = Field(False, description="if the observation has updated user profile")

    keyword: str = Field("", description="keywords of the content")


    @property
    def node_keys(self):
        return list(self.model_json_schema()["properties"].keys())

    def __getitem__(self, key: str):
        return self.model_dump().get(key)

    def gen_memory_id(self):
        self.memory_id = f"{self.user_id}_{self.timestamp}_{md5_hash(self.content)[:8]}"
