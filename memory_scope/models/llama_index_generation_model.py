import datetime
from typing import List, Dict

from llama_index.core.base.llms.types import ChatMessage, ChatResponse, CompletionResponse
from llama_index.llms.dashscope import DashScope

from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models.base_model import BaseModel, MODEL_REGISTRY
from memory_scope.models.model_response import ModelResponse, ModelResponseGen
from memory_scope.scheme.message import Message


class LlamaIndexGenerationModel(BaseModel):
    m_type: ModelEnum = ModelEnum.GENERATION_MODEL

    MODEL_REGISTRY.register("dashscope_generation", DashScope)

    def before_call(self, **kwargs) -> None:
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Message] | List[Dict[str, str]] = kwargs.pop("messages", [])

        if prompt:
            input_text = prompt
            input_type = "prompt"
            llama_input = input_text
        elif messages:
            input_text = messages
            input_type = "messages"
            llama_input = [ChatMessage(role=x["role"], content=x["content"]) for x in input_text]
        else:
            raise RuntimeError("prompt and messages is both empty!")

        self.data = {input_type: llama_input}

    def after_call(self,
                   model_response: ModelResponse,
                   stream: bool = False,
                   **kwargs) -> ModelResponse | ModelResponseGen:
        now_ts = datetime.datetime.now()
        model_response.message = Message(role=MessageRoleEnum.ASSISTANT,
                                         content="",
                                         time_created=int(now_ts.timestamp()))

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
        return results

    async def _async_call(self, **kwargs) -> ModelResponse:
        raise NotImplementedError
