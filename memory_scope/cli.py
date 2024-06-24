import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
import questionary
from rich.console import Console
import sys
import time
import fire

from memory_scope.chat.base_memory_chat import BaseMemoryChat
from memory_scope.chat.global_context import GLOBAL_CONTEXT
from memory_scope.enumeration.language_enum import LanguageEnum
from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.utils.logger import Logger
from memory_scope.utils.tool_functions import (
    complete_config_name,
    init_instance_by_config,
)
from memory_scope.chat.memory_chat import MemoryChat


class CliMemoryChat(object):  # object -> MemoryChat

    USER_COMMANDS = {
        "/exit": "exit the CLI",
        "/memory": "print the current contents of agent memory",
        "/retrieve": "retrieve related memory",
        "/log": "log chat progress"
        # TODO add more commands
    }

    def chat_with_memory(self, query):  # for testing
        return query

    def retrieve_all(self):  # for testing
        return "memory 1. 2. 3."

    def run(self):
        console = Console()
        while True:
            query = questionary.text(
                "Enter your message or command:",
                multiline=False,
                qmark=">",
            ).ask()

            query = query.rstrip()

            if query == "":
                console.print("Empty input received. Try again!")
                continue

            # Handle CLI commands
            if query.startswith("/"):
                if query.lower() == "/exit":
                    break
                elif query.lower() == "/memory":
                    console.print(self.memory_service.retrieve_all())
                elif query.lower() == "/help":
                    questionary.print("CLI commands", "bold")
                    for cmd, desc in self.USER_COMMANDS.items():
                        questionary.print(cmd, "bold")
                        questionary.print(f" {desc}")
                    continue

                continue

            while True:
                try:
                    with console.status("[bold cyan]Thinking..."):
                        messages = self.chat_with_memory(query=query)
                        console.print(messages)
                        break
                except KeyboardInterrupt:
                    console.print("User interrupt occurred.")
                    retry = questionary.confirm("Retry chat_with_memory()?").ask()
                    if not retry:
                        break
                except Exception as e:
                    console.print(
                        f"An exception occurred when running chat_with_memory(): {e}"
                    )
                    retry = questionary.confirm("Retry chat_with_memory()?").ask()
                    if not retry:
                        break


class CliJob(object):

    def __init__(self, config_path: str):
        self.config_path: str = config_path
        self.config_base_dir: str = os.path.dirname(config_path)
        self.config: Dict[str, Any] = {}

        self.worker_chat_dict: Dict[str, List[str]] = {}
        self.logger: Logger = Logger.get_logger("memory_chat")

    def init_memory_chat(self):
        for chat_name in self.config["chat_list"]:
            memory_chat_config = self.config[chat_name]
            memory_chat: BaseMemoryChat = init_instance_by_config(
                memory_chat_config, chat_name=chat_name
            )
            GLOBAL_CONTEXT.memory_chat_dict[chat_name] = memory_chat

            for worker_name in memory_chat.memory_service.get_worker_list():
                if worker_name not in self.worker_chat_dict:
                    self.worker_chat_dict[worker_name] = []
                self.worker_chat_dict[worker_name].append(chat_name)

            generation_model = memory_chat_config[ModelEnum.GENERATION_MODEL.value]
            self.init_model(generation_model)

    def init_model(self, model_name: str):
        if not model_name or model_name in GLOBAL_CONTEXT.model_dict:
            return

        with open(
            os.path.join(
                self.config_base_dir, "model", complete_config_name(model_name)
            )
        ) as f:
            model_config = json.load(f)
        GLOBAL_CONTEXT.model_dict[model_name] = init_instance_by_config(model_config)

    def init_workers(self):
        """load worker config & init workers"""
        worker_config_name: str = self.config["workers"]
        with open(
            os.path.join(self.config_base_dir, complete_config_name(worker_config_name))
        ) as f:
            worker_config_dict = json.load(f)

        for worker_name, worker_config in worker_config_dict.items():
            if worker_name not in self.worker_chat_dict:
                continue

            chat_name_list = self.worker_chat_dict[worker_name]
            for chat_name in chat_name_list:
                if chat_name not in GLOBAL_CONTEXT.worker_dict:
                    GLOBAL_CONTEXT.worker_dict[chat_name] = {}
                GLOBAL_CONTEXT.worker_dict[chat_name][worker_name] = (
                    init_instance_by_config(
                        worker_config,
                        suffix_name="worker",
                        **GLOBAL_CONTEXT.global_configs,
                    )
                )

            self.init_model(worker_config.get(ModelEnum.EMBEDDING_MODEL.value))
            self.init_model(worker_config.get(ModelEnum.GENERATION_MODEL.value))
            self.init_model(worker_config.get(ModelEnum.RANK_MODEL.value))

    @staticmethod
    def set_global_config():
        """TODO set global_configs & set apikey into env"""
        GLOBAL_CONTEXT.language = LanguageEnum(
            GLOBAL_CONTEXT.global_configs["language"]
        )
        GLOBAL_CONTEXT.thread_pool = ThreadPoolExecutor(
            max_workers=int(GLOBAL_CONTEXT.global_configs["max_workers"])
        )

    def init_global_content_by_config(self):
        with open(complete_config_name(self.config_path)) as f:
            self.config = json.load(f)

        GLOBAL_CONTEXT.global_configs = self.config["global_configs"]
        self.set_global_config()

        self.init_memory_chat()

        self.init_workers()
        GLOBAL_CONTEXT.vector_store = init_instance_by_config(
            self.config["vector_store"]
        )
        GLOBAL_CONTEXT.monitor = init_instance_by_config(self.config["monitor"])

    @staticmethod
    def run():
        with GLOBAL_CONTEXT.thread_pool:
            memory_chat = list(GLOBAL_CONTEXT.memory_chat_dict.values())[0]
            memory_chat.run()


def main(config_path: str):
    job = CliJob(config_path=config_path)
    job.init_global_content_by_config()
    job.run()


if __name__ == "__main__":
    fire.Fire(main)