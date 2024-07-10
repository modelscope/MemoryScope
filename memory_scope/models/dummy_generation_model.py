import time
from typing import List

from llama_index.core.base.llms.types import ChatMessage

from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models.base_model import BaseModel, MODEL_REGISTRY
from memory_scope.scheme.message import Message
from memory_scope.scheme.model_response import ModelResponse, ModelResponseGen


class DummyGenerationModel(BaseModel):
    m_type: ModelEnum = ModelEnum.GENERATION_MODEL

    class DummyModel:
        pass

    MODEL_REGISTRY.register("dummy_generation", DummyModel)

    def before_call(self, **kwargs):
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Message] | List[dict] = kwargs.pop("messages", [])

        if prompt:
            self.data = {"prompt": prompt}
        elif messages:
            if isinstance(messages[0], dict):
                self.data = {"messages": [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]}
            else:
                self.data = {"messages": [ChatMessage(role=msg.role, content=msg.content) for msg in messages]}
        else:
            raise RuntimeError("prompt and messages is both empty!")

    def after_call(self,
                   model_response: ModelResponse,
                   stream: bool = False,
                   **kwargs) -> ModelResponse | ModelResponseGen:
        model_response.message = Message(role=MessageRoleEnum.ASSISTANT, content="")

        call_result = ["-" for _ in range(10)]
        if stream:
            def gen() -> ModelResponseGen:
                for delta in call_result:
                    model_response.message.content += delta
                    model_response.delta = delta
                    time.sleep(0.1)
                    yield model_response

            return gen()
        else:
            model_response.message.content = "".join(call_result)
            return model_response

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)
        return results

    async def _async_call(self, **kwargs) -> ModelResponse:
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)
        return results
