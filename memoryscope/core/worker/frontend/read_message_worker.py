from typing import List

from memoryscope.constants.common_constants import RESULT
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.scheme.message import Message


class ReadMessageWorker(MemoryBaseWorker):
    """
    Fetches unmemorized chat messages.
    """

    def _run(self):
        """
        Executes the primary function to fetch unmemorized chat messages.
        """
        chat_messages_not_memorized: List[List[Message]] = []
        for messages in self.chat_messages:
            if not messages:
                continue

            if messages[0].memorized:
                continue

            contain_flag = False

            for msg in messages:
                if msg.role_name == self.target_name:
                    contain_flag = True
                    break

            if contain_flag:
                chat_messages_not_memorized.append(messages)

        contextual_msg_max_count: int = self.chat_kwargs["contextual_msg_max_count"]
        chat_message_scatter = []
        for messages in chat_messages_not_memorized[-contextual_msg_max_count:]:
            chat_message_scatter.extend(messages)
        chat_message_scatter.sort(key=lambda _: _.time_created)
        self.set_workflow_context(RESULT, chat_message_scatter)
