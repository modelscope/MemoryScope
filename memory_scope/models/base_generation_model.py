from typing import List, Dict

#from llama_index.llms.dashscope import DashScope as DashScopeLLM
from llama_index.llms.dashscope import DashScope

from llama_index.core.base.llms.types import ChatMessage
from llama_index.core.base.llms.types import (
    ChatResponse,
    CompletionResponse,
)
from memory_scope.models import MODEL_REGISTRY
from memory_scope.models.base_model import BaseModel
from memory_scope.models.response import ModelResponse, ModelResponseGen
from memory_scope.utils.timer import Timer


class BaseGenerationModel(BaseModel):
    MODEL_REGISTRY.batch_register([
        DashScope,
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


class LLILLM(BaseGenerationModel):

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
        if isinstance(call_result, CompletionResponse):
            content = call_result.text
        elif isinstance(call_result, ChatResponse):
            content = call_result.message.content
        else:
            raise NotImplementedError
        
        return ModelResponse(text=content,
                             model_type="LLM")
    
    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:

        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse()
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

