import datetime

import questionary
from rich.console import Console

from .memory_chat import MemoryChat
from enumeration.message_role_enum import MessageRoleEnum
from scheme.message import Message


class CliMemoryChat(MemoryChat):

    USER_COMMANDS = {
        "/exit": "exit the CLI",
        "/memory": "print the current contents of agent memory",
        "/retrieve": "retrieve related memory",
        "/log": "log chat progress",
        # TODO add more commands
    }

    def chat_with_memory(self, query):  # for testing
        query = query.strip()
        if not query:
            return

        time_created = int(datetime.datetime.now().timestamp())
        message = Message(
            role=MessageRoleEnum.USER, content=query, time_created=time_created
        )
        messages = [message]
        return self.generation_model.call(messages=messages, stream=True)

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

            while True:
                try:
                    # with console.status("[bold cyan]Thinking..."):
                    for msg in self.chat_with_memory(query=query):
                        console.print(msg.delta, end="")
                    console.print()
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
