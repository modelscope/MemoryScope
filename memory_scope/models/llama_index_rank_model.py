from typing import List

from llama_index.core.data_structs import Node
from llama_index.core.schema import NodeWithScore
from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

from memory_scope.enumeration.model_enum import ModelEnum
from memory_scope.models.base_model import BaseModel, MODEL_REGISTRY
from memory_scope.scheme.model_response import ModelResponse


class LlamaIndexRankModel(BaseModel):
    """
    The LlamaIndexRankModel class is designed to rerank documents according to their relevance
    to a provided query, utilizing the DashScope Rerank model. It transforms document lists
    and queries into a compatible format for ranking, manages the ranking process, and allocates
    rank scores to individual documents.
    """
    m_type: ModelEnum = ModelEnum.RANK_MODEL

    MODEL_REGISTRY.register("dashscope_rank", DashScopeRerank)

    def before_call(self, **kwargs) -> None:
        """
        Prepares necessary data before the ranking call by extracting the query and documents,
        ensuring they are valid, and initializing nodes with dummy scores.

        Args:
            **kwargs: Keyword arguments containing 'query' and 'documents'.
        """
        query: str = kwargs.pop("query", "")
        documents: List[str] = kwargs.pop("documents", [])
        if isinstance(documents, str):
            documents = [documents]

        assert query and documents, f"query or documents is empty! query={query}, documents={len(documents)}"

        # Using -1.0 as dummy scores
        nodes = [NodeWithScore(node=Node(text=doc), score=-1.0) for doc in documents]
        self._get_documents_mapping(documents)

        self.data = {"nodes": nodes, "query_str": query}

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

        for node in model_response.raw:
            text = node.node.text
            idx = self.documents_map[text]
            model_response.rank_scores[idx] = node.score
        return model_response

    def _call(self, **kwargs) -> ModelResponse:
        """
        Executes the ranking process by passing prepared data to the model's postprocessing method.

        Args:
            **kwargs: Keyword arguments (unused).

        Returns:
            ModelResponse: A response object encapsulating the ranked nodes.
        """
        return ModelResponse(m_type=self.m_type, raw=self.model.postprocess_nodes(**self.data))

    async def _async_call(self, **kwargs) -> ModelResponse:
        """
        Asynchronous wrapper for the `_call` method, maintaining the same functionality.

        Args:
            **kwargs: Keyword arguments (unused).

        Returns:
            ModelResponse: A response object encapsulating the ranked nodes.
        """
        return self._call(**kwargs)

    def _get_documents_mapping(self, documents):
        """
        Generates a mapping of each document to its index within the provided document list.

        Args:
            documents (List[str]): The list of documents.
        """
        self.documents_map = {}
        for idx, doc in enumerate(documents):
            self.documents_map[doc] = idx
