from typing import List

from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

from memoryscope.core.models.base_model import BaseModel, MODEL_REGISTRY
from memoryscope.enumeration.model_enum import ModelEnum
from memoryscope.scheme.model_response import ModelResponse
from memoryscope.core.utils.logger import Logger


class LlamaIndexRankModel(BaseModel):
    """
    The LlamaIndexRankModel class is designed to rerank documents according to their relevance
    to a provided query, utilizing the DashScope Rerank model. It transforms document lists
    and queries into a compatible format for ranking, manages the ranking process, and allocates
    rank scores to individual documents.
    """
    m_type: ModelEnum = ModelEnum.RANK_MODEL

    MODEL_REGISTRY.register("dashscope_rank", DashScopeRerank)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = Logger.get_logger("llama_index_rank_model")

    def before_call(self, model_response: ModelResponse, **kwargs):
        """
        Prepares necessary data before the ranking call by extracting the query and documents,
        ensuring they are valid, and initializing nodes with dummy scores.

        Args:
            model_response: model response
            **kwargs: Keyword arguments containing 'query' and 'documents'.
        """
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        if isinstance(documents, str):
            documents = [documents]
        assert query and documents and all(documents), \
            f"query or documents is empty! query={query}, documents={len(documents)}"
        assert len(documents) < 500, \
            "The input documents of Dashscope rerank model should not larger than 500!"
        # Using -1.0 as dummy scores
        nodes = [NodeWithScore(node=Node(text=doc), score=-1.0) for doc in documents]

        model_response.meta_data.update({
            "data": {"nodes": nodes, "query_str": query, "top_n": len(documents)},
            "documents_map": {doc: idx for idx, doc in enumerate(documents)},
        })

    def after_call(self, model_response: ModelResponse, **kwargs) -> ModelResponse:
        """
        Processes the model response post-ranking, assigning calculated rank scores to each document
        based on their index in the original document list.

        Args:
            model_response (ModelResponse): The initial response from the ranking model.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            ModelResponse: Updated response with rank scores assigned to documents.
        """
        if not model_response.rank_scores:
            model_response.rank_scores = {}

        documents_map = model_response.meta_data["documents_map"]
        for node in model_response.raw:
            text = node.node.text
            idx = documents_map[text]
            model_response.rank_scores[idx] = node.score

        self.logger.info(self.logger.format_rank_message(model_response))
        return model_response

    def _call(self, model_response: ModelResponse, **kwargs):
        """
        Executes the ranking process by passing prepared data to the model's postprocessing method.

        Args:
            **kwargs: Keyword arguments (unused).

        Returns:
            ModelResponse: A response object encapsulating the ranked nodes.
        """
        self.model.top_n = model_response.meta_data["data"]["top_n"]
        model_response.meta_data["data"].pop("top_n")
        model_response.raw = self.model.postprocess_nodes(**model_response.meta_data["data"])

    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        Asynchronous wrapper for the `_call` method, maintaining the same functionality.

        Args:
            **kwargs: Keyword arguments (unused).

        Returns:
            ModelResponse: A response object encapsulating the ranked nodes.
        """
        raise NotImplementedError
