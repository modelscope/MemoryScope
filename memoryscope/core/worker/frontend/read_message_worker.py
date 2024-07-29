from memoryscope.constants.common_constants import RESULT
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.message_role_enum import MessageRoleEnum


class ReadMessageWorker(MemoryBaseWorker):
    """
    Fetches unmemorized chat messages.
    """

    def _run(self):
        """
        Executes the primary function to fetch unmemorized chat messages.
        """
        chat_messages = [x for x in self.chat_messages if not x.memorized]
        if len(chat_messages) > 0 and chat_messages[-1].role == MessageRoleEnum.USER.value:
            chat_messages = chat_messages[:-1]

        contextual_msg_max_count: int = self.chat_kwargs["contextual_msg_max_count"]
        chat_messages = chat_messages[-contextual_msg_max_count:]

        self.set_context(RESULT, chat_messages)
