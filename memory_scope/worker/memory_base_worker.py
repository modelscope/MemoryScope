from typing import List, Dict, Optional

from constants import common_constants
from constants.common_constants import CONFIG, MESSAGES, PROMPT_CONFIG
from enumeration.message_role_enum import MessageRoleEnum
from node.message import Message
from node.user_attribute import UserAttribute
from pipeline.memory import MemoryServiceRequestModel
from worker.base_worker import BaseWorker
from cli.cli_config import C
from utils.tool_functions import init_instance_by_config

class MemoryBaseWorker(BaseWorker):
    def __init__(self, **kwargs):
        super(MemoryBaseWorker, self).__init__(**kwargs)

    @property
    def request(self) -> MemoryServiceRequestModel:
        return self.get_context(common_constants.REQUEST)

    @property
    def messages(self) -> List[Message]:
        messages: List[Message] = self.context_handler.get_context(MESSAGES)
        if messages is None:
            messages = self.request.messages
            self.context_handler.set_context(MESSAGES, messages)
        return messages

    @messages.setter
    def messages(self, value):
        self.context_handler.set_context(MESSAGES, value)

    def flush(self, context_handler):
        super(MemoryBaseWorker, self).flush(context_handler)
        self._user_profile_dict: Dict[str, UserAttribute] = {}

    @property
    def user_profile_dict(self) -> Dict[str, UserAttribute]:
        if not self._user_profile_dict:
            self._user_profile_dict = {user_attr.memory_key: user_attr for user_attr in self.request.user.user_profile}
        return self._user_profile_dict

    @property
    def request_ext_info(self):
        return self.request.user.ext_info
        # if not self._request_ext_info:
        #     self._request_ext_info = self.request.ext_info
        # return self._request_ext_info

    @property
    def prompt_config(self) -> BailianPromptConfig:
        return self.request.user.prompt

    @property
    def client(self, model_type: str, model_name:str):
        models = C.get(model_type)
        models["model_name"] = init_instance_by_config(
            config = models.get(model_name),
            try_kwargs={
                "is_multi_thread": is_multi_thread,
                "thread_pool": self.thread_pool
            }
            )
        return models["model_name"]

    @property
    def emb_client(self, model_name: str):
        self.client("model_embedding", model_name)

    @property
    def gene_client(self):
        self.client("model_generate", model_name)

    @property
    def rerank_client(self):
        self.client("model_rerank", model_name)

    @property
    def es_client(self):
        self.client("db", model_name)

    @property
    def tenant_id(self):
        return self.request.user.tenant_id

    @property
    def memory_id(self):
        return self.request.user.memory_id

    @staticmethod
    def prompt_to_msg(system_prompt: str, few_shot: str, user_query: str):
        return [
            {
                "role": MessageRoleEnum.SYSTEM.value,
                "content": system_prompt.strip(),
            },
            {
                "role": MessageRoleEnum.USER.value,
                "content": "\n".join([x.strip() for x in [few_shot, system_prompt, user_query]])
            },
        ]
