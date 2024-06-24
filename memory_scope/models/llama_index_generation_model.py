from typing import List, Dict

from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.base.llms.types import (
    ChatResponse,
    CompletionResponse,
)
from llama_index.llms.dashscope import DashScope

from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen


class LlamaIndexGenerationModel(BaseModel):
    model_type: ModelEnum = ModelEnum.GENERATION_MODEL

    MODEL_REGISTRY.batch_register([
        DashScope,
    ])

    def before_call(self, **kwargs) -> None:
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Dict[str, str]] = kwargs.pop("messages", [])

        if prompt:
            input_text = prompt
            input_type = 'prompt'
            llama_input = input_text
        elif messages:
            input_text = messages
            input_type = 'messages'
            llama_input = [ChatMessage(
                role=x['role'], content=x['content']
            ) for x in input_text]
        else:
            raise RuntimeError("prompt and messages is both empty!")

        self.data = {
            input_type: llama_input,
        }

    def after_call(
            self, model_response: ModelResponse, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        call_result = model_response.raw
        if stream:
            def gen() -> ModelResponseGen:
                content = ""
                for response in call_result:
                    delta = response.delta
                    content += delta
                    model_response.text = content
                    model_response.delta = delta
                    yield model_response
            return gen()
        else:
            if isinstance(call_result, CompletionResponse):
                content = call_result.text
            elif isinstance(call_result, ChatResponse):
                content = call_result.message.content
            else:
                raise NotImplementedError
            model_response.text = content
            return model_response

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:

        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(model_type=self.model_type)
        try:
            if 'prompt' in self.data:
                if stream:
                    response = self.model.stream_complete(**self.data)
                else:
                    response = self.model.complete(**self.data)
            else:
                if stream:
                    response = self.model.stream_chat(**self.data)
                else:
                    response = self.model.chat(**self.data)    
            results.raw = response
            results.status = True
        except Exception as e:
            results.status = False
            results.details = e
        return results

    async def _async_call(self, **kwargs) -> ModelResponse:
        raise NotImplementedError
