import sys

sys.path.append(".")  # noqa: E402

import unittest
import time
import asyncio
from memoryscope.scheme.message import Message
from memoryscope.models.llama_index_generation_model import LlamaIndexGenerationModel
from memoryscope.utils.logger import Logger


class TestLLILLM(unittest.TestCase):
    """Tests for LlamaIndexGenerationModel"""

    def setUp(self):
        config = {
            "module_name": "dashscope_generation",
            "model_name": "qwen-max",
            "clazz": "models.llama_index_generation_model",
            "max_tokens": 2000,
            "top_k": 1,
            "seed": 1234,
        }
        self.llm = LlamaIndexGenerationModel(**config)
        self.logger = Logger.get_logger()

    def test_llm_prompt(self):
        prompt = "你是谁？"
        ans = self.llm.call(stream=False, prompt=prompt)
        self.logger.info(ans.message.content)

    def test_llm_messages(self):
        messages = [Message(role="system", content="you are a helpful assistant."),
                    Message(role="user", content="你如何看待黄金上涨？")]
        ans = self.llm.call(stream=False, messages=messages)
        self.logger.info(ans.message.content)

    def test_llm_prompt_stream(self):
        prompt = "你如何看待黄金上涨？"
        ans = self.llm.call(stream=True, prompt=prompt)
        self.logger.info("-----start-----")
        for a in ans:
            sys.stdout.write(a.delta)
            sys.stdout.flush()
            time.sleep(0.1)
        self.logger.info("-----end-----")

    def test_llm_messages_stream(self):
        messages = [Message(role="system", content="you are a helpful assistant."),
                    Message(role="user", content="你如何看待黄金上涨？")]
        ans = self.llm.call(stream=True, messages=messages)
        self.logger.info("-----start-----")
        for a in ans:
            sys.stdout.write(a.delta)
            sys.stdout.flush()
            time.sleep(0.1)
        self.logger.info("-----end-----")

    def test_async_llm_messages(self):

        messages = [Message(role="system", content="you are a helpful assistant."),
                    Message(role="user", content="你如何看待黄金上涨？")]

        ans = asyncio.run(self.llm.async_call(messages=messages))
        self.logger.info(ans.message.content)
