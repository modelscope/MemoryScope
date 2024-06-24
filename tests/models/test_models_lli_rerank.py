import unittest
from memory_scope.models.base_rank_model import LLIReRank

class TestLLIReRank(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        config = {
            "method_type": "DashScopeRerank",
            "model_name": "gte-rerank",
            "clazz": "models.base_rank_model"
        }
        self.reranker = LLIReRank(**config)

    def test_rerank(self):
        query = "吃啥？"
        documents = ["您吃了吗？", 
                "吃了吗您？"]
        embs = self.reranker.call(
                             stream=False,
                             documents=documents,
                             query=query)
