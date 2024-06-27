import datetime
import time
from typing import Dict, List

import questionary
from memory_scope.chat_v2.base_memory_chat import BaseMemoryChat
from memory_scope.chat_v2.global_context import G_CONTEXT
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.models.base_model import BaseModel
from memory_scope.prompts.memory_chat_prompt import MEMORY_PROMPT, SYSTEM_PROMPT
from memory_scope.scheme.message import Message
from ..models.model_response import ModelResponse, ModelResponseGen


class CliMemoryChat(BaseMemoryChat):
    USER_COMMANDS = {
        "exit": "exit the CLI",
        "help": "get cli commands help",
        "stream": "get stream response"
    }

    def __init__(self, memory_service: str, generation_model: str, **kwargs):
        super().__init__(**kwargs)
        self._memory_service: BaseMemoryService | str = memory_service
        self._generation_model: BaseModel | str = generation_model
        self.stream: bool = True

    @property
    def memory_service(self) -> BaseMemoryService:
        if isinstance(self._memory_service, str):
            self._memory_service = G_CONTEXT.memory_service_dict[self._memory_service]
            self._memory_service.prepare_service()
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
        self.submit_messages(new_message)
        related_memories: List[str] = self.memory_service.read_memory()
        system_message: Message = self.get_system_prompt(related_memories, time_created)
        if self.stream:
            for result in self.generation_model.call(messages=[system_message, new_message], stream=self.stream):
                yield result

        self.submit_messages(result.text)

    def run(self):
        op_description_dict: Dict[str, str] = self.memory_service.get_op_description_dict()
        self.USER_COMMANDS.update({f"/{k}": v for k, v in op_description_dict.items()})

        while True:
            query = questionary.text(
                "Please enter your message or command:",
                multiline=False,
                qmark=">",
            ).ask()

            query: str = query.rstrip()

            if query == "":
                print("Empty input received. Please try again!")
                continue

            # handle cli / commands with memory ops
            if query.startswith("/"):
                query_split = query.lstrip("/").lower().split(" ")
                query = query_split[0]
                args = query_split[1:]
                if query == "exit":
                    break
                elif query == "help":
                    questionary.print("CLI commands", "bold")
                    for cmd, desc in self.USER_COMMANDS.items():
                        questionary.print(cmd, "bold")
                        print(f" {desc}")
                elif query == "stream":
                    questionary.print(f"stream: {self.stream}")
                    self.stream = ~self.stream
                elif query in op_description_dict:
                    if not args:
                        result = self.memory_service.do_operation(op_name=query)
                        print(result)

                    elif args[0].isdigit():
                        refresh_time = int(args[0])
                        try:
                            while True:
                                time.sleep(refresh_time)
                                result = self.memory_service.do_operation(op_name=query)
                                print(result, flush=True)
                        except KeyboardInterrupt:
                            print("stop refresh!")
                    else:
                        print("unknown command received. Please try again!")
                else:
                    print("unknown command received. Please try again!")
                continue

            while True:
                try:
                    if self.stream:
                        for msg in self.chat_with_memory(query=query):
                            print(msg.text, flush=True)
                        print()
                    else:
                        msg = self.chat_with_memory(query=query)
                        print(msg.text)
                    break
                except KeyboardInterrupt:
                    questionary.print("User interrupt occurred.")
                    retry = questionary.confirm("Retry chat_with_memory()?").ask()
                    if not retry:
                        break
                except Exception as e:
                    questionary.print(f"An exception occurred when running chat_with_memory(): {e}")
                    retry = questionary.confirm("Retry chat_with_memory()?").ask()
                    if not retry:
                        break
