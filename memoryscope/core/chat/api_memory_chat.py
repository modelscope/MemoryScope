from typing import List, Optional, Literal

from memoryscope.constants.common_constants import MEMORIES
from memoryscope.constants.language_constants import DEFAULT_HUMAN_NAME, USER_NAME_EXPRESSION
from memoryscope.core.chat.base_memory_chat import BaseMemoryChat
from memoryscope.core.memoryscope_context import MemoryscopeContext
from memoryscope.core.models.base_model import BaseModel
from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.datetime_handler import DatetimeHandler
from memoryscope.core.utils.prompt_handler import PromptHandler
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.scheme.message import Message
from memoryscope.scheme.model_response import ModelResponse, ModelResponseGen


class ApiMemoryChat(BaseMemoryChat):

    def __init__(self,
                 memory_service: str,
                 generation_model: str,
                 context: MemoryscopeContext,
                 stream: bool = False,
                 **kwargs):

        super().__init__(**kwargs)

        self._memory_service: BaseMemoryService | str = memory_service
        self._generation_model: BaseModel | str = generation_model
        self.context: MemoryscopeContext = context
        self.stream: bool = stream
        self.generation_model_kwargs: dict = kwargs.pop("generation_model_kwargs", {})

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
            self._prompt_handler = PromptHandler(__file__,
                                                 language=self.context.language,
                                                 prompt_file="memory_chat_prompt",
                                                 **self.kwargs)
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
    def human_name(self):
        return self.memory_service.human_name

    @property
    def assistant_name(self):
        return self.memory_service.assistant_name

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

    def iter_response(self,
                      remember_response: bool,
                      resp: ModelResponseGen,
                      memories: str,
                      query_message: Message) -> ModelResponseGen:

        model_response: ModelResponse | None = None
        for model_response in resp:
            yield model_response

        if remember_response:
            if model_response and model_response.message:
                model_response.message.role_name = self.assistant_name
                model_response.meta_data[MEMORIES] = memories
                self.memory_service.add_messages_pair([query_message, model_response.message])
            else:
                self.logger.warning("model_response or model_response.message is empty!")

    def chat_with_memory(self,
                         query: str,
                         role_name: Optional[str] = None,
                         system_prompt: Optional[str] = None,
                         memory_prompt: Optional[str] = None,
                         temporary_memories: Optional[str] = None,
                         history_message_strategy: Literal["auto", None] | int = "auto",
                         remember_response: bool = True,
                         **kwargs):

        chat_messages: List[Message] = []

        # prepare query message
        if not role_name:
            role_name = self.human_name
        query_message = Message(role=MessageRoleEnum.USER.value, role_name=role_name, content=query)

        # To retrieve memory, prepare the query timestamp and role name by adding query_message.
        memories: str = self.memory_service.retrieve_memory(query=query_message.content,
                                                            role_name=query_message.role_name,
                                                            timestamp=query_message.time_created)

        # format system_message with memories
        system_prompt_list = []
        if system_prompt:
            system_prompt_list.append(system_prompt)
        else:
            dt_handler = DatetimeHandler()
            date_time = dt_handler.datetime_format("%Y-%m-%d %H:%M:%S")
            weekday = dt_handler.get_dt_info_dict(self.context.language)["weekday"]
            system_prompt_list.append(self.prompt_handler.system_prompt.format(date_time=f"{date_time} {weekday}"))

        if memories:
            # add memory prompt
            if memory_prompt:
                system_prompt_list.append(memory_prompt)
            else:
                system_prompt_list.append(self.prompt_handler.memory_prompt)

            if self.human_name != DEFAULT_HUMAN_NAME[self.context.language]:
                system_prompt_list.append(USER_NAME_EXPRESSION[self.context.language].format(name=self.human_name))
            system_prompt_list.append(memories)

        if temporary_memories:
            system_prompt_list.extend(temporary_memories)

        system_prompt_join = "\n".join([x.strip() for x in system_prompt_list])
        system_message = Message(role=MessageRoleEnum.SYSTEM, content=system_prompt_join)
        chat_messages.append(system_message)

        # Include past conversation history in the message list
        if history_message_strategy:
            history_messages = []

            if history_message_strategy == "auto":
                history_messages = self.memory_service.read_message()

            elif isinstance(history_message_strategy, int):
                history_messages = self.memory_service.get_chat_messages_scatter(history_message_strategy)

            if history_messages:
                assert isinstance(history_messages[0], Message)
                chat_messages.extend(history_messages)

        # Append the current user's message to the conversation context
        chat_messages.append(query_message)
        self.logger.info(f"chat_messages={chat_messages}")

        resp = self.generation_model.call(messages=chat_messages, stream=self.stream, **self.generation_model_kwargs)
        if self.stream:
            return self.iter_response(remember_response, resp, memories, query_message)

        else:
            model_response: ModelResponse = resp
            if remember_response:
                if model_response and model_response.message:
                    model_response.message.role_name = self.assistant_name
                    model_response.meta_data[MEMORIES] = memories
                    self.memory_service.add_messages_pair([query_message, model_response.message])
                else:
                    self.logger.warning("model_response or model_response.message is empty!")
            return model_response
