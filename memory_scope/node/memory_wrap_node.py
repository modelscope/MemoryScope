from pydantic import Field, BaseModel

from model.memory_node import MemoryNode


class MemoryWrapNode(BaseModel):
    id: str = Field("", description="uuid64")

    score_similar: float = Field(0, description="相似度打分")

    score_rank: float = Field(0, description="排序打分")

    score_rerank: float = Field(0, description="重排打分")

    memory_node: MemoryNode = Field(None, description="memory node 核心，返回给上游的结构")

    @classmethod
    def init_from_es(cls, hit: dict):
        memory_node = MemoryNode(**hit['_source'])
        return cls(id=hit['_id'], score_similar=hit['_score'], memory_node=memory_node)

    @classmethod
    def init_from_attrs(cls, **kwargs):
        _id: str = kwargs.get("_id", "")
        score_similar: float = kwargs.pop("score_similar", 0)
        score_rank: float = kwargs.pop("score_rank", 0)
        score_rerank: float = kwargs.pop("score_rerank", 0)
        memory_node = MemoryNode(**kwargs)
        return cls(id=_id,
                   score_similar=score_similar,
                   score_rank=score_rank,
                   score_rerank=score_rerank,
                   memory_node=memory_node)
