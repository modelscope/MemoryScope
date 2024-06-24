from typing import List, Dict

from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore # type: ignore

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank


class BaseRankModel(BaseModel):
    MODEL_REGISTRY.batch_register([
        DashScopeRerank
    ])

    def before_call(self, **kwargs) -> None:
        pass

    def after_call(self, **kwargs) -> ModelResponse:
        pass

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse:
        pass

    async def _async_call(self, **kwargs) -> ModelResponse:
        pass


class LLIReRank(BaseRankModel):
   
    def before_call(self, **kwargs) -> None:
        assert "query" in kwargs or "documents" in kwargs
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        
        assert query and documents, f"query or documents is empty! query={query}, documents={len(documents)}"
    
        # using -1.0 as dummy scores
        nodes = [NodeWithScore(node=Node(text=text), score=-1.0) for text in documents] 

        self.data = {
            "nodes": nodes,
            "query_str": query,
        }
        
    def after_call(self, model_response: ModelResponse, stream: bool = False, **kwargs) -> ModelResponse: 
        nodes = model_response.raw
        ranks = list()
        for node in nodes:
            ranks.append(dict(relevance_score=node.score,
                                document=node.node.text))
        results = ModelResponse(rank_scores=ranks)
        return results

    def _call(self, **kwargs) -> ModelResponse:
        results = ModelResponse()
        try:
            response = self.model.postprocess_nodes(**self.data)    
            results.raw = response
            results.status = True
        except Exception as e:
            results.details = e
            results.status = False
        return results
