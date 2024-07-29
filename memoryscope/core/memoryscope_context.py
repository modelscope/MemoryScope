from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from memoryscope.enumeration.language_enum import LanguageEnum


@dataclass
class MemoryscopeContext(object):
    """
    The context class archives all configs utilized by store, monitor, services and workers.
    """

    language: LanguageEnum = LanguageEnum.EN

    thread_pool: ThreadPoolExecutor | None = None

    memory_store = None

    monitor = None

    memory_chat_dict: dict = field(default_factory=lambda: {}, metadata={"help": "name -> memory_chat"})

    memory_service_dict: dict = field(default_factory=lambda: {}, metadata={"help": "name -> memory_service"})

    model_dict: dict = field(default_factory=lambda: {}, metadata={"help": "name -> model"})

    worker_conf_dict: dict = field(default_factory=lambda: {}, metadata={"help": "name -> worker_conf"})

    meta_data: dict = field(default_factory=lambda: {})
