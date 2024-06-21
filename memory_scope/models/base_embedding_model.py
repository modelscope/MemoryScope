from typing import List, Dict
from llama_index.embeddings.dashscope import DashScopeEmbedding

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen


class BaseEmbeddingModel(BaseModel):
    MODEL_REGISTRY.batch_register([
        DashScopeEmbedding,
    ])

    def before_call(self, **kwargs) -> None:
        pass

    def after_call(self, model_response: ModelResponse | ModelResponseGen,
                   **kwargs) -> ModelResponse | ModelResponseGen:
        pass

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        pass

    async def _async_call(self, **kwargs) -> ModelResponse:
        pass


class LLIEmbedding(BaseEmbeddingModel):

    def before_call(self, **kwargs):
        text: str | List[str] = kwargs.pop("text", "")
        if isinstance(text, str):
            text = [text]
        self.data = dict(texts=text)

    def after_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse:
        embeddings = model_response.raw
        model_response.embedding_results = embeddings
        return model_response

    def _call(self, **kwargs) -> ModelResponse:
        results = ModelResponse()
        try:
            response = self.model.get_text_embedding_batch(**self.data)  
            results.raw = response
            results.status = True
        except Exception as e:
            results.details = e
            results.status = False
        return results
    

    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        :param kwargs:
        :return:
        """
        results = ModelResponse()
        try:
            response = self.model.aget_text_embedding_batch(**self.data)  
            results.raw = response
            results.status = True
        except Exception as e:
            results.details = e
            results.status = False
        return results

   