from memory_scope.constants.common_constants import RESULT
from memory_scope.enumeration.message_role_enum import MessageRoleEnum
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker


class ReadMessageWorker(MemoryBaseWorker):

    def _run(self):
        contextual_msg_count: int = self.chat_kwargs["contextual_msg_count"]

        chat_messages = self.chat_messages.copy()
        if len(chat_messages) > 0 and chat_messages[-1].role == MessageRoleEnum.USER.value:
            chat_messages = chat_messages[:-1]

        self.set_context(RESULT, chat_messages[-contextual_msg_count:])
