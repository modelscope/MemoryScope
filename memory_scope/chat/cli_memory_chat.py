import os
import time
from typing import List

import questionary

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.constants.language_constants import DEFAULT_HUMAN_NAME
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.message import Message
from memory_scope.scheme.model_response import ModelResponse, ModelResponseGen
from memory_scope.utils.global_context import G_CONTEXT
from memory_scope.utils.logger import Logger
from memory_scope.utils.prompt_handler import PromptHandler
from memory_scope.utils.tool_functions import char_logo


class CliMemoryChat(BaseMemoryChat):
    """
    Command-line interface for chatting with an AI that integrates memory functionality.
    Allows users to interact, manage chat history, adjust streaming settings, and view commands' help.
    """
    USER_COMMANDS = {
        "exit": "Exit the CLI.",
        "clear": "Clear the command history.",
        "help": "Display available CLI commands and their descriptions.",
        "stream": "Toggle between getting streamed responses from the model."
    }

    def __init__(self,
                 memory_service: str,
                 generation_model: str,
                 stream: bool = True,
                 human_name: str = DEFAULT_HUMAN_NAME[G_CONTEXT.language],
                 assistant_name: str = "AI",
                 **kwargs):
        """
        Initializes the CLI chat instance with specified services, models, and personalized settings.

        Args:
            memory_service (str | BaseMemoryService): The memory service to be used for storing conversation history.
            generation_model (str | BaseModel): The model responsible for generating AI responses.
            stream (bool, optional): Flag indicating whether responses should be streamed. Defaults to True.
            human_name (str, optional): The name assigned to the human user. Defaults to a language-specific default.
            assistant_name (str, optional): The name of the AI assistant. Defaults to "AI".
            **kwargs: Additional keyword arguments for flexibility or future extensions.

        Side Effects:
            - Updates global context with human and AI names.
            - Initializes logging for the instance.
        """
        self._memory_service: BaseMemoryService | str = memory_service
        self._generation_model: BaseModel | str = generation_model
        self.stream: bool = stream
        self.human_name: str = human_name
        self.assistant_name: str = assistant_name
        self.kwargs: dict = kwargs

        self._logo = char_logo("MemoryScope")
        self._prompt_handler: PromptHandler | None = None
        G_CONTEXT.meta_data.update({
            "human_name": human_name,
            "assistant_name": assistant_name,
        })

        self.logger = Logger.get_logger()

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
            self._prompt_handler = PromptHandler(__file__, **self.kwargs)
        return self._prompt_handler

    def print_logo(self):
        """
        Prints the logo of the CLI application to the console.

        The logo is composed of multiple lines, which are iterated through
        and printed one by one to provide a visual identity for the chat interface.
        """
        for line in self._logo:
            print(line)

    @property
    def memory_service(self) -> BaseMemoryService:
        """
        Property to access the memory service. If the service is initially set as a string,
        it will be looked up in the global context's memory service dictionary, initialized,
        and then returned as an instance of `BaseMemoryService`. Ensures the memory service
        is properly started before use.

        Returns:
            BaseMemoryService: The active memory service instance.

        Raises:
            ValueError: If the memory service string reference is not found in the global context's dictionary.
        """
        if isinstance(self._memory_service, str):
            if self._memory_service not in G_CONTEXT.memory_service_dict:
                raise ValueError("Missing declaration of memory_service in yaml configuration: " + self._memory_service)
            self._memory_service = G_CONTEXT.memory_service_dict[self._memory_service]
            self._memory_service.init_service()
            self._memory_service.start_backend_service()
        return self._memory_service

    @property
    def generation_model(self) -> BaseModel:
        """
        Property to get the generation model. If the model is set as a string, it will be resolved from the global
        context's model dictionary.

        Raises:
            ValueError: If the model string is not found in the global context's model dictionary.

        Returns:
            BaseModel: The actual generation model instance.
        """
        if isinstance(self._generation_model, str):
            if self._generation_model not in G_CONTEXT.model_dict:
                raise ValueError(f"Missing declaration of generation model in yaml config: {self._generation_model}")
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]
        return self._generation_model

    def chat_with_memory(self, query: str, remember_response: bool = False) -> ModelResponse | ModelResponseGen:
        """
        Engages in a conversation with the AI model, utilizing conversation memory.
        The function sends the user's query, incorporates conversation history and memory,
        and optionally remembers the AI's response based on the user's preference.

        Args:
            query (str): The user's input or query for the AI.
            remember_response (bool, optional): Flag indicating whether to save the AI's response to memory.
                Defaults to False.

        Returns:
        - ModelResponse: In non-streaming mode, returns the complete AI response.
        - ModelResponseGen: In streaming mode, returns a generator yielding AI response parts.

        Side Effects:
            - Updates the conversation memory with the user's query and (optionally) the AI's response.
            - Retrieves and includes historical messages and memory content in the conversation context.
        """
        new_message: Message = Message(role=MessageRoleEnum.USER.value, role_name=self.human_name, content=query)
        self.memory_service.add_messages(new_message)

        messages: List[Message] = []

        # Incorporate memory into the system prompt if available
        system_prompt = self.prompt_handler.system_prompt
        memories: str = self.memory_service.read_memory()
        if memories:
            memory_prompt = self.prompt_handler.memory_prompt
            system_prompt = "\n".join([x.strip() for x in [system_prompt, memory_prompt, memories]])
        messages.append(Message(role=MessageRoleEnum.SYSTEM, content=system_prompt))

        # Include past conversation history in the message list
        history_messages = self.memory_service.read_message()
        if history_messages:
            messages.extend(history_messages)

        # Append the current user's message to the conversation context
        messages.append(new_message)
        self.logger.info(f"messages={messages}")

        # Invoke the Language Model with the constructed message context, respecting streaming setting
        generated = self.generation_model.call(messages=messages, stream=self.stream)

        # In non-streaming interactions, explicitly save the AI's reply to memory if instructed
        if remember_response:
            assert not self.stream  # Ensure we're not in streaming mode when remembering responses
            generated.message.role_name = self.assistant_name
            self.memory_service.add_messages(generated.message)

        # Return the AI's response directly or as a generator based on the streaming mode
        return generated

    @staticmethod
    def parse_query_command(query: str):
        """
        Parses the user's input query command, separating it into the command and its associated keyword arguments.

        Args:
            query (str): The raw input string from the user which includes the command and its arguments.

        Returns:
            tuple: A tuple containing the command (str) as the first element and a dictionary (kwargs) of keyword
            arguments as the second element.
        """
        query_split = query.lstrip("/").lower().split(" ")  # Split and preprocess the input command
        command = query_split[0]  # Extract the command
        args = query_split[1:]  # Extract the arguments following the command
        kwargs = {}  # Initialize dictionary to hold keyword arguments

        for arg in args:
            # Skip if no arguments exist (unnecessary check due to prior assignment, but retained as per original)
            if not args:
                continue
            arg_split = arg.split("=")  # Split argument into key-value pair
            if len(arg_split) >= 2:  # Ensure there's both a key and value
                k = arg_split[0]  # Extract key
                v = arg_split[1]  # Extract value
                if k and v:  # Only add to kwargs if both key and value are non-empty
                    kwargs[k] = v

        return command, kwargs  # Return the parsed command and keyword arguments

    def process_commands(self, query: str) -> bool:
        """
        Parses and executes commands from user input in the CLI chat interface.
        Supports operations like exiting, clearing screen, showing help, toggling stream mode,
        executing predefined memory operations, and handling unknown commands.

        Args:
            query (str): The user's input command string.

        Returns:
        bool: Indicates whether to continue running the CLI after processing the command.
        """
        continue_run = True
        command, kwargs = self.parse_query_command(query)

        if command == "exit":
            self.memory_service.stop_backend_service()
            continue_run = False

        elif command == "clear":
            os.system("clear")

        elif command == "help":
            questionary.print("CLI commands", "bold")
            for cmd, desc in self.USER_COMMANDS.items():
                questionary.print(text=f" /{cmd}:", style="bold")
                questionary.print(text=f"  {desc}")

        elif command == "stream":
            self.stream = not self.stream
            questionary.print(f"set stream: {self.stream}")

        elif command in self.memory_service.op_description_dict:
            refresh_time = kwargs.pop("refresh_time", "")
            if refresh_time and refresh_time.isdigit():
                refresh_time = int(refresh_time)
                self.memory_service.stop_backend_service()
                while True:
                    result = self.memory_service.do_operation(op_name=command, **kwargs)
                    os.system("clear")
                    self.print_logo()
                    if result:
                        questionary.print(result)
                    else:
                        questionary.print(f"command={command} result is empty! kwargs={kwargs}")
                    time.sleep(refresh_time)

            else:
                result = self.memory_service.do_operation(op_name=command, **kwargs)
                if result:
                    questionary.print(result)
                else:
                    questionary.print(f"command={command} result is empty! kwargs={kwargs}")

        else:
            questionary.print(f"Unknown command={command} received.")

        return continue_run

    def run(self):
        """
        Runs the CLI chat loop, which handles user input, processes commands,
        communicates with the AI model, manages conversation memory, and controls
        the chat session including streaming responses, command execution, and error handling.
        
        The loop continues until the user explicitly chooses to exit.
        """
        self.print_logo()
        self.USER_COMMANDS.update(self.memory_service.op_description_dict)

        while True:
            try:
                query = questionary.text(message=f"{self.human_name}:", multiline=False, qmark=">").unsafe_ask()
                if not query:
                    continue

                query: str = query.strip()

                # Handle special commands prefixed with '/'
                if query.startswith("/"):
                    if self.process_commands(query=query):
                        continue
                    else:
                        break

                # Print prompt for AI's response
                questionary.print("> ", end="", style="fg:yellow")
                questionary.print(f"{self.assistant_name}: ", end="", style="bold")

                # Fetch and display AI's response, with support for streaming
                self.memory_service.start_backend_service()
                if self.stream:
                    model_response = None
                    for model_response in self.chat_with_memory(query=query):
                        questionary.print(model_response.delta, end="")
                    questionary.print("")

                else:
                    model_response = self.chat_with_memory(query=query)
                    questionary.print(model_response.message.content)

                # Append AI's response to the conversation memory
                model_response.message.role_name = self.assistant_name
                self.memory_service.add_messages(model_response.message)

            except KeyboardInterrupt:
                # Handle user interruption and confirm exit
                questionary.print("User interrupt occurred.")
                is_exit = questionary.confirm("Continue exit?").unsafe_ask()
                if is_exit:
                    self.memory_service.stop_backend_service()
                    break

            except Exception as e:
                # Log and handle any unanticipated exceptions
                import traceback
                traceback.print_exc()
                self.logger.exception(f"An exception occurred when running cli memory chat. args={e.args}.")
                continue
