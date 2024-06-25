import asyncio
import unittest

from memory_scope.models.llama_index_embedding_model import LlamaIndexEmbeddingModel


class TestLLIEmbedding(unittest.TestCase):
    """Tests for LlamaIndexEmbeddingModel"""

    def setUp(self):
        config = {
            "method_type": "DashScopeEmbedding",
            "model_name": "text-embedding-v2",
            "clazz": "models.base_embedding_model"
        }
        self.emb = LlamaIndexEmbeddingModel(**config)

    def test_single_embedding(self):
        text = "您吃了吗？"
        result = self.emb.call(text=text)
        print(result)

    def test_batch_embedding(self):
        texts = ["您吃了吗？",
                 "吃了吗您？"]
        result = self.emb.call(text=texts)
        print(result)

    def test_async_embedding(self):
        texts = ["您吃了吗？",
                 "吃了吗您？"]
        # 调用异步函数并等待其结果
        result = asyncio.run(self.emb.async_call(text=texts))
        print(result)
