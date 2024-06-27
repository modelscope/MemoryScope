from datetime import datetime
from typing import List

from ...utils.response_text_parser import ResponseTextParser
from ...utils.tool_functions import (
    time_to_formatted_str,
    get_datetime_info_dict,
    extract_date_parts,
)
from ...constants.common_constants import (
    REFLECTED,
    DT,
    TIME_INFER,
    NEW,
    MSG_TIME,
    KEY_WORD,
    DATATIME_WORD_LIST,
    NEW_OBS_WITH_TIME_NODES,
    CONTENT_MODIFIED,
)
from ...enumeration.memory_status_enum import MemoryNodeStatus
from ...enumeration.memory_type_enum import MemoryTypeEnum
from ...scheme.memory_node import MemoryNode
from ...scheme.message import Message
from ..memory_base_worker import MemoryBaseWorker
from ...prompts.get_observation_with_time_prompt import (
    GET_OBSERVATION_WITH_TIME_FEW_SHOT_PROMPT,
    GET_OBSERVATION_WITH_TIME_SYSTEM_PROMPT,
    GET_OBSERVATION_WITH_TIME_USER_QUERY_PROMPT,
)


class GetObservationWithTimeWorker(MemoryBaseWorker):

    def add_observation(
        self, message: Message, obs_content: str, time_infer: str, keywords: str
    ):
        created_dt: datetime = datetime.fromtimestamp(float(message.time_created))
        dt = time_to_formatted_str(time=created_dt)

        # 组合meta_data
        meta_data = {
            MemoryTypeEnum.CONVERSATION.value: message.content,  # 原始对话
            REFLECTED: "0",  # reflect标记
            DT: dt,  # 当天标记
            NEW: "1",  # summary-long标记
            MSG_TIME: message.time_created,  # 对话时间
            TIME_INFER: time_infer,  # 推断的时间
            KEY_WORD: keywords,  # 关键词
            CONTENT_MODIFIED: True,  # 新增的obs需要置为true
        }

        # 事件时间
        meta_data.update(
            {f"event_{k}": str(v) for k, v in extract_date_parts(time_infer).items()}
        )
        # 对话时间
        meta_data.update(
            {f"msg_{k}": str(v) for k, v in get_datetime_info_dict(created_dt).items()}
        )

        return MemoryNode.init_from_attrs(
            content=obs_content,
            memory_id=self.memory_id,
            memory_type=MemoryTypeEnum.OBSERVATION.value,
            meta_data=meta_data,
            status=MemoryNodeStatus.ACTIVE.value,
        )

    def _run(self):
        # gene prompt
        user_query_list = []
        i = 1
        for msg in self.messages:
            match = False
            for time_keyword in DATATIME_WORD_LIST:
                if time_keyword in msg.content:
                    match = True
                    break
            if match:
                dt = time_to_formatted_str(
                    time=msg.time_created,
                    date_format="",
                    string_format="{year}年{month}月{day}日{weekday}{hour}点",
                )
                user_query_list.append(f"{i} {dt} 用户：{msg.content}")
                i += 1

        if not user_query_list:
            self.add_run_info(
                f"get obs with time user_query_list={user_query_list} is empty"
            )
            return

        obtain_obs_message = self.prompt_to_msg(
            system_prompt=self.get_prompt(
                GET_OBSERVATION_WITH_TIME_SYSTEM_PROMPT
            ).format(num_obs=len(user_query_list)),
            few_shot=self.get_prompt(GET_OBSERVATION_WITH_TIME_FEW_SHOT_PROMPT),
            user_query=self.get_prompt(
                GET_OBSERVATION_WITH_TIME_USER_QUERY_PROMPT
            ).format(user_query="\n".join(user_query_list)),
        )
        self.logger.info(f"obtain_obs_message={obtain_obs_message}")

        # call LLM
        response_text: str = self.generation_model.call(
            messages=obtain_obs_message,
            model_name=self.summary_messages_model,
            max_token=self.summary_messages_max_token,
            temperature=self.summary_messages_temperature,
            top_k=self.summary_messages_top_k,
        )

        # return if empty
        if not response_text:
            self.add_run_info("summary call llm failed!", continue_run=False)
            return

        # parse text
        idx_obs_list = ResponseTextParser(response_text).parse_v1("get_obs_time")
        if len(idx_obs_list) <= 0:
            self.add_run_info("idx_obs_list is empty!", continue_run=False)
            return

        # gene new obs nodes
        new_obs_nodes: List[MemoryNode] = []
        for obs_content_list in idx_obs_list:
            if not obs_content_list:
                continue

            # [1, 2022年6月, 用户在2022年6月去杭州旅游, 旅游]
            if len(obs_content_list) != 4:
                self.logger.warning(f"obs_content_list={obs_content_list} is invalid!")
                continue

            idx, time_infer, obs_content, keywords = obs_content_list

            if obs_content in ["无", "重复"]:
                continue

            if not idx.isdigit():
                self.logger.warning(f"idx={idx} is invalid!")
                continue

            if time_infer == "无":
                time_infer = ""

            # 序号需要修正-1
            idx = int(idx) - 1
            if idx >= len(self.messages):
                self.logger.warning(
                    f"idx={idx} is invalid! messages.size={len(self.messages)}"
                )
                continue

            new_obs_nodes.append(
                self.add_observation(
                    message=self.messages[idx],
                    obs_content=obs_content,
                    time_infer=time_infer,
                    keywords=keywords,
                )
            )

        # save context
        self.set_context(NEW_OBS_WITH_TIME_NODES, new_obs_nodes)