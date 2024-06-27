from typing import List

from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models.base_model import BaseModel, MODEL_REGISTRY
from memory_scope.models.model_response import ModelResponse


class LlamaIndexRankModel(BaseModel):
    m_type: ModelEnum = ModelEnum.RANK_MODEL

    MODEL_REGISTRY.register("dashscope_rank", DashScopeRerank)

    def before_call(self, **kwargs) -> None:
        assert "query" in kwargs or "documents" in kwargs
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])

        assert (
            query and documents
        ), f"query or documents is empty! query={query}, documents={len(documents)}"

        # using -1.0 as dummy scores
        nodes = [NodeWithScore(node=Node(text=doc), score=-1.0) for doc in documents]
        self._get_documents_mapping(documents)

        self.data = {
            "nodes": nodes,
            "query_str": query,
        }

    def after_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse:
        if not model_response.rank_scores:
            model_response.rank_scores = {}

        for node in model_response.raw:
            text = node.node.text
            idx = self.documents_map[text]
            model_response.rank_scores[idx] = node.score
        return model_response

    def _call(self, **kwargs) -> ModelResponse:
        return ModelResponse(
            m_type=self.m_type, raw=self.model.postprocess_nodes(**self.data)
        )

    async def _async_call(self, **kwargs) -> ModelResponse:
        raise NotImplementedError

    def _get_documents_mapping(self, documents):
        self.documents_map = {}
        for idx, doc in enumerate(documents):
            self.documents_map[doc] = idx
