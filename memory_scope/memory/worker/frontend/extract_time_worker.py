import re
from typing import Dict

from memory_scope.constants.common_constants import QUERY_WITH_TS, EXTRACT_TIME_DICT
from memory_scope.constants.language_constants import DATATIME_KEY_MAP
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.utils.datetime_handler import DatetimeHandler
from memory_scope.utils.tool_functions import prompt_to_msg


class ExtractTimeWorker(MemoryBaseWorker):
    """
    A specialized worker class designed to identify and extract time-related information
    from text generated by an LLM, translating date-time keywords based on the set language,
    and storing this extracted data within a shared context.
    """

    EXTRACT_TIME_PATTERN = r'-\s*(\S+)：(\d+)'
    FILE_PATH: str = __file__

    def _parse_params(self, **kwargs):
        self.generation_model_top_k: int = kwargs.get("generation_model_top_k", 1)

    def _run(self):
        """
        Executes the primary logic of identifying and extracting time data from an LLM's response.

        This method first checks if the input query contains any datetime keywords. If not, it logs and returns.
        It then constructs a prompt with contextual information including formatted timestamps and calls the LLM.
        The response is parsed for time-related data using regex, translated via a language-specific key map,
        and the resulting time data is stored in the shared context.
        """
        query, query_timestamp = self.get_context(QUERY_WITH_TS)

        # Identify if the query contains datetime keywords
        contain_datetime = DatetimeHandler.has_time_word(query)
        if not contain_datetime:
            self.logger.info(f"contain_datetime={contain_datetime}")
            return

        # Prepare the prompt with necessary contextual details
        query_time_str = DatetimeHandler(dt=query_timestamp).string_format(self.prompt_handler.time_string_format)
        system_prompt = self.prompt_handler.extract_time_system
        few_shot = self.prompt_handler.extract_time_few_shot.format(user_name=self.target_name)
        user_query = self.prompt_handler.extract_time_user_query.format(query=query, query_time_str=query_time_str)
        extract_time_message = prompt_to_msg(system_prompt=system_prompt, few_shot=few_shot, user_query=user_query)
        self.logger.info(f"extract_time_message={extract_time_message}")

        # Invoke the LLM to generate a response
        response = self.generation_model.call(messages=extract_time_message, top_k=self.generation_model_top_k)

        # Handle empty or unsuccessful responses
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # Extract time information from the LLM's response using regex
        extract_time_dict: Dict[str, str] = {}
        matches = re.findall(self.EXTRACT_TIME_PATTERN, response_text)
        key_map: dict = self.get_language_value(DATATIME_KEY_MAP)
        for key, value in matches:
            if key in key_map.keys():
                extract_time_dict[key_map[key]] = value
        self.logger.info(f"response_text={response_text} filters={extract_time_dict}")
        self.set_context(EXTRACT_TIME_DICT, extract_time_dict)
