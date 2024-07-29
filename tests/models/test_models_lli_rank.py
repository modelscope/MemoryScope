import asyncio
import unittest

from memoryscope.core.models.llama_index_rank_model import LlamaIndexRankModel


class TestLLIReRank(unittest.TestCase):
    """Tests for LlamaIndexRerankModel"""

    def setUp(self):
        config = {
            "module_name": "dashscope_rank",
            "model_name": "gte-rerank",
            "clazz": "models.llama_index_rerank_model"
        }
        self.reranker = LlamaIndexRankModel(**config)

    def test_rerank(self):
        query = "吃啥？"
        documents = ["您吃了吗？",
                     "吃了吗您？"]
        result = self.reranker.call(
            documents=documents,
            query=query)
        print(result)

    def test_async_rerank(self):
        query = "吃啥？"
        documents = ["您吃了吗？",
                     "吃了吗您？"]
        result = asyncio.run(self.reranker.async_call(
            documents=documents,
            query=query))
        print(result)
