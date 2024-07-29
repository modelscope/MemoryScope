import os
import time
from typing import Optional, Literal

import questionary

from memoryscope.core.chat.api_memory_chat import ApiMemoryChat
from memoryscope.core.utils.tool_functions import char_logo


class CliMemoryChat(ApiMemoryChat):
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logo = char_logo("MemoryScope")

    def print_logo(self):
        """
        Prints the logo of the CLI application to the console.

        The logo is composed of multiple lines, which are iterated through
        and printed one by one to provide a visual identity for the chat interface.
        """
        for line in self._logo:
            print(line)

    def chat_with_memory(self,
                         query: str,
                         role_name: Optional[str] = None,
                         system_prompt: Optional[str] = None,
                         memory_prompt: Optional[str] = None,
                         temporary_memories: Optional[str] = None,
                         history_message_strategy: Literal["auto", None] | int = "auto",
                         remember_response: bool = True,
                         **kwargs):
        resp = super().chat_with_memory(query=query,
                                        role_name=role_name,
                                        system_prompt=system_prompt,
                                        memory_prompt=memory_prompt,
                                        temporary_memories=temporary_memories,
                                        history_message_strategy=history_message_strategy,
                                        remember_response=remember_response,
                                        **kwargs)

        if self.stream:
            for _resp in resp:
                questionary.print(_resp.delta, end="")
            questionary.print("")
        else:
            questionary.print(resp.message.content)

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

        # Print prompt for AI's response
        questionary.print("> ", end="", style="fg:yellow")
        questionary.print(f"{self.assistant_name}: ", end="", style="bold")

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
                    result = self.memory_service.run_operation(name=command, **kwargs)
                    if os.name == 'nt':
                        os.system('cls')
                    else:
                        os.system('clear')
                    self.print_logo()
                    if result:
                        if isinstance(result, list):
                            result = "\n".join([str(x) for x in result])
                        questionary.print(result)
                    else:
                        questionary.print(f"command={command} result is empty! kwargs={kwargs}")
                    time.sleep(refresh_time)

            else:
                result = self.memory_service.run_operation(name=command, **kwargs)
                if result:
                    if isinstance(result, list):
                        result = "\n".join([str(x) for x in result])
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

                # Fetch and display AI's response
                self.start_backend_service()
                self.chat_with_memory(query=query)

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
