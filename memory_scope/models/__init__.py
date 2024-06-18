from utils.registry import Registry

from llama_index.embeddings.dashscope import (
    DashScopeEmbedding,
)
# from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

from llama_index.llms.dashscope import DashScope # type: ignore


EMB = Registry('embedding')
EMB.register_module(DashScopeEmbedding)

# RERANKER = Registry('reranker')
# RERANKER.register_module(DashScopeRerank)

LLM = Registry('llm')
LLM.register_module(DashScope)
