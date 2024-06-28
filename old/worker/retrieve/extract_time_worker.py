import re

from utils.tool_functions import time_to_formatted_str
from constants.common_constants import (
    DATATIME_WORD_LIST,
    DATATIME_KEY_MAP,
    EXTRACT_TIME_DICT,
)
from worker.memory_base_worker import MemoryBaseWorker


class ExtractTimeWorker(MemoryBaseWorker):
    # TODO add en version
    @staticmethod
    def get_parse_time_prompt(query: str, query_time_str: str):
        return f"""
任务指令：从语句与语句发生的时间，推断并提取语句内容中指向的时间段。回答尽可能完整的时间段。
语句：{query}
时间：{query_time_str}
回答：
        """.strip()

    def _run(self):
        # save to context
        extract_time_dict = {}
        self.set_context(EXTRACT_TIME_DICT, extract_time_dict)

        # get query & time_created_dt
        query = self.messages[-1].content
        time_created = self.messages[-1].time_created

        # find datetime keyword
        contain_datetime = False
        for datetime_word in DATATIME_WORD_LIST:
            if datetime_word in query:
                contain_datetime = True
                break
        if not contain_datetime:
            self.logger.info(f"contain_datetime={contain_datetime}")
            return

        # prepare prompt
        # TODO add en version
        time_format = "{year}年{month}月{day}日，{year}年第{week}周，{weekday}，{hour}时{minute}分{second}秒。"
        query_time_str = time_to_formatted_str(
            time=time_created, date_format="", string_format=time_format
        )
        extract_time_prompt = self.get_parse_time_prompt(
            query=query, query_time_str=query_time_str
        )
        self.logger.info(f"extract_time_prompt={extract_time_prompt}")

        # call sft model

        response_text = self.generation_model.call(
            prompt=extract_time_prompt,
            model_name=self.parse_time_model,
            max_token=self.parse_time_max_token,
            temperature=self.parse_time_temperature,
            top_k=self.parse_time_top_k,
        )

        # if empty, return
        if not response_text:
            return

        # re-match time info to dict
        pattern = r"-\s*(\S+)：(\d+)"
        matches = re.findall(pattern, response_text)
        for key, value in matches:
            if key in DATATIME_KEY_MAP.keys():
                extract_time_dict[DATATIME_KEY_MAP[key]] = value

        self.logger.info(f"response_text={response_text} filters={extract_time_dict}")
