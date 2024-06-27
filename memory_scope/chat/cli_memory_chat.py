import datetime
import os
import time
from typing import List

import questionary

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.chat.global_context import G_CONTEXT
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.models.base_model import BaseModel
from memory_scope.prompts.memory_chat_prompt import MEMORY_PROMPT, SYSTEM_PROMPT
from memory_scope.scheme.message import Message
from memory_scope.scheme.model_response import ModelResponse, ModelResponseGen
from memory_scope.utils.logger import Logger
from memory_scope.utils.tool_functions import char_logo


class CliMemoryChat(BaseMemoryChat):
    USER_COMMANDS = {
        "exit": "exit the CLI",
        "help": "get cli commands help",
        "stream": "get stream response"
    }

    def __init__(self, memory_service: str, generation_model: str, stream: bool = True, **kwargs):
        self._memory_service: BaseMemoryService | str = memory_service
        self._generation_model: BaseModel | str = generation_model
        self.stream: bool = stream
        self.kwargs: dict = kwargs

        self._logo = char_logo("MemoryScope")
        self.logger = Logger.get_logger()

    def print_logo(self):
        for line in self._logo:
            print(line)

    @property
    def memory_service(self) -> BaseMemoryService:
        if isinstance(self._memory_service, str):
            self._memory_service = G_CONTEXT.memory_service_dict[self._memory_service]
            self._memory_service.start_service()
        return self._memory_service

    @property
    def generation_model(self) -> BaseModel:
        if isinstance(self._generation_model, str):
            self._generation_model = G_CONTEXT.model_dict[self._generation_model]
        return self._generation_model

    @staticmethod
    def get_system_prompt(related_memories: List[str], time_created: int) -> Message:
        system_prompt = SYSTEM_PROMPT[G_CONTEXT.language]
        if related_memories:
            memory_prompt = MEMORY_PROMPT[G_CONTEXT.language]
            all_prompt_list = [system_prompt, memory_prompt]
            all_prompt_list.extend(related_memories)
            system_prompt = "\n".join([x.strip() for x in all_prompt_list])
        return Message(role=MessageRoleEnum.SYSTEM, content=system_prompt, time_created=time_created)

    def chat_with_memory(self, query: str) -> ModelResponse | ModelResponseGen:
        query = query.strip()
        if not query:
            return

        time_created = int(datetime.datetime.now().timestamp())
        new_message: Message = Message(role=MessageRoleEnum.USER, content=query, time_created=time_created)
        self.memory_service.add_messages(new_message)
        related_memories: List[str] = self.memory_service.read_memory()
        system_message: Message = self.get_system_prompt(related_memories, time_created)
        result = self.generation_model.call(messages=[system_message, new_message], stream=self.stream)
        if self.stream:
            for _ in result:
                yield _
        else:
            return result

    def process_commands(self, query: str) -> bool:
        continue_run = True
        query_split = query.lstrip("/").lower().split(" ")
        query = query_split[0]
        args = query_split[1:]
        if query == "exit":
            self.memory_service.stop_service()
            continue_run = False

        elif query == "help":
            questionary.print("CLI commands", "bold")
            for cmd, desc in self.USER_COMMANDS.items():
                questionary.print(text=f" /{cmd}:", style="bold")
                questionary.print(text=f"  {desc}")

        elif query == "stream":
            self.stream = bool(args[0])
            questionary.print(f"stream: {self.stream}")

        elif query in self.memory_service.op_description_dict:
            if not args:
                result = self.memory_service.do_operation(op_name=query)
                questionary.print(result)

            elif args[0].isdigit():
                refresh_time = int(args[0])
                while True:
                    time.sleep(refresh_time)
                    result = self.memory_service.do_operation(op_name=query)
                    os.system('clear')
                    self.print_logo()
                    questionary.print(result)

            else:
                questionary.print("unknown command received. Please try again!")

        else:
            questionary.print("unknown command received. Please try again!")

        return continue_run

    def run(self):
        self.print_logo()
        self.USER_COMMANDS.update(self.memory_service.op_description_dict)

        while True:
            try:
                query = questionary.text(message="user:", multiline=False, qmark=">").unsafe_ask()
                if not query:
                    continue

                query: str = query.strip()

                # handle cli / commands with memory ops
                if query.startswith("/"):
                    if self.process_commands(query=query):
                        continue
                    else:
                        break

                msg = None
                questionary.print("> ", end="", style="fg:yellow")
                questionary.print("assistant: ", end="", style="bold")
                if self.stream:
                    for msg in self.chat_with_memory(query=query):
                        questionary.print(msg.delta, end="")
                    questionary.print("")
                else:
                    msg = self.chat_with_memory(query=query)
                    questionary.print(msg.message.content)
                self.memory_service.add_messages(msg.message)

            except KeyboardInterrupt:
                questionary.print("User interrupt occurred.")
                is_exit = questionary.confirm("continue exit").unsafe_ask()
                if is_exit:
                    self.memory_service.stop_service()
                    break

            except Exception as e:
                line = f"An exception occurred when running cli memory chat. args={e.args}"
                questionary.print(line)
                self.logger.exception(line)
                continue

        questionary.print(f"A memory writing thread is still running, please be patient and wait!")
