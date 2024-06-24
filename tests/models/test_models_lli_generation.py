import unittest

from memory_scope.models.llama_index_generation_model import LlamaIndexGenerationModel


class TestLLILLM(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        config = {
            "method_type": "DashScope",
            "model_name": "qwen-max",
            "clazz": "models.llama_index_generation_model"
        }
        self.llm = LlamaIndexGenerationModel(**config)

    def test_llm_prompt(self):
        prompt = "你是谁？"
        ans = self.llm.call(
            stream=False,
            prompt=prompt
        )
        print(ans.text)

    def test_llm_messages(self):
        messages = [{"role": "system", "content": "you are a helpful assistant."},
                    {"role": "user", "content": "你是谁？"}]
        ans = self.llm.call(
            stream=False,
            messages=messages
        )
        print(ans.text)

    def test_llm_prompt_stream(self):
        prompt = "你如何看待黄金上涨？"
        ans = self.llm.call(
            stream=True,
            prompt=prompt
        )
        import sys
        import time
        for a in ans:
            sys.stdout.write(a.delta)
            sys.stdout.flush()
            time.sleep(0.1)
        
    @unittest.skip('tmp')
    def test_llm_messages(self):
        messages = [{"role": "system", "content": "you are a helpful assistant."},
                    {"role": "user", "content": "你如何看待黄金上涨？"}]
        ans = self.llm.call(
            stream=True,
            messages=messages
        )
        import sys
        import time
        for a in ans:
            sys.stdout.write(a.delta)
            sys.stdout.flush()
            time.sleep(0.1)