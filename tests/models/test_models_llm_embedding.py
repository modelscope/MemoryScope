import unittest
from memory_scope.models.base_embedding_model import LLIEmbedding

class TestLLIEmbedding(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        config = {
            "method_type": "DashScopeEmbedding",
            "model_name": "text-embedding-v2",
            "clazz": "models.base_embedding_model"
        }
        self.emb = LLIEmbedding(**config)
    
    def test_single_embedding(self):
        text = "您吃了吗？"
        embs = self.emb.call(text=text)

    def test_batch_embedding(self):
        text = ["您吃了吗？", 
                "吃了吗您？"]
        embs = self.emb.call(text=text)

        