from typing import List

from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

from memoryscope.core.models.base_model import BaseModel, MODEL_REGISTRY
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.scheme.model_response import ModelResponse
from memoryscope.core.utils.logger import Logger


class LlamaIndexEmbeddingModel(BaseModel):
    """
    Manages text embeddings utilizing the DashScopeEmbedding within the LlamaIndex framework,
    facilitating embedding operations for both sync and async modes, inheriting from BaseModel.
    """
    m_type: ModelEnum = ModelEnum.EMBEDDING_MODEL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = Logger.get_logger("llama_index_embedding_model")

    @classmethod
    def register_model(cls, model_name: str, model_class: type):
        """
        Registers a new embedding model class with the model registry.

        Args:
            model_name (str): The name to register the model under.
            model_class (type): The class of the model to register.
        """
        MODEL_REGISTRY.register(model_name, model_class)

    MODEL_REGISTRY.register("dashscope_embedding", DashScopeEmbedding)
    MODEL_REGISTRY.register("openai_embedding", OpenAIEmbedding)

    def before_call(self, model_response: ModelResponse, **kwargs):
        text: str | List[str] = kwargs.pop("text", "")
        if isinstance(text, str):
            text = [text]
        model_response.meta_data["data"] = dict(texts=text)
        self.logger.info("Embedding Model:\n" + text[0])

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

    def _call(self, model_response: ModelResponse, **kwargs):
        """
        Executes a synchronous call to generate embeddings for the input data.

        This method utilizes the `get_text_embedding_batch` method of the encapsulated model,
        passing the processed data from `self.data`. The result is then packaged into a
        `ModelResponse` object with the model type specified by `self.m_type`.

        Args:
            **kwargs: Additional keyword arguments that might be used in the embedding process.

        Returns:
            ModelResponse: An object containing the embedding results and the model type.
        """
        model_response.raw = self.model.get_text_embedding_batch(**model_response.meta_data["data"])

    async def _async_call(self, model_response: ModelResponse, **kwargs):
        """
        Executes an asynchronous call to generate embeddings for the input data.

        Similar to `_call`, but uses the asynchronous `aget_text_embedding_batch` method
        of the model. It handles the input data asynchronously and packages the result
        within a `ModelResponse` instance.

        Args:
            **kwargs: Additional keyword arguments for the embedding process, if any.

        Returns:
            ModelResponse: An object encapsulating the embedding output and the model's type.
        """
        model_response.raw = await self.model.aget_text_embedding_batch(**model_response.meta_data["data"])
