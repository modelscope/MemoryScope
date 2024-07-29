import threading
from typing import List

from memoryscope.core.operation.base_operation import BaseOperation
from memoryscope.core.service.base_memory_service import BaseMemoryService
from memoryscope.core.utils.tool_functions import init_instance_by_config
from memoryscope.scheme.message import Message


class MemoryScopeService(BaseMemoryService):
    def __init__(self,
                 history_msg_count: int = 100,
                 contextual_msg_max_count: int = 20,
                 contextual_msg_min_count: int = 0,
                 human_name: str = None,
                 assistant_name: str = None,
                 **kwargs):
        """
        init function.
        Args:
            history_msg_count (int): The conversation history in memory, control the quantity, and reduce memory usage.
            contextual_msg_max_count (int): The maximum context length in a conversation. If it exceeds this length,
                    it will not be included in the context to prevent token overflow.
            contextual_msg_min_count (int): The minimum context length in a conversation. If it is shorter than this
                    length, no conversation summary will be made and no long-term memory will be generated.
            human_name (str): human name.
            assistant_name (str): assistant name.
            kwargs (dict): other kwargs.
        """
        super().__init__(**kwargs)
        self.history_msg_count: int = history_msg_count
        self.contextual_msg_max_count: int = contextual_msg_max_count
        self.contextual_msg_min_count: int = contextual_msg_min_count
        assert history_msg_count >= contextual_msg_max_count >= contextual_msg_min_count
        if human_name:
            self.context.meta_data["human_name"] = human_name
        if assistant_name:
            self.context.meta_data["assistant_name"] = assistant_name

        self.message_lock = threading.Lock()

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

    def register_operation(self, name: str, operation_config: dict, **kwargs):
        if name in self._operation_dict:
            self.logger.warning(f"op_name={name} is registered before!")
            return

        operation: BaseOperation = init_instance_by_config(
            config=operation_config,
            name=name,
            chat_messages=self.chat_messages,
            message_lock=self.message_lock,
            memoryscope_context=self.context,
            contextual_msg_max_count=self.contextual_msg_max_count,
            contextual_msg_min_count=self.contextual_msg_min_count)

        # Initialize workflow for each operation
        operation.init_workflow(**kwargs)
        self._operation_dict[name] = operation
        self.logger.info(f"service={self.__class__.__name__} init operation={name}")

    def init_service(self, **kwargs):
        for name, operation_config in self.memory_operations_conf.items():
            self.register_operation(name, operation_config, **kwargs)

    def start_backend_service(self, name: str = None):
        """
        Start all backend operations.
        """
        for op_name, operation in self._operation_dict.items():
            if name:
                if op_name == name:
                    operation.start_operation_backend()
            else:
                if operation.operation_type == "backend":
                    operation.start_operation_backend()

    def stop_backend_service(self, wait_service_end: bool = False):
        """
        Stops all backend operations that are currently running.
        """
        for _, operation in self._operation_dict.items():
            if operation.operation_type == "backend":
                operation.stop_operation_backend(wait_task_end=wait_service_end)
