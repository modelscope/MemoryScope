import datetime

from memoryscope.constants.common_constants import QUERY_WITH_TS
from memoryscope.enumeration.message_role_enum import MessageRoleEnum
from memoryscope.memory.worker.memory_base_worker import MemoryBaseWorker


class SetQueryWorker(MemoryBaseWorker):
    """
    The `SetQueryWorker` class is responsible for setting a query and its associated timestamp
    into the context, utilizing either provided chat parameters or details from the most recent
    chat message.
    """

    def _run(self):
        """
        Executes the worker's primary function, which involves determining the query and its
        timestamp, then storing these values within the context.

        If 'query' is found within `self.chat_kwargs`, it is considered as the query input.
        Otherwise, the content of the last message in `self.chat_messages` is used as the query,
        along with its creation timestamp.
        """
        query = "_"  # Default query value
        query_timestamp = int(datetime.datetime.now().timestamp())  # Current timestamp as default

        if "query" in self.chat_kwargs:
            # Check if a specific 'query' has been provided via chat kwargs
            query = self.chat_kwargs["query"]
            if not query:
                query = ""
            query = query.strip()

        elif self.chat_messages:
            # If no explicit query is given, use the content of the latest chat message
            chat_messages = [msg for msg in self.chat_messages if msg.role == MessageRoleEnum.USER.value]
            if chat_messages:
                message = chat_messages[-1]
                query = message.content
                query_timestamp = message.time_created

        # Store the determined query and its timestamp in the context
        self.set_context(QUERY_WITH_TS, (query, query_timestamp))
