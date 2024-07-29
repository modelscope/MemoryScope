import datetime
from typing import Dict, List
from uuid import uuid4

from pydantic import Field, BaseModel


class MemoryNode(BaseModel):
    """
    Represents a memory node with comprehensive attributes to store memory information including unique ID,
    user details, content, metadata, scoring metrics.
    Automatically handles timestamp conversion to date format during initialization.
    """
    memory_id: str = Field(default_factory=lambda: uuid4().hex, description="unique id for memory")

    user_name: str = Field("", description="the user who owns the memory")

    target_name: str = Field("", description="target name described by the memory")

    meta_data: Dict[str, str] = Field({}, description="meta data infos")

    content: str = Field("", description="memory content")

    key: str = Field("", description="memory key")

    key_vector: List[float] = Field([], description="memory key embedding result")

    value: str = Field("", description="memory value")

    score_recall: float = Field(0, description="embedding similarity score used in recall stage")

    score_rank: float = Field(0, description="rank model score used in rank stage")

    score_rerank: float = Field(0, description="rerank score used in rerank stage")

    memory_type: str = Field("", description="conversation / observation / insight...")

    action_status: str = Field("none", description="new / content_modified / modified / deleted / none")

    store_status: str = Field("valid", description="store_status: valid / expired")

    vector: List[float] = Field([], description="content embedding result")

    timestamp: int = Field(default_factory=lambda: int(datetime.datetime.now().timestamp()),
                           description="timestamp of the memory node")

    dt: str = Field("", description="dt of the memory node")

    obs_reflected: int = Field(0, description="if the observation is reflected: 0/1")

    obs_updated: int = Field(0, description="if the observation has updated user profile or insight: 0/1")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dt = datetime.datetime.fromtimestamp(self.timestamp).strftime("%Y%m%d")

    @property
    def node_keys(self):
        return list(self.model_json_schema()["properties"].keys())

    def __getitem__(self, key: str):
        return self.model_dump().get(key)
