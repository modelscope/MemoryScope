from llama_index.llms.dashscope import DashScope as DashScopeLLM

from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen


class BaseGenerationModel(BaseModel):
    MODEL_REGISTRY.batch_register([
        DashScopeLLM
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
