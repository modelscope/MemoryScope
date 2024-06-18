from common.response_text_parser import ResponseTextParser
from enumeration.message_role_enum import MessageRoleEnum
from worker.memory.memory_base_worker import MemoryBaseWorker


class InfoFilterWorker(MemoryBaseWorker):
    def __init__(self, info_filter_msg_max_size, info_filter_model, info_filter_max_token, info_filter_temperature, info_filter_top_k, *args, **kwargs):
        super(InfoFilterWorker,self).__init__(*args,**kwargs)
        self.info_filter_msg_max_size
        self.info_filter_model = info_filter_model
        self.info_filter_max_token = info_filter_max_token
        self.info_filter_temperature = info_filter_temperature
        self.info_filter_top_k = info_filter_top_k

    def _run(self):
        # filter user msg
        info_messages = []
        for msg in self.messages:
            if msg.role != MessageRoleEnum.USER.value:
                continue
            if len(msg.content) >= self.info_filter_msg_max_size:
                continue
            info_messages.append(msg)

        # gene prompt
        user_query = "\n".join([f"{i + 1} 用户：{msg.content}" for i, msg in enumerate(info_messages)])
        info_filter_message = self.prompt_to_msg(
            system_prompt=self.prompt_config.info_filter_system.format(batch_size=len(info_messages)),
            few_shot=self.prompt_config.info_filter_few_shot,
            user_query=self.prompt_config.info_filter_user_query.format(user_query=user_query))
        self.logger.info(f"info_filter_message={info_filter_message}")

        # call llm
        response_text = self.gene_client.call(messages=info_filter_message,
                                              model_name=self.info_filter_model,
                                              max_token=self.info_filter_max_token,
                                              temperature=self.info_filter_temperature,
                                              top_k=self.info_filter_top_k)

        # return if empty
        if not response_text:
            self.add_run_info("info score call llm failed!", continue_run=False)
            return

        # parse text
        info_score_list = ResponseTextParser(response_text).parse_v1("info_filter")
        if len(info_score_list) != len(info_messages):
            self.add_run_info(f"info_score_size != info_messages_size, "
                              f"{len(info_score_list)} vs {len(info_messages)}", continue_run=False)
            return

        # 过滤value=0的messages
        filtered_messages = []
        for msg, info_score in zip(info_messages, info_score_list):
            if not info_score:
                continue
            score = info_score[0]
            # if score in ("1", "2",):
            if score in ("2",):
                msg.info_score = score
                filtered_messages.append(msg)

        # 后续不会关注为0的msg，直接丢弃
        self.messages = filtered_messages
