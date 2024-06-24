import unittest
from memory_scope.models.llama_index_rerank_model import LlamaIndexRerankModel

class TestLLIReRank(unittest.TestCase):
    """Tests for LlamaIndexRerankModel"""

    def setUp(self):
        config = {
            "method_type": "DashScopeRerank",
            "model_name": "gte-rerank",
            "clazz": "models.llama_index_rerank_model"
        }
        self.reranker = LlamaIndexRerankModel(**config)

    def test_rerank(self):
        query = "吃啥？"
        documents = ["您吃了吗？", 
                "吃了吗您？"]
        embs = self.reranker.call(
                             stream=False,
                             documents=documents,
                             query=query)
        print(embs)