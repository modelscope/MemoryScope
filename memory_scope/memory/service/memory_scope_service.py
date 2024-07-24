from typing import List

from memory_scope.memory.operation.base_operation import BaseOperation
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.scheme.message import Message
from memory_scope.utils.tool_functions import init_instance_by_config


class MemoryScopeService(BaseMemoryService):
    def __init__(self,
                 history_msg_count: int = 100,
                 contextual_msg_max_count: int = 20,
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
            kwargs (dict): other kwargs
        """
        super().__init__(**kwargs)
        self.history_msg_count: int = history_msg_count
        self.contextual_msg_max_count: int = contextual_msg_max_count
        self.contextual_msg_min_count: int = contextual_msg_min_count
        assert history_msg_count >= contextual_msg_max_count >= contextual_msg_min_count

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

        with self.message_lock:
            # Append the sorted messages to the chat history
            self.chat_messages.extend(messages)

            # Sort the messages by their creation time to maintain chronological order
            self.chat_messages.sort(key=lambda x: x.time_created)

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
                contextual_msg_max_count=self.contextual_msg_max_count,
                contextual_msg_min_count=self.contextual_msg_min_count)
            operation.init_workflow(**kwargs)  # Initialize workflow for each operation

            self._operation_dict[name] = operation
            self.logger.info(f"service={self.__class__.__name__} init operation={name}")

    def start_backend_service(self):
        """
        Start all backend operations.
        """
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
