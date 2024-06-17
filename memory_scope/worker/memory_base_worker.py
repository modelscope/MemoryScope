from typing import List, Dict, Optional

from common.dash_embedding_client import DashEmbeddingClient
from common.dash_generate_client import DashGenerateClient
from common.dash_rerank_client import DashReRankClient
from common.elastic_search_client import ElasticSearchClient
from config.bailian_memory_config import BailianMemoryConfig
from config.bailian_prompt_config import BailianPromptConfig
from constants import common_constants
from constants.common_constants import CONFIG, MESSAGES, PROMPT_CONFIG
from enumeration.message_role_enum import MessageRoleEnum
from model.message import Message
from model.user_attribute import UserAttribute
from request.memory import MemoryServiceRequestModel
from worker.bailian.base_worker import BaseWorker


class MemoryBaseWorker(BaseWorker):

    def __init__(self, **kwargs):
        super(MemoryBaseWorker, self).__init__(**kwargs)

        self._user_profile_dict: Dict[str, UserAttribute] = {}
        self._request_ext_info: Dict[str, str] = {}

        self._config: Optional[BailianMemoryConfig] = None
        self._prompt_config: Optional[BailianPromptConfig] = None

        self._dash_embedding_client: Optional[DashEmbeddingClient] = None
        self._dash_generate_client: Optional[DashGenerateClient] = None
        self._dash_rerank_client: Optional[DashReRankClient] = None

        self._es_client: Optional[ElasticSearchClient] = None

    @property
    def request(self) -> MemoryServiceRequestModel:
        return self.get_context(common_constants.REQUEST)

    @property
    def messages(self) -> List[Message]:
        messages: List[Message] = self.context_handler.get_context(MESSAGES)
        if messages is None:
            messages = self.request.messages[-self.config.messages_pick_n:]
            self.context_handler.set_context(MESSAGES, messages)
        return messages

    @messages.setter
    def messages(self, value):
        self.context_handler.set_context(MESSAGES, value)

    @property
    def user_profile_dict(self) -> Dict[str, UserAttribute]:
        if not self._user_profile_dict:
            self._user_profile_dict = {user_attr.memory_key: user_attr for user_attr in self.request.user_profile}
        return self._user_profile_dict

    @property
    def request_ext_info(self):
        if not self._request_ext_info:
            self._request_ext_info = self.request.ext_info
        return self._request_ext_info

    @property
    def config(self) -> BailianMemoryConfig:
        if self._config is None:
            self._config = self.get_context(CONFIG)
        return self._config

    @property
    def prompt_config(self) -> BailianPromptConfig:
        if self._prompt_config is None:
            self._prompt_config = self.get_context(PROMPT_CONFIG)
            if not self._prompt_config:
                self._prompt_config = BailianPromptConfig()
                self.set_context(PROMPT_CONFIG, self._prompt_config)
        return self._prompt_config

    @property
    def emb_client(self):
        if self._dash_embedding_client is None:
            self._dash_embedding_client = DashEmbeddingClient(request_id=self.config.request_id,
                                                              dash_scope_uid=self.config.uid,
                                                              authorization=self.config.api_key,
                                                              workspace=self.config.workspace_id,
                                                              env_type=self.env_type,
                                                              max_retry_count=self.config.dash_embedding_retry_cnt)
        return self._dash_embedding_client

    @property
    def gene_client(self):
        if self._dash_generate_client is None:
            self._dash_generate_client = DashGenerateClient(request_id=self.config.request_id,
                                                            dash_scope_uid=self.config.uid,
                                                            authorization=self.config.api_key,
                                                            workspace=self.config.workspace_id,
                                                            env_type=self.env_type,
                                                            max_retry_count=self.config.dash_generate_retry_cnt)
        return self._dash_generate_client

    @property
    def rerank_client(self):
        if self._dash_rerank_client is None:
            self._dash_rerank_client = DashReRankClient(request_id=self.config.request_id,
                                                        dash_scope_uid=self.config.uid,
                                                        authorization=self.config.api_key,
                                                        workspace=self.config.workspace_id,
                                                        env_type=self.env_type,
                                                        max_retry_count=self.config.dash_rerank_retry_cnt)
        return self._dash_rerank_client

    @property
    def es_client(self):
        if self._es_client is None:
            self._es_client = ElasticSearchClient(es_user_name=self.config.es_user_name,
                                                  es_password=self.config.es_password,
                                                  es_index_name=self.config.es_index_name,
                                                  embedding_client=self.emb_client,
                                                  max_retries=self.config.es_retry_cnt)
        return self._es_client

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
