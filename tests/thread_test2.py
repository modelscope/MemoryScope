import sys

sys.path.append(".")

import asyncio
from concurrent.futures import ThreadPoolExecutor

from memory_scope.models.llama_index_embedding_model import LlamaIndexEmbeddingModel
from memory_scope.storage.llama_index_es_memory_store import LlamaIndexEsMemoryStore
from memory_scope.utils.logger import Logger

logger = Logger.get_logger("default")


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
        self.logger = logger

    async def async_func(self, i: int):
        try:
            self.logger.info(f"i: {i}")
            await asyncio.sleep(i)
            # result = self.es_store.retrieve_memories("_", top_k=10, filter_dict={"memory_id": "ggg567"})
        except Exception as e:
            self.logger.exception(f"encounter error. e={e.args}")

    def submit_async_task(self, fn, *args, **kwargs):
        self.task_list.append((fn, args, kwargs))

    def gather_async_result(self):
        async def async_gather():
            return await asyncio.gather(*[fn(*args, **kwargs) for fn, args, kwargs in self.task_list])

        results = asyncio.run(async_gather())
        self.task_list.clear()
        return results

    def run(self):
        while True:
            self.submit_async_task(self.async_func, i=1)
            # self.submit_async_task(self.async_func, i=2)
            # self.submit_async_task(self.async_func, i=3)

            self.gather_async_result()


executor = ThreadPoolExecutor(max_workers=5)
t1 = executor.submit(ThreadTest().run)
executor.shutdown()
