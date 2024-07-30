import sys

sys.path.append(".")  # noqa: E402

import asyncio
import unittest

from memoryscope.core.models.llama_index_embedding_model import LlamaIndexEmbeddingModel
from memoryscope.core.utils.logger import Logger


class TestLLIEmbedding(unittest.TestCase):
    """Tests for LlamaIndexEmbeddingModel"""

    def setUp(self):
        config = {
            "module_name": "openai_embedding",
            "model_name": "text-embedding-3-large",
            "clazz": "models.base_embedding_model"
        }
        self.emb = LlamaIndexEmbeddingModel(**config)
        self.logger = Logger.get_logger()

    def test_single_embedding(self):
        text = "您吃了吗？"
        result = self.emb.call(text=text)
        self.logger.info(result.m_type)
        self.logger.info(len(result.embedding_results))

    def test_batch_embedding(self):
        texts = ["您吃了吗？",
                 "吃了吗您？"]
        result = self.emb.call(text=texts)
        print()
        self.logger.info(result)

    def test_async_embedding(self):
        texts = ["您吃了吗？",
                 "吃了吗您？"]
        # 调用异步函数并等待其结果
        result = asyncio.run(self.emb.async_call(text=texts))
        print()
        self.logger.info(result)
