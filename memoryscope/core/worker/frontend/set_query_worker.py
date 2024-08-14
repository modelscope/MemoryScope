import datetime

from memoryscope.constants.common_constants import QUERY_WITH_TS
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker


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
        query = ""  # Default query value
        timestamp = int(datetime.datetime.now().timestamp())  # Current timestamp as default

        if "query" in self.chat_kwargs:
            # set query if exists
            query = self.chat_kwargs["query"]
            if not query:
                query = ""
            query = query.strip()

            # set ts if exists
            _timestamp = self.chat_kwargs.get("timestamp")
            if _timestamp and isinstance(_timestamp, int):
                timestamp = _timestamp

        # Store the determined query and its timestamp in the context
        self.set_workflow_context(QUERY_WITH_TS, (query, timestamp))
