from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.llms.dashscope import DashScope as DashScopeLLM

from memory_scope.utils.registry import Registry

MODEL_REGISTRY = Registry("models")
MODEL_REGISTRY.batch_register([
    DashScopeEmbedding,
    DashScopeLLM,
])
