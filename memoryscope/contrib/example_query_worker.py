import datetime

from memoryscope.constants.common_constants import QUERY_WITH_TS
from memoryscope.constants.language_constants import NONE_WORD
from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker
from memoryscope.enumeration.message_role_enum import MessageRoleEnum


class ExampleQueryWorker(MemoryBaseWorker):
    # NOTE: If you want to utilize the capabilities of the prompt handler, please be sure to include this sentence.
    FILE_PATH: str = __file__

    def _parse_params(self, **kwargs):
        self.rewrite_history_count: int = kwargs.get("rewrite_history_count", 2)
        self.generation_model_kwargs: dict = kwargs.get("generation_model_kwargs", {})

    def rewrite_query(self, query: str) -> str:
        chat_messages = self.chat_messages_scatter
        if len(chat_messages) <= 1:
            return query

        if chat_messages[-1].role == MessageRoleEnum.USER:
            chat_messages = chat_messages[:-1]
        chat_messages = chat_messages[-self.rewrite_history_count:]

        # get context
        context_list = []
        for message in chat_messages:
            context = message.content
            if len(context) > 200:
                context = context[:100] + context[-100:]
            if message.role == MessageRoleEnum.USER:
                context_list.append(f"{self.target_name}: {context}")
            elif message.role == MessageRoleEnum.ASSISTANT:
                context_list.append(f"Assistant: {context}")

        if not context_list:
            return query

        system_prompt = self.prompt_handler.rewrite_query_system
        user_query = self.prompt_handler.rewrite_query_query.format(query=query,
                                                                    context="\n".join(context_list))
        rewrite_query_message = self.prompt_to_msg(system_prompt=system_prompt,
                                                   few_shot="",
                                                   user_query=user_query)
        self.logger.info(f"rewrite_query_message={rewrite_query_message}")

        # Invoke the LLM to generate a response
        response = self.generation_model.call(messages=rewrite_query_message,
                                              **self.generation_model_kwargs)

        # Handle empty or unsuccessful responses
        if not response.status or not response.message.content:
            return query

        response_text = response.message.content
        self.logger.info(f"rewrite_query.response_text={response_text}")

        if not response_text or response_text.lower() == self.get_language_value(NONE_WORD):
            return query

        return response_text

    def _run(self):
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

            if self.rewrite_history_count > 0:
                t_query = self.rewrite_query(query=query)
                if t_query:
                    query = t_query

        # Store the determined query and its timestamp in the context
        self.set_workflow_context(QUERY_WITH_TS, (query, timestamp))
