import datetime
from typing import List

from llama_index.core.base.llms.types import ChatMessage, ChatResponse, CompletionResponse
from llama_index.llms.dashscope import DashScope

from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models.base_model import BaseModel, MODEL_REGISTRY
from memory_scope.scheme.model_response import ModelResponse, ModelResponseGen
from memory_scope.scheme.message import Message


class LlamaIndexGenerationModel(BaseModel):
    m_type: ModelEnum = ModelEnum.GENERATION_MODEL

    MODEL_REGISTRY.register("dashscope_generation", DashScope)

    def before_call(self, **kwargs):
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Message] = kwargs.pop("messages", [])

        if prompt:
            self.data = {"prompt": prompt}
        elif messages:
            self.data = {"messages": [ChatMessage(role=msg.role, content=msg.content) for msg in messages]}
        else:
            raise RuntimeError("prompt and messages is both empty!")

    def after_call(self,
                   model_response: ModelResponse,
                   stream: bool = False,
                   **kwargs) -> ModelResponse | ModelResponseGen:
        model_response.message = Message(role=MessageRoleEnum.ASSISTANT, content="")

        call_result = model_response.raw
        if stream:
            def gen() -> ModelResponseGen:
                for response in call_result:
                    model_response.message.content += response.delta
                    model_response.delta = response.delta
                    yield model_response
            return gen()
        else:
            if isinstance(call_result, CompletionResponse):
                model_response.message.content = call_result.text
            elif isinstance(call_result, ChatResponse):
                model_response.message.content = call_result.message.content
            else:
                raise NotImplementedError

            return model_response

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)

        if "prompt" in self.data:
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
        return results

    async def _async_call(self, **kwargs) -> ModelResponse:
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)

        if "prompt" in self.data:
            response = await self.model.acomplete(**self.data)
        else:
            response = await self.model.achat(**self.data)
        results.raw = response
        return results

        raise NotImplementedError
