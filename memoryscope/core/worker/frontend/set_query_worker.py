import datetime

from memoryscope.constants.common_constants import QUERY_WITH_TS
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.message_role_enum import MessageRoleEnum


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

            # check role_name
            role_name = self.chat_kwargs.get("role_name")
            if role_name:
                assert role_name == self.target_name, (f"role_name={role_name} <> target_name={self.target_name} "
                                                       f"is not supported in human/assistant memory workflow!")

        elif self.chat_messages:
            # If no explicit query is given, use the content of the latest chat message
            chat_messages = [msg for msg in self.chat_messages if msg.role == MessageRoleEnum.USER.value]
            if chat_messages:
                message = chat_messages[-1]
                query = message.content
                timestamp = message.time_created

                # check role_name
                role_name = message.role_name
                if role_name:
                    assert role_name == self.target_name, \
                        f"role_name={role_name} is not supported in human/assistant memory workflow!"

        # Store the determined query and its timestamp in the context
        self.set_context(QUERY_WITH_TS, (query, timestamp))
