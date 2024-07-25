import time
from typing import List

from llama_index.core.base.llms.types import ChatMessage

from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.models.base_model import BaseModel, MODEL_REGISTRY
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

    class DummyModel:
        """
        An inner class representing the dummy model placeholder.
        """
        pass

    MODEL_REGISTRY.register("dummy_generation", DummyModel)

    def before_call(self, **kwargs):
        """
        Prepares the input data before making a call to the model's generate function.
        Accepts either a 'prompt' or a list of 'messages'. If both are provided or missing, 
        a RuntimeError is raised. Transforms the input into a standardized format for processing.

        Args:
            **kwargs: Arbitrary keyword arguments including 'prompt' or 'messages'.
        
        Raises:
            RuntimeError: If neither 'prompt' nor 'messages' is provided, or both are provided.
        """
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
            raise RuntimeError("Both 'prompt' and 'messages' are empty!")

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
                    time.sleep(0.1)  # ⭐ Introduce a delay to simulate streaming
                    yield model_response

            return gen()
        else:
            model_response.message.content = "".join(call_result)  # ⭐ Concatenate results for non-streaming
            return model_response

    def _call(self, stream: bool = False, **kwargs) -> ModelResponse | ModelResponseGen:
        """
        Generates a dummy response based on the input data, supporting both immediate
        and streamed response types.

        Args:
            stream (bool, optional): If True, indicates the response should be generated
                                     in a streaming manner. Defaults to False.
            **kwargs: Additional keyword arguments not used in this dummy implementation.

        Returns:
            Union[ModelResponse, ModelResponseGen]: A dummy response object or a generator
                                                    object capable of streaming responses.
        """
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)
        return results

    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        Asynchronous version of `_call`, providing the same functionality but designed
        to be used in asynchronous contexts.

        Args:
            **kwargs: Additional keyword arguments not used in this dummy implementation.

        Returns:
            ModelResponse: A dummy response object suitable for asynchronous use.
        """
        assert "prompt" in self.data or "messages" in self.data
        results = ModelResponse(m_type=self.m_type)
        return results
