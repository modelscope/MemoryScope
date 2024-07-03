import os
import time

import questionary

from memory_scope.chat.base_memory_chat import BaseMemoryChat
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
    USER_COMMANDS = {
        "exit": "exit the CLI",
        "clear": "clear commands",
        "help": "get cli commands help",
        "stream": "get stream response"
    }

    def __init__(self,
                 memory_service: str,
                 generation_model: str,
                 stream: bool = True,
                 human_name: str = "",
                 assistant_name: str = "",
                 **kwargs):

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
        if self._prompt_handler is None:
            self._prompt_handler = PromptHandler(__file__, **self.kwargs)
        return self._prompt_handler

    def print_logo(self):
        for line in self._logo:
            print(line)

    @property
    def memory_service(self) -> BaseMemoryService:
        if isinstance(self._memory_service, str):
            if self._memory_service not in G_CONTEXT.memory_service_dict:
                raise ValueError("Missing declaration of memory_service in yaml configuration: " + self._memory_service)
            self._memory_service = G_CONTEXT.memory_service_dict[self._memory_service]
            self._memory_service.start_service()
        return self._memory_service

    @property
    def generation_model(self) -> BaseModel:
        if isinstance(self._generation_model, str):
            if self._generation_model not in G_CONTEXT.model_dict:
                raise ValueError("Missing declaration of generation model in yaml configuration: " + self._generation_model)
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]
        return self._generation_model

    @property
    def system_prompt_with_memory(self) -> Message:
        system_prompt = self.prompt_handler.system_prompt

        memories: str = self.memory_service.read_memory()
        if memories:
            memory_prompt = self.prompt_handler.memory_prompt
            system_prompt = "\n".join([x.strip() for x in [system_prompt, memory_prompt, memories]])

        return Message(role=MessageRoleEnum.SYSTEM, content=system_prompt)

    def chat_with_memory(self, query: str) -> ModelResponse | ModelResponseGen:
        new_message: Message = Message(role=MessageRoleEnum.USER.value, role_name=self.human_name, content=query)
        self.memory_service.add_messages(new_message)
        return self.generation_model.call(messages=[self.system_prompt_with_memory, new_message], stream=self.stream)

    @staticmethod
    def parse_query_command(query: str):
        query_split = query.lstrip("/").lower().split(" ")
        command = query_split[0]
        args = query_split[1:]
        kwargs = {}
        for arg in args:
            if not args:
                continue
            arg_split = arg.split("=")
            if len(arg_split) >= 2:
                k = arg_split[0]
                v = arg_split[1]
                if k and v:
                    kwargs[k] = v
        return command, kwargs

    def process_commands(self, query: str) -> bool:
        continue_run = True
        command, kwargs = self.parse_query_command(query)

        if command == "exit":
            self.memory_service.stop_service()
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
                while True:
                    time.sleep(refresh_time)
                    result = self.memory_service.do_operation(op_name=command, **kwargs)
                    os.system("clear")
                    self.print_logo()
                    questionary.print(result)
            else:
                result = self.memory_service.do_operation(op_name=command, **kwargs)
                questionary.print(result)

        else:
            questionary.print(f"Unknown command={command} received.")

        return continue_run

    def run(self):
        self.print_logo()
        self.USER_COMMANDS.update(self.memory_service.op_description_dict)

        while True:
            try:
                query = questionary.text(message=f"{self.human_name}:", multiline=False, qmark=">").unsafe_ask()
                if not query:
                    continue

                query: str = query.strip()

                # handle cli / commands with memory ops
                if query.startswith("/"):
                    if self.process_commands(query=query):
                        continue
                    else:
                        break

                questionary.print("> ", end="", style="fg:yellow")
                questionary.print(f"{self.assistant_name}: ", end="", style="bold")

                if self.stream:
                    model_response = None
                    for model_response in self.chat_with_memory(query=query):
                        questionary.print(model_response.delta, end="")
                    questionary.print("")

                else:
                    model_response = self.chat_with_memory(query=query)
                    questionary.print(model_response.message.content)

                model_response.message.role_name = self.assistant_name
                self.memory_service.add_messages(model_response.message)

            except KeyboardInterrupt:
                questionary.print("User interrupt occurred.")
                is_exit = questionary.confirm("continue exit").unsafe_ask()
                if is_exit:
                    self.memory_service.stop_service()
                    break

            except Exception as e:
                import traceback
                traceback.print_exc()
                line = f"An exception occurred when running cli memory chat. args={e.args}."
                questionary.print(line)
                self.logger.exception(line)
                continue

        questionary.print(f"A memory writing thread is still running, please be patient and wait!")
