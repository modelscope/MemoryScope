from typing import List

from llama_index.core.base.llms.types import ChatMessage, ChatResponse, CompletionResponse
from llama_index.llms.dashscope import DashScope

from memoryscope.core.models.base_model import BaseModel, MODEL_REGISTRY
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.scheme.message import Message
from memoryscope.scheme.model_response import ModelResponse, ModelResponseGen


class LlamaIndexGenerationModel(BaseModel):
    """
    This class represents a generation model within the LlamaIndex framework,
    capable of processing input prompts or message histories, selecting an appropriate
    language model service from a registry, and generating text responses, with support
    for both streaming and non-streaming modes. It encapsulates logic for formatting
    these interactions within the context of a memory scope management system.
    """

    m_type: ModelEnum = ModelEnum.GENERATION_MODEL

    MODEL_REGISTRY.register("dashscope_generation", DashScope)

    def before_call(self, model_response: ModelResponse, **kwargs):
        """
        Prepares the input data before making a call to the language model.
        It accepts either a 'prompt' directly or a list of 'messages'.
        If 'prompt' is provided, it sets the data accordingly.
        If 'messages' are provided, it constructs a list of ChatMessage objects from the list.
        Raises an error if neither 'prompt' nor 'messages' are supplied.

        Args:
            model_response: model_response
            **kwargs: Arbitrary keyword arguments including 'prompt' and 'messages'.

        Raises:
            RuntimeError: When both 'prompt' and 'messages' inputs are not provided.
        """
        prompt: str = kwargs.pop("prompt", "")
        messages: List[Message] | List[dict] = kwargs.pop("messages", [])

        if prompt:
            data = {"prompt": prompt}
        elif messages:
            if isinstance(messages[0], dict):
                data = {"messages": [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]}
            else:
                data = {"messages": [ChatMessage(role=msg.role, content=msg.content) for msg in messages]}
        else:
            raise RuntimeError("prompt and messages are both empty!")
        data.update(**kwargs)
        model_response.meta_data["data"] = data

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

    def _call(self, model_response: ModelResponse, stream: bool = False, **kwargs):
        data = model_response.meta_data["data"]

        if "prompt" in data:
            if stream:
                model_response.raw = self.model.stream_complete(**data)
            else:
                model_response.raw = self.model.complete(**data)
        elif "messages" in data:
            if stream:
                model_response.raw = self.model.stream_chat(**data)
            else:
                model_response.raw = self.model.chat(**data)
        else:
            raise RuntimeError("prompt or messages is missing!")

    async def _async_call(self, model_response: ModelResponse, **kwargs):
        """
        Asynchronously calls the language model with the provided prompt or message history,
        and packages the raw response into a ModelResponse object.

        This method checks if the input data contains a 'prompt' or 'messages' key to decide
        which method to call on the model instance. It uses 'acomplete' for simple prompts and
        'achat' for chat-based message histories.

        Args:
            **kwargs: Additional keyword arguments that might be used in the model call.

        Returns:
            ModelResponse: An object containing the raw response from the language model.
        """
        data = model_response.meta_data["data"]

        if "prompt" in data:
            model_response.raw = await self.model.acomplete(**data)
        elif "messages" in data:
            model_response.raw = await self.model.achat(**data)
        else:
            raise RuntimeError("prompt or messages is missing!")
