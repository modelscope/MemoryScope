from typing import List

from memory_scope.memory.operation.base_operation import BaseOperation
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.scheme.message import Message
from memory_scope.utils.tool_functions import init_instance_by_config


class ChatMemoryService(BaseMemoryService):
    def __init__(self, history_msg_count: int = 100, contextual_msg_count: int = 6, **kwargs):
        super().__init__(**kwargs)
        self.history_msg_count: int = history_msg_count
        self.contextual_msg_count: int = contextual_msg_count
        assert self.history_msg_count >= self.contextual_msg_count

    def add_messages(self, messages: List[Message] | Message):
        """
        Adds a single message or a list of messages to the chat history, ensuring the message list
        remains sorted by creation time and does not exceed the maximum history message count.

        Args:
            messages (List[Message] | Message): A single message instance or a list of message instances 
            to be added to the chat history.
        """
        # If a single message is provided, convert it into a list for uniform processing
        if isinstance(messages, Message):
            messages = [messages]

        # Sort the messages by their creation time to maintain chronological order
        messages = sorted(messages, key=lambda x: x.time_created)

        # Append the sorted messages to the chat history
        self.chat_messages.extend(messages)

        # If the chat history exceeds the allowed message count, remove the oldest messages
        if len(self.chat_messages) > self.history_msg_count:
            gap_size = len(self.chat_messages) - self.history_msg_count
            for _ in range(gap_size):
                self.chat_messages.pop(0)

    def do_operation(self, op_name: str, **kwargs):
        """
        Executes a specific operation by its name with provided keyword arguments.

        Args:
            op_name (str): The name of the operation to execute.
            **kwargs: Keyword arguments for the operation's execution.

        Returns:
            The result of the operation execution, if any. Otherwise, None.

        Raises:
            Warning: If the operation name is not initialized in `_operation_dict`.
        """
        if op_name not in self._operation_dict:
            self.logger.warning(f"op_name={op_name} is not inited!")  # Warn if operation not initialized
            return
        return self._operation_dict[op_name].run_operation(**kwargs)  # Execute the operation

    def init_service(self, **kwargs):
        for name, operation_config in self.memory_operations.items():
            if name in self._operation_dict:
                self.logger.warning(f"memory operation={name} is repeated!")
                continue

            # ⭐ Initialize operation instance by its config
            operation: BaseOperation = init_instance_by_config(
                config=operation_config,
                name=name,
                chat_messages=self.chat_messages,
                message_lock=self.message_lock,
                contextual_msg_count=self.contextual_msg_count)
            operation.init_workflow(**kwargs)  # Initialize workflow for each operation

            self._operation_dict[name] = operation
            self.logger.info(f"service={self.__class__.__name__} init operation={name}")

    def start_backend_service(self):
        for _, operation in self._operation_dict.items():
            if operation.operation_type == "backend":
                # Run backend operations
                operation.run_operation_backend()
                self.logger.info(f"start operation={operation.name}...")

    def stop_backend_service(self):
        """
        Stops all backend operations that are currently running.
        """
        for _, operation in self._operation_dict.items():
            if operation.operation_type == "backend":
                # Stop backend operations
                operation.stop_operation_backend()
                self.logger.info(f"stop operation={operation.name}...")
