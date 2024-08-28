from dataclasses import dataclass, field
from typing import Literal, Dict

@dataclass
class Arguments(object):
    language: Literal["cn", "en"] = field(default="cn", metadata={"help": "support en & cn now"})

    thread_pool_max_workers: int = field(default=5, metadata={"help": "thread pool max workers"})

    memory_chat_class: str = field(default="cli_memory_chat", metadata={
        "help": "cli_memory_chat(Command-line interaction), api_memory_chat(API interface interaction), etc."})

    chat_stream: bool | None = field(default=None, metadata={
        "help": "In the case of cli_memory_chat, stream mode is recommended. For api_memory_chat mode, "
                "please use non-stream. If set to None, the value will be automatically determined."})

    human_name: str = field(default="user", metadata={"help": "Human user's name"})

    assistant_name: str = field(default="AI", metadata={"help": "assistant' name"})

    consolidate_memory_interval_time: int | None = field(default=1, metadata={
        "help": "Memory backend service: If you feel that the token consumption is relatively high, "
                "please increase the time interval. When set to None, the value will not be updated."})

    reflect_and_reconsolidate_interval_time: int | None = field(default=15, metadata={
        "help": "Memory backend service: If you feel that the token consumption is relatively high, "
                "please increase the time interval. When set to None, the value will not be updated."})

    worker_params: Dict[str, dict] = field(default_factory=lambda: {}, metadata={
        "help": "dict format: worker_name -> param_key -> param_value"})

    generation_backend: str = field(default="dashscope_generation", metadata={
        "help": "global generation backend: openai_generation, dashscope_generation, etc."})

    generation_model: str = field(default="gpt-4o", metadata={
        "help": "global generation model: gpt-4o, gpt-4o-mini, gpt-4-turbo, qwen-max, etc."})

    generation_params: dict = field(default_factory=lambda: {}, metadata={
        "help": "global generation params: max_tokens, top_p, temperature, etc."})

    embedding_backend: str = field(default="dashscope_generation", metadata={
        "help": "global embedding backend: openai_embedding, dashscope_embedding, etc."})

    embedding_model: str = field(default="text-embedding-3-small", metadata={
        "help": "global embedding model: text-embedding-3-large, text-embedding-3-small, text-embedding-ada-002, "
                "text-embedding-v2, etc."})

    embedding_params: dict = field(default_factory=lambda: {})

    rank_backend: str = field(default="dashscope_rank", metadata={"help": "global rank backend: dashscope_rank, etc."})

    rank_model: str = field(default="gte-rerank", metadata={"help": "global rank model: gte-rerank, etc."})

    rank_params: dict = field(default_factory=lambda: {})

    es_index_name: str = field(default="memory_index")

    es_url: str = field(default="http://localhost:9200")

    retrieve_mode: str = field(default="dense", metadata={
        "help": "retrieve_mode: dense, sparse(not implemented), hybrid(not implemented)"})

    enable_ranker: bool = field(default=False, metadata={
        "help": "If a semantic ranking model is not available, MemoryScope will use cosine similarity scoring as a "
                "substitute. However, the ranking effectiveness will be somewhat compromised.",
        "map_yaml": "global->enable_ranker"})

    enable_today_contra_repeat: bool = field(default=True, metadata={
        "help": "Whether enable conflict resolution and deduplication for the day? "
                "Note that enabling this will increase token consumption.",
        "map_yaml": "global->enable_today_contra_repeat"})

    enable_long_contra_repeat: bool = field(default=False, metadata={
        "help": "Whether to enable long-term conflict resolution and deduplication. "
                "Note that enabling this will increase token consumption.",
        "map_yaml": "global->enable_long_contra_repeat"})

    output_memory_max_count: int = field(default=20, metadata={
        "help": "The maximum number of memories retrieved during memory recall.",
        "map_yaml": "global->output_memory_max_count"})
