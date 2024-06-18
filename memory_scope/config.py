
import json

from pipeline.memory_service import MemoryService
from utils.tool_functions import init_instance_by_config


class Wrapper:
    """Wrapper class for anything that needs to set up during init"""

    def __init__(self):
        self._provider = None

    def register(self, provider):
        self._provider = provider

    def __getattr__(self, key: str):
        if self.__dict__.get("_provider", None) is None:
            raise AttributeError("Please run __init__ first!")
        return getattr(self._provider, key)

C = Wrapper()

def init(config_path: str):
    config = json.loads(config_path)
    C.register(config)

    ## register workers
    C.worker = json.loads(C.worker)

    ## register services
    for k,v in C.pipeline.items():
        C.pipeline[k] = MemoryService(k)

