from typing import List, Dict

from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.scheme.message import Message
from memory_scope.utils.tool_functions import init_instance_by_config


class ChatMemoryService(BaseMemoryService):
    def __init__(self, history_msg_count: int = 32, contextual_msg_count: int = 6, **kwargs):
        super().__init__(**kwargs)
        self.history_msg_count: int = history_msg_count
        self.contextual_msg_count: int = contextual_msg_count
        assert self.history_msg_count >= self.contextual_msg_count

        self._init_operation(self.memory_operations)

    def _init_operation(self, memory_operations: Dict[str, dict]):
        for name, operation_config in memory_operations.items():
            if name in self._operation_dict:
                self.logger.warning(f"memory operation={name} is repeated!")
                continue
            self._operation_dict[name] = init_instance_by_config(
                config=operation_config,
                name=name,
                chat_messages=self.chat_messages,
                message_lock=self.message_lock,
                contextual_msg_count=self.contextual_msg_count)

    def add_messages(self, messages: List[Message] | Message):
        if isinstance(messages, Message):
            messages = [messages]

        messages = sorted(messages, key=lambda x: x.time_created)
        self.chat_messages.extend(messages)
        if len(self.chat_messages) > self.history_msg_count:
            gap_size = len(self.chat_messages) - self.history_msg_count
            for _ in range(gap_size):
                self.chat_messages.pop(0)

    def start_service(self):
        for _, operation in self._operation_dict.items():
            operation.init_workflow()
            if operation.operation_type == "backend":
                operation.run_operation_backend()

    def do_operation(self, op_name: str, *args, **kwargs):
        if op_name not in self._operation_dict:
            self.logger.warning(f"op_name={op_name} is not inited!")
            return
        return self._operation_dict[op_name].run_operation()

    def stop_service(self):
        for _, operation in self._operation_dict.items():
            if operation.operation_type == "backend":
                operation.stop_operation_backend()
