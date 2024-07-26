from dataclasses import dataclass, field
from typing import Literal, Dict


@dataclass
class MemoryscopeArguments(object):
    language: Literal["cn", "en"] = field(default="en", metadata={"help": "support en & cn now"})

    thread_pool_max_workers: int = field(default=5, metadata={"help": "thread pool max workers"})

    logger_name: str = field(default="memoryscope")

    logger_name_time_suffix: str = field(default="%Y%m%d_%H%M%S")

    memory_chat_class: str = field(default="chat.api_memory_chat", metadata={
        "help": "The memory chat class for dynamic import: chat.cli_memory_chat, chat.api_memory_chat"})

    human_name: str = field(default="user", metadata={"help": "en: user, cn: 用户"})

    assistant_name: str = field(default="AI")

    consolidate_memory_interval_time: int = field(default=1, metadata={
        "help": "If you feel that the token consumption is relatively high, please increase the time interval."})

    reflect_and_reconsolidate_interval_time: int = field(default=15, metadata={
        "help": "If you feel that the token consumption is relatively high, please increase the time interval."})

    worker_params: Dict[str, dict] = field(default_factory=lambda: {}, metadata={
        "help": "dict format: worker_name -> param_key -> param_value"})

    generation_backend: str = field(default="openai_generation", metadata={
        "help": "global generation backend: openai_generation, dashscope_generation, etc."})

    generation_model: str = field(default="gpt-4o", metadata={
        "help": "global generation model: gpt-4o, gpt-4, qwen-max, etc."})

    generation_params: dict = field(default_factory=lambda: {}, metadata={
        "help": "global generation params: max_tokens, top_p, temperature, etc."})

    embedding_backend: str = field(default="openai_embedding", metadata={
        "help": "global embedding backend: openai_embedding, dashscope_embedding, etc."})

    embedding_model: str = field(default="gpt-4o", metadata={
        "help": "global embedding model: text-embedding-ada-002, text-embedding-v2, etc."})

    embedding_params: dict = field(default_factory=lambda: {})

    rank_backend: str = field(default="dashscope_rank", metadata={"help": "global rank backend: dashscope_rank, etc."})

    rank_model: str = field(default="gte-rerank", metadata={"help": "global rank model: gte-rerank, etc."})

    rank_params: dict = field(default_factory=lambda: {})

    es_index_name: str = field(default="memory_index")

    es_url: str = field(default="http://localhost:9200")

    retrieve_mode: str = field(default="dense", metadata={
        "help": "retrieve_mode: dense, sparse(not implemented), hybrid(not implemented)"})

    hybrid_alpha: float | None = field(default=1.0, metadata={"help": ""})
