
import json
from pydantic import BaseModel

from models.dash_embedding_client import DashEmbeddingClient
from models.dash_generate_client import DashGenerateClient
from models.dash_rerank_client import DashReRankClient
from models.elastic_search_client import ElasticSearchClient
from pipeline.memory_service import MemoryService
from enumeration.memory_type_enum import MemoryTypeEnum
from utils.tool_functions import init_instance_by_config

class Wrapper:
    """Wrapper class for anything that needs to set up during init"""

    def __init__(self):
        self._provider = None

    def register(self, provider):
        self._provider = provider

    def __getattr__(self, key):
        if self.__dict__.get("_provider", None) is None:
            raise AttributeError("Please run init() first using qlib")
        return getattr(self._provider, key)

class Config(BaseModel):
    thread_pool_max_count: int = 5
    pipeline: dict = {
        "retrive": """
parse_params,es.load_profile,[retrieve.extract_time|es.es_similar|es.es_keyword],retrieve.semantic_rank,retrieve.fuse_rerank
""".strip(),
        "summary_long": """
parse_params,summary_short.info_filter,[es.es_today_obs|summary_short.get_observation|summary_short.get_observation_with_time],summary_short.contra_repeat,memory_store
""".strip(),
        "summary_short": """
parse_params,[es.load_profile|es.es_new_obs|es.es_insight],[summary_long.update_insight|summary_long.get_reflection,summary_long.get_insight|summary_long.update_profile],summary_long.summary_collect,memory_store
""".strip()
    }
    model_embedding = _default_embedding_client
    model_generate = _default_generate_client
    model_rerank = _default_rerank_client
    db = _default_es_client

class UserConfig(BaseModel):
    memory_id: str = ""

C = Wrapper()

def init(config_path):
    config = json.loads(config_path)
    C.register(Config(**config))

    # ## register modules
    C.model_embedding = init_instance_by_config(C.model_embedding)
    C.model_generate = init_instance_by_config(C.model_generate)
    C.model_rerank = init_instance_by_config(C.model_rerank)
    C.db = init_instance_by_config(C.db)

    ## register workers
    C.worker = json.loads(C.worker)

    ## register services
    for k,v in C.pipeline.items():
        C.pipeline[k] = MemoryService(k)

