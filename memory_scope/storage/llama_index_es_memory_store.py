import warnings
from typing import Dict, List, Any, Optional, cast

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode, NodeWithScore
from llama_index.vector_stores.elasticsearch import AsyncDenseVectorStrategy

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.storage.llama_index_sync_elasticsearch import SyncElasticsearchStore
from memory_scope.utils.logger import Logger


class _AsyncDenseVectorStrategy(AsyncDenseVectorStrategy):
    def _hybrid(self, query: str, knn: Dict[str, Any], filter: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
        # Add a query to the knn query.
        # RRF is used to even the score from the knn query and text query
        # RRF has two optional parameters: {'rank_constant':int, 'window_size':int}
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        query_body = {
            "knn": knn,
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                self.text_field: {
                                    "query": query,
                                }
                            }
                        }
                    ],
                    "filter": filter,
                }
            },
        }

        if isinstance(self.rrf, Dict):
            query_body["rank"] = {"rrf": self.rrf}
        elif isinstance(self.rrf, bool) and self.rrf is True:
            query_body["rank"] = {"rrf": {"window_size": top_k}}
        return query_body

    def es_query(
            self,
            *,
            query: Optional[str],
            query_vector: Optional[List[float]],
            text_field: str,
            vector_field: str,
            k: int,
            num_candidates: int,
            filter: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if filter is None:
            filter = []

        knn = {
            "filter": filter,
            "field": vector_field,
            "k": k,
            "num_candidates": num_candidates,
        }

        if query_vector is not None:
            knn["query_vector"] = query_vector
        else:
            # Inference in Elasticsearch. When initializing we make sure to always have
            # a model_id if we don't have an embedding_service.
            knn["query_vector_builder"] = {
                "text_embedding": {
                    "model_id": self.model_id,
                    "model_text": query,
                }
            }

        if self.hybrid:
            return self._hybrid(query=cast(str, query), knn=knn, filter=filter, top_k=k)

        return {"knn": knn}


def _to_elasticsearch_filter(standard_filters: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Converts standard Llama-index filters into a format compatible with Elasticsearch.

    This function transforms dictionary-based filters, where each key represents a field and 
    the value is a list of strings, into an Elasticsearch query structure. It supports both 
    list values (interpreted as 'should' clauses for OR logic) and single values (interpreted 
    as 'must' clauses for AND logic).

    Args:
        standard_filters (Dict[str, List[str]]): A dictionary containing filter criteria, 
            where keys are field names and values are lists of strings or single string values 
            representing filter values.

    Returns:
        Dict[str, Any]: A dictionary structured as an Elasticsearch filter query.
    """
    result = {
        "bool": {}
    }
    for key, value in standard_filters.items():
        if isinstance(value, list):
            operands = []
            for v in value:
                key_str = f"metadata.{key}.keyword" if isinstance(v, str) else f"metadata.{key}"
                operands.append(
                    {
                        "term":
                            {
                                key_str: {"value": v}
                            }
                    }
                )
            result['bool'].update({"should": operands})  # ⭐ Add 'should' clause for OR logic
            result['bool'].update({"minimum_should_match": 1})  # Ensure at least one 'should' match
        else:
            key_str = f"metadata.{key}.keyword" if isinstance(value, str) else f"metadata.{key}"
            operand = [{
                "term": {
                    key_str: {
                        "value": value,
                    }
                }
            }]
            if "must" in result['bool']:
                result['bool']['must'].extend(operand)  # Extend existing 'must' clause for AND logic
            else:
                result['bool'].update({"must": operand})  # Initialize 'must' clause if not present
    return result


class LlamaIndexEsMemoryStore(BaseMemoryStore):

    def __init__(self,
                 embedding_model: BaseModel,
                 index_name: str,
                 es_url: str,
                 use_hybrid: bool = True,
                 **kwargs):

        self.embedding_model: BaseModel = embedding_model
        self.es_store = SyncElasticsearchStore(index_name=index_name,
                                               es_url=es_url,
                                               retrieval_strategy=_AsyncDenseVectorStrategy(hybrid=use_hybrid),
                                               **kwargs)
        # TODO The llamaIndex utilizes some deprecated functions, hence langchain logs warning messages. By
        #  adding the following lines of code, the display of deprecated information is suppressed.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.index = VectorStoreIndex.from_vector_store(vector_store=self.es_store,
                                                            embed_model=self.embedding_model.model)

        self.index.build_index_from_nodes([TextNode(text="text")])
        self.logger = Logger.get_logger()

    def retrieve_memories(self,
                          query: str,
                          top_k: int,
                          filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(vector_store_kwargs={"es_filter": es_filter}, similarity_top_k=top_k,
                                            sparse_top_k=top_k)
        text_nodes = retriever.retrieve(query)
        return [self._text_node_2_memory_node(n) for n in text_nodes]

    async def a_retrieve_memories(self,
                                  query: str,
                                  top_k: int,
                                  filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        self.logger.info(f"query={query} top_k={top_k} filter_dict={filter_dict}")

        if filter_dict is None:
            filter_dict = {}
        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(
            vector_store_kwargs={"es_filter": es_filter},
            similarity_top_k=top_k)
        text_nodes: List[NodeWithScore] = await retriever.aretrieve(query)
        return [self._text_node_2_memory_node(n) for n in text_nodes]

    def batch_insert(self, nodes: List[MemoryNode]):
        # TODO batch insert
        for node in nodes:
            self.insert(node)

    def batch_update(self, nodes: List[MemoryNode], update_embedding: bool = True):
        # TODO batch_update & update_embedding
        for node in nodes:
            self.update(node, update_embedding=update_embedding)

    def batch_delete(self, nodes: List[MemoryNode]):
        # TODO batch_delete
        for node in nodes:
            self.delete(node)

    def insert(self, node: MemoryNode):
        self.index.insert_nodes([self._memory_node_2_text_node(node)])

    def delete(self, node: MemoryNode):
        return self.es_store.delete(node.memory_id)

    def update(self, node: MemoryNode, update_embedding: bool = True):
        # TODO update without embedding?
        self.delete(node)
        self.insert(node)

    def close(self):
        """
        Closes the Elasticsearch store, releasing any resources associated with it.
        """
        self.es_store.close()

    @staticmethod
    def _memory_node_2_text_node(memory_node: MemoryNode) -> TextNode:
        """
        Converts a MemoryNode object into a TextNode object.

        Args:
            memory_node (MemoryNode): The MemoryNode to be converted.

        Returns:
            TextNode: The converted TextNode with content and metadata from the MemoryNode.
        """
        return TextNode(id_=memory_node.memory_id,
                        text=memory_node.content,
                        metadata=memory_node.model_dump(exclude={"content"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        """
        Converts a NodeWithScore object into a MemoryNode object.

        Args:
            text_node (NodeWithScore): The NodeWithScore to be converted, typically retrieved from search results.

        Returns:
            MemoryNode: The converted MemoryNode with text and metadata from the NodeWithScore.
        """
        return MemoryNode(content=text_node.text, **text_node.metadata)
