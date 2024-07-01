import re
from typing import Dict

from memory_scope.constants.common_constants import DATATIME_KEY_MAP, QUERY_WITH_TS, EXTRACT_TIME_DICT
from memory_scope.constants.language_constants import DATATIME_WORD_LIST
from memory_scope.memory.worker.memory_base_worker import MemoryBaseWorker
from memory_scope.utils.datetime_handler import DatetimeHandler


class ExtractTimeWorker(MemoryBaseWorker):
    EXTRACT_TIME_PATTERN = r'-\s*(\S+)：(\d+)'

    def _run(self):
        query, query_timestamp = self.get_context(QUERY_WITH_TS)

        # find datetime keyword
        contain_datetime = False
        for datetime_word in self.get_language_value(DATATIME_WORD_LIST):
            if datetime_word in query:
                contain_datetime = True
                break
        if not contain_datetime:
            self.logger.info(f"contain_datetime={contain_datetime}")
            return

        # prepare prompt
        query_time_str = DatetimeHandler(dt=query_timestamp).string_format(self.prompt_handler.time_string_format)
        extract_time_prompt: str = self.prompt_handler.extract_time_prompt.format(query=query,
                                                                                  query_time_str=query_time_str)
        self.logger.info(f"extract_time_prompt={extract_time_prompt}")

        # call sft model
        response = self.generation_model.call(prompt=extract_time_prompt, top_k=self.extra_time_top_k)

        # if empty, return
        if not response.status or not response.message.content:
            return
        response_text = response.message.content

        # re-match time info to dict
        extract_time_dict: Dict[str, str] = {}
        matches = re.findall(self.EXTRACT_TIME_PATTERN, response_text)
        for key, value in matches:
            if key in DATATIME_KEY_MAP.keys():
                extract_time_dict[DATATIME_KEY_MAP[key]] = value
        self.logger.info(f"response_text={response_text} filters={extract_time_dict}")
        self.set_context(EXTRACT_TIME_DICT, extract_time_dict)
