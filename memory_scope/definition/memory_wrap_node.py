from pydantic import Field, BaseModel

from memory_scope.definition.memory_node import MemoryNode


class MemoryWrapNode(BaseModel):
    id: str = Field("", description="uuid64")

    score_similar: float = Field(0, description="相似度打分")

    score_rank: float = Field(0, description="排序打分")

    score_rerank: float = Field(0, description="重排打分")

    memory_node: MemoryNode = Field(None, description="memory node 核心，返回给上游的结构")
