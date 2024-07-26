from typing import List

from memoryscope.chat.base_memory_chat import BaseMemoryChat
from memoryscope.constants.language_constants import DEFAULT_HUMAN_NAME
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.memory.service.base_memory_service import BaseMemoryService
from memoryscope.memoryscope_context import MemoryscopeContext
from memoryscope.models.base_model import BaseModel
from memoryscope.scheme.message import Message
from memoryscope.scheme.model_response import ModelResponse, ModelResponseGen
from memoryscope.utils.prompt_handler import PromptHandler


class ApiMemoryChat(BaseMemoryChat):

    def __init__(self,
                 memory_service: str,
                 generation_model: str,
                 context: MemoryscopeContext,
                 human_name: str = None,
                 assistant_name: str = None,
                 **kwargs):

        super().__init__(**kwargs)

        self._memory_service: BaseMemoryService | str = memory_service
        self._generation_model: BaseModel | str = generation_model
        self.context: MemoryscopeContext = context
        self.generation_model_kwargs: dict = kwargs.pop("generation_model_kwargs", {})

        self.human_name: str = human_name
        if not self.human_name:
            self.human_name = DEFAULT_HUMAN_NAME[self.context.language]
        self.context.meta_data["human_name"] = self.human_name

        self.assistant_name: str = assistant_name
        if not self.assistant_name:
            self.assistant_name = "AI"
        self.context.meta_data["assistant_name"] = self.assistant_name

        self._prompt_handler: PromptHandler | None = None

    @property
    def prompt_handler(self) -> PromptHandler:
        """
        Lazy initialization property for the prompt handler.

        This property ensures that the `_prompt_handler` attribute is only instantiated when it is first accessed.
        It uses the current file's path and additional keyword arguments for configuration.

        Returns:
            PromptHandler: An instance of the PromptHandler configured for this CLI session.
        """
        if self._prompt_handler is None:
            self._prompt_handler = PromptHandler(__file__, prompt_file="memory_chat_prompt", **self.kwargs)
        return self._prompt_handler

    @property
    def memory_service(self) -> BaseMemoryService:
        """
        Property to access the memory service. If the service is initially set as a string,
        it will be looked up in the memory service dictionary of context, initialized,
        and then returned as an instance of `BaseMemoryService`. Ensures the memory service
        is properly started before use.

        Returns:
            BaseMemoryService: An active memory service instance.

        Raises:
            ValueError: If the declaration of memory service is not found in the memory service dictionary of context.
        """
        if isinstance(self._memory_service, str):
            if self._memory_service not in self.context.memory_service_dict:
                raise ValueError(f"Missing declaration of memory_service in context: {self._memory_service}")

            self._memory_service: BaseMemoryService = self.context.memory_service_dict[self._memory_service]
            # init service & update kwargs
            self._memory_service.init_service()
        return self._memory_service

    @property
    def generation_model(self) -> BaseModel:
        """
        Property to get the generation model. If the model is set as a string, it will be resolved from the global
        context's model dictionary.

        Raises:
            ValueError: If the declaration of generation model is not found in the model dictionary of context .

        Returns:
            BaseModel: An actual generation model instance.
        """
        if isinstance(self._generation_model, str):
            if self._generation_model not in self.context.model_dict:
                raise ValueError(f"Missing declaration of generation model in yaml config: {self._generation_model}")
            self._generation_model = self.context.model_dict[self._generation_model]
        return self._generation_model

    def get_new_message(self, query: str, role_name: str = "") -> Message:
        if not role_name:
            role_name = self.human_name
        return Message(role=MessageRoleEnum.USER.value, role_name=role_name, content=query)

    def get_system_message_with_memory(self, memories: str) -> Message:
        # Incorporate memory into the system prompt if available
        system_prompt = self.prompt_handler.system_prompt
        if memories:
            memory_prompt = self.prompt_handler.memory_prompt
            system_prompt = "\n".join([x.strip() for x in [system_prompt, memory_prompt, memories]])
        return Message(role=MessageRoleEnum.SYSTEM, content=system_prompt)

    def chat_with_memory(self,
                         query: str,
                         role_name: str = "",
                         remember_response: bool = True):

        chat_messages: List[Message] = []

        new_message: Message = self.get_new_message(query=query, role_name=role_name)

        # To retrieve memory, prepare the query timestamp and role name by adding new_message.
        memories: str = self.memory_service.retrieve_memory(query=new_message.content,
                                                            role_name=new_message.role_name,
                                                            timestamp=new_message.time_created)

        # format system_message with memories
        system_message: Message = self.get_system_message_with_memory(memories=memories)
        chat_messages.append(system_message)

        # Include past conversation history in the message list
        history_messages = self.memory_service.read_message()
        if history_messages:
            chat_messages.extend(history_messages)

        # Append the current user's message to the conversation context
        chat_messages.append(new_message)
        self.logger.info(f"chat_messages={chat_messages}")

        resp = self.generation_model.call(messages=chat_messages, stream=self.stream, **self.generation_model_kwargs)

        if self.stream:
            assert isinstance(resp, ModelResponseGen)
            model_response: ModelResponse | None = None
            for model_response in resp:
                yield model_response

            if remember_response:
                if model_response and model_response.message:
                    model_response.message.role_name = self.assistant_name
                    self.memory_service.add_messages([new_message, model_response.message])
                else:
                    self.logger.info("model_response or model_response.message is empty!")

        else:
            assert isinstance(resp, ModelResponse)
            model_response: ModelResponse = resp
            if remember_response:
                if model_response and model_response.message:
                    model_response.message.role_name = self.assistant_name
                    self.memory_service.add_messages([new_message, model_response.message])
                else:
                    self.logger.info("model_response or model_response.message is empty!")
            return model_response
