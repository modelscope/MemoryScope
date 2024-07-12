import datetime

from memory_scope.constants.common_constants import QUERY_WITH_TS
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker


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

        # Check if a specific 'query' has been provided via chat kwargs
        if "query" in self.chat_kwargs:
            query = self.chat_kwargs["query"]

        # If no explicit query is given, use the content of the latest chat message
        elif self.chat_messages:
            query = self.chat_messages[-1].content
            query_timestamp = self.chat_messages[-1].time_created

        # Store the determined query and its timestamp in the context
        self.set_context(QUERY_WITH_TS, (query, query_timestamp))
