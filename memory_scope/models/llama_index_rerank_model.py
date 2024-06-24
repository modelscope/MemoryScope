from typing import List, Dict

from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore # type: ignore

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank
from memory_scope.enumeration.model_enum import ModelEnum



class LlamaIndexRerankModel(BaseModel):
    model_type: ModelEnum = ModelEnum.RANK_MODEL

    MODEL_REGISTRY.batch_register([
        DashScopeRerank
    ])

    def before_call(self, **kwargs) -> None:
        assert "query" in kwargs or "documents" in kwargs
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        
        assert query and documents, f"query or documents is empty! query={query}, documents={len(documents)}"
    
        # using -1.0 as dummy scores
        nodes = [NodeWithScore(node=Node(text=doc), score=-1.0) for doc in documents] 
        self._get_documents_mapping(documents)

        self.data = {
            "nodes": nodes,
            "query_str": query,
        }
        
    def after_call(self, model_response: ModelResponse, stream: bool = False, **kwargs) -> ModelResponse: 
        nodes = model_response.raw
        ranks = []
        for node in nodes:
            text = node.node.text
            idx = self.documents_map[text]
            ranks.append({idx: node.score})
        model_response.rank_scores = ranks
        return model_response

    def _call(self, **kwargs) -> ModelResponse:
        results = ModelResponse(model_type=self.model_type)
        try:
            response = self.model.postprocess_nodes(**self.data)    
            results.raw = response
            results.status = True
        except Exception as e:
            results.details = e
            results.status = False
        return results
    
    async def _async_call(self, **kwargs) -> ModelResponse:
        raise NotImplementedError
    
    def _get_documents_mapping(self, documents):
        self.documents_map = {}
        for idx, doc in enumerate(documents):
            self.documents_map[doc] = idx

