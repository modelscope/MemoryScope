import sys

sys.path.append(".")

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from memory_scope.models.llama_index_embedding_model import LlamaIndexEmbeddingModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.llama_index_es_memory_store import LlamaIndexEsMemoryStore
from memory_scope.utils.logger import Logger

import questionary


class ThreadTest(object):
    def __init__(self):
        self.task_list = []
        config = {
            "module_name": "dashscope_embedding",
            "model_name": "text-embedding-v2",
            "clazz": "models.llama_index_embedding_model",
        }
        emb = LlamaIndexEmbeddingModel(**config)

        config = {
            "index_name": "0708_2",
            "es_url": "http://localhost:9200",
            "embedding_model": emb,
            "use_hybrid": True

        }
        self.es_store = LlamaIndexEsMemoryStore(**config)
        self.logger = Logger.get_logger("default")

    async def async_func(self, i: int):
        self.logger.info(f"i: {i}")
        await asyncio.sleep(i)
        self.es_store.insert(MemoryNode(
            content="xxxxxx",
            memory_type="profile",
            user_id="6",
            status="valid",
            memory_id="ggg567",
            meta_data={"5": "5"}
        ))

        result = self.es_store.retrieve_memories("_", top_k=10, filter_dict={"memory_id": "ggg567"})
        self.logger.info(f"result: {result}")

    def submit_async_task(self, fn, *args, **kwargs):
        self.task_list.append((fn, args, kwargs))

    def gather_async_result(self):
        async def async_gather():
            return await asyncio.gather(*[fn(*args, **kwargs) for fn, args, kwargs in self.task_list])

        results = asyncio.run(async_gather())
        self.task_list.clear()
        return results

    def run(self):
        self.submit_async_task(self.async_func, i=1)
        self.submit_async_task(self.async_func, i=2)
        self.submit_async_task(self.async_func, i=3)

        self.gather_async_result()
        self.logger.close()


executor = ThreadPoolExecutor(max_workers=5)
t = executor.submit(ThreadTest().run)
questionary.text(message="user:", multiline=False, qmark=">").unsafe_ask()

print(as_completed([t]))
executor.shutdown()
