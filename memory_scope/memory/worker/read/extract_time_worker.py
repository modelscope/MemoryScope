import re

from memory_scope.constants.common_constants import DATATIME_KEY_MAP, QUERY_WITH_TS, EXTRACT_TIME_DICT
from memory_scope.constants.language_constants import DATATIME_WORD_LIST
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.utils.tool_functions import time_to_formatted_str


class ExtractTimeWorker(MemoryBaseWorker):
    EXTRACT_TIME_PATTERN = r'-\s*(\S+)：(\d+)'

    def _run(self):
        query, query_timestamp = self.get_context(QUERY_WITH_TS)

        # find datetime keyword
        contain_datetime = False
        for datetime_word in self.get_language_prompt(DATATIME_WORD_LIST):
            if datetime_word in query:
                contain_datetime = True
                break
        if not contain_datetime:
            self.logger.info(f"contain_datetime={contain_datetime}")
            return

        # prepare prompt
        query_time_str = time_to_formatted_str(dt=query_timestamp,
                                               date_format="",
                                               string_format=self.prompt_handler.time_format_prompt)
        extract_time_prompt: str = self.prompt_handler.extract_time_prompt
        extract_time_prompt: str = extract_time_prompt.format(query=query, query_time_str=query_time_str)
        self.logger.info(f"extract_time_prompt={extract_time_prompt}")

        # call sft model
        response = self.generation_model.call(prompt=extract_time_prompt,
                                              model_name=self.extra_time_model,
                                              max_token=self.extra_time_max_token,
                                              temperature=self.extra_time_temperature,
                                              top_k=self.extra_time_top_k)

        # if empty, return
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # re-match time info to dict
        extract_time_dict = {}
        matches = re.findall(self.EXTRACT_TIME_PATTERN, response_text)
        for key, value in matches:
            if key in DATATIME_KEY_MAP.keys():
                extract_time_dict[DATATIME_KEY_MAP[key]] = value
        self.set_context(EXTRACT_TIME_DICT, extract_time_dict)

        self.logger.info(f"response_text={response_text} filters={extract_time_dict}")
