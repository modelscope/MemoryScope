import time
from typing import List

from llama_index.core.base.llms.types import ChatMessage

from memoryscope.core.models.base_model import BaseModel, MODEL_REGISTRY
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.scheme.message import Message
from memoryscope.scheme.model_response import ModelResponse, ModelResponseGen


class DummyGenerationModel(BaseModel):
    """
    The `DummyGenerationModel` class serves as a placeholder model for generating responses.
    It processes input prompts or sequences of messages, adapting them into a structure compatible
    with chat interfaces. It also facilitates the generation of mock (dummy) responses for testing,
    supporting both immediate and streamed output.
    """
    m_type: ModelEnum = ModelEnum.GENERATION_MODEL

    MODEL_REGISTRY.register("dummy_generation", object)

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
        """
        Processes the model's response post-call, optionally streaming the output or returning it as a whole.

        This method modifies the input `model_response` by resetting its message content and, based on the `stream`
        parameter, either yields the response in a generated stream or returns the complete response directly.

        Args:
            model_response (ModelResponse): The initial response object to be processed.
            stream (bool, optional): Flag indicating whether to stream the response. Defaults to False.
            **kwargs: Additional keyword arguments (not used in this implementation).

        Returns:
            ModelResponse | ModelResponseGen: If `stream` is True, a generator yielding updated `ModelResponse` objects;
                                             otherwise, a modified `ModelResponse` object with the complete content.
        """
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

    def _call(self, model_response: ModelResponse, stream: bool = False, **kwargs):
        return model_response

    async def _async_call(self, model_response: ModelResponse, **kwargs):
        return model_response
