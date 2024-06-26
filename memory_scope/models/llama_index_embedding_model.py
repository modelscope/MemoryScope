from typing import List

from llama_index.embeddings.dashscope import DashScopeEmbedding

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen
from memory_scope.enumeration.model_enum import ModelEnum


class LlamaIndexEmbeddingModel(BaseModel):
    m_type: ModelEnum = ModelEnum.EMBEDDING_MODEL

    MODEL_REGISTRY.batch_register(
        [
            DashScopeEmbedding,
        ]
    )

    def before_call(self, **kwargs):
        text: str | List[str] = kwargs.pop("text", "")
        if isinstance(text, str):
            text = [text]
        self.data = dict(texts=text)

    def after_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse:
        embeddings = model_response.raw
        if not embeddings:
            model_response.details = "empty embeddings"
            model_response.status = False
            return model_response

        if len(embeddings) == 1:
            # return list[float]
            embeddings = embeddings[0]

        model_response.embedding_results = embeddings
        return model_response

    def _call(self, **kwargs) -> ModelResponse:
        """
        :param kwargs:
        :return:
        """
        return ModelResponse(
            m_type=self.m_type, raw=self.model.get_text_embedding_batch(**self.data)
        )

    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        :param kwargs:
        :return:
        """
        return ModelResponse(
            m_type=self.m_type,
            raw=await self.model.aget_text_embedding_batch(**self.data),
        )
