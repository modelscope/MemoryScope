import threading
from typing import List, Dict

from memory_scope.memory.operation.base_operation import BaseOperation
from memory_scope.memory.service.base_memory_service import BaseMemoryService
from memory_scope.scheme.message import Message
from memory_scope.utils.tool_functions import init_instance_by_config


class ChatMemoryService(BaseMemoryService):

    def __init__(self,
                 memory_operations: Dict[str, dict],
                 history_msg_count: int = 32,
                 contextual_msg_count: int = 6,
                 **kwargs):
        super().__init__(**kwargs)

        self.op_dict: Dict[str, BaseOperation] = self._init_operation(memory_operations)
        self.history_msg_count: int = history_msg_count
        self.contextual_msg_count: int = contextual_msg_count

        self.chat_messages: List[Message] = []
        self.message_lock = threading.Lock

    def _init_operation(self, memory_operations: Dict[str, dict]):
        op_dict: Dict[str, BaseOperation] = {}
        for name, operation_config in memory_operations.items():
            if name in self.op_dict:
                self.logger.warning(f"memory operation={name} is repeated!")
                continue
            self.op_dict[name] = init_instance_by_config(config=operation_config,
                                                         name=name,
                                                         chat_messages=self.chat_messages,
                                                         message_lock=self.message_lock,
                                                         contextual_msg_count=self.contextual_msg_count)
        return op_dict

    def submit_message(self, messages: List[Message]):
        messages = sorted(messages, key=lambda x: x.time_created)
        self.chat_messages.extend(messages)
        if len(self.chat_messages) > self.history_msg_count:
            gap_size = len(self.chat_messages) - self.history_msg_count
            for _ in range(gap_size):
                self.chat_messages.pop(0)

    def prepare_service(self):
        for _, operation in self.op_dict.items():
            operation.init_workflow()
            if operation.operation_type == "backend":
                operation.run_operation_backend()

    def do_operation(self, op_name: str):
        if op_name not in self.op_dict:
            self.logger.warning(f"op_name={op_name} is not inited!")
            return

        operation = self.op_dict[op_name]
        return operation.run_operation()
