import threading
from typing import List

from memoryscope.core.operation.base_operation import BaseOperation
from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.scheme.message import Message


class MemoryScopeService(BaseMemoryService):
    def __init__(self,
                 history_msg_count: int = 100,
                 contextual_msg_max_count: int = 10,
                 contextual_msg_min_count: int = 0,
                 **kwargs):
        """
        init function.
        Args:
            history_msg_count (int): The conversation history in memory, control the quantity, and reduce memory usage.
            contextual_msg_max_count (int): The maximum context length in a conversation. If it exceeds this length,
                    it will not be included in the context to prevent token overflow.
            contextual_msg_min_count (int): The minimum context length in a conversation. If it is shorter than this
                    length, no conversation summary will be made and no long-term memory will be generated.
            kwargs (dict): Additional parameters to customize service behavior.
        """
        super().__init__(**kwargs)

        assert history_msg_count >= contextual_msg_max_count >= contextual_msg_min_count
        self._history_msg_count: int = history_msg_count
        self._contextual_msg_max_count: int = contextual_msg_max_count
        self._contextual_msg_min_count: int = contextual_msg_min_count

        self._message_lock = threading.Lock()

    def add_messages_pair(self, messages: List[Message]):
        """
        Adds a list of messages to the chat history, it can be a pair [user_message, assistant_message].
        Ensuring the message list remains sorted by creation time and does not exceed the maximum history message count.

        Args:
            messages (List[Message] | Message): A single message instance or a list of message instances
            to be added to the chat history.
        """
        assert messages, "messages should not be empty!"

        with self._message_lock:
            # Append the sorted messages to the chat history
            self._chat_messages.append(messages)

            # Sort the messages by their creation time to maintain chronological order
            self._chat_messages.sort(key=lambda x: x[0].time_created)

            # If the chat history exceeds the allowed message count, remove the oldest messages
            if len(self._chat_messages) > self._history_msg_count:
                gap_size = len(self._chat_messages) - self._history_msg_count
                for _ in range(gap_size):
                    self._chat_messages.pop(0)

        for message in messages:
            if message.role_name and message.role_name != self.assistant_name \
                    and message.role_name not in self._role_names:
                self._role_names.append(message.role_name)

    def register_operation(self, name: str, operation_config: dict, **kwargs):
        if name in self._operation_dict:
            self.logger.warning(f"op_name={name} is registered before!")
            return

        operation: BaseOperation = init_instance_by_config(
            config=operation_config,
            name=name,
            user_name=self._assistant_name,
            target_names=self._role_names,
            chat_messages=self._chat_messages,
            message_lock=self._message_lock,
            memoryscope_context=self._context,
            contextual_msg_max_count=self._contextual_msg_max_count,
            contextual_msg_min_count=self._contextual_msg_min_count)

        # Initialize workflow for each operation
        operation.init_workflow(**kwargs)
        self._operation_dict[name] = operation
        self.logger.info(f"service={self.__class__.__name__} init operation={name}")

    def init_service(self, **kwargs):
        for name, operation_config in self._operations_conf.items():
            self.register_operation(name, operation_config, **kwargs)

    def run_operation(self, name: str, role_name: str = "", **kwargs):
        """
        Executes a specific operation by its name with provided keyword arguments.

        Args:
            name (str): The name of the operation to execute.
            role_name (str): The name of the operation to execute.
            **kwargs: Keyword arguments for the operation's execution.

        Returns:
            The result of the operation execution, if any. Otherwise, None.

        Raises:
            Warning: If the operation name is not initialized in `_operation_dict`.
        """
        if name not in self._operation_dict:
            self.logger.warning(f"operation={name} is not registered!")
            return

        target_name = self._human_name
        if role_name:
            target_name = role_name
            if role_name not in self._role_names:
                self._role_names.append(role_name)

        return self._operation_dict[name].run_operation(target_name=target_name, **kwargs)

    def start_backend_service(self, name: str = None, **kwargs):
        """
        Start all backend operations.
        """
        for op_name, operation in self._operation_dict.items():
            if name:
                if op_name == name:
                    operation.start_operation_backend(**kwargs)
            else:
                if operation.operation_type == "backend":
                    operation.start_operation_backend(**kwargs)

    def stop_backend_service(self, wait_service: bool = False):
        """
        Stops all backend operations that are currently running.
        """
        for _, operation in self._operation_dict.items():
            if operation.operation_type == "backend":
                operation.stop_operation_backend(wait_operation=wait_service)
