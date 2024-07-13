import ray

from typing import Dict, List, Any, Optional, cast

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode, NodeWithScore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore, AsyncDenseVectorStrategy

from memory_scope.enumeration.action_status_enum import ActionStatusEnum
from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.utils.logger import Logger

ray.init(ignore_reinit_error=True)


class _AsyncDenseVectorStrategy(AsyncDenseVectorStrategy):
    """
    Custom asynchronous dense vector strategy extending LlamaIndex's ElasticsearchStore's strategy.
    This strategy enables hybrid search combining KNN queries with text queries and supports customizable ranking functions.
    """

    def _hybrid(self, query: str, knn: Dict[str, Any], filter: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
        """
        Constructs a hybrid query body combining KNN search with a text query, and applies filters.

        Args:
            query (str): The text query to be combined with the KNN results.
            knn (Dict[str, Any]): The KNN query part specifying the vector search parameters.
            filter (List[Dict[str, Any]]): A list of filters to apply to the search.
            top_k (int): The number of top results to retrieve.

        Returns:
            Dict[str, Any]: The constructed query body for Elasticsearch to perform the hybrid search.
        """
        # Combines KNN query with a text query and applies optional RRF ranking for result balancing
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

        # Configures Rank-Risk Function (RRF) if enabled or specified, to balance scores between KNN and text matches
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


class _ElasticsearchStore(ElasticsearchStore):
    async def adelete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """
        Async delete node from Elasticsearch index.

        Args:
            ref_doc_id: ID of the node to delete.
            delete_kwargs: Optional. Additional arguments to
                        pass to AsyncElasticsearch delete_by_query.

        Raises:
            Exception: If AsyncElasticsearch delete_by_query fails.
        """
        return await self._store.delete(query={"term": {"_id": ref_doc_id}}, **delete_kwargs)


def _to_elasticsearch_filter(standard_filters: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Converts the provided standard Llama-index filters into an Elasticsearch compatible filter format.

    This function processes each key-value pair in the input dictionary. If the value is a list,
    it constructs a 'should' clause with multiple 'term' sub-clauses for each item in the list,
    requiring at least one to match. If the value is not a list, it forms a 'must' clause with a single 'term'
    sub-clause. The resulting structure is nested within a 'bool' clause which is the standard way to combine
    boolean logic in Elasticsearch queries.

    Args:
        standard_filters (Dict[str, List[str]]): A dictionary where keys represent filter fields and values are
                                                 either single values or lists of values to filter by.

    Returns:
        Dict[str, Any]: An Elasticsearch query filter dictionary ready to be used in a query.
    """
    result = {
        "bool": {}
    }
    for key, value in standard_filters.items():
        if isinstance(value, list):
            operands = []
            for v in value:
                operands.append(
                    {
                        "term":
                            {
                                f"metadata.{key}.keyword": {"value": v}
                            }
                    }
                )
            result['bool'].update({"should": operands})
            result['bool'].update({"minimum_should_match": 1})
        else:
            operand = [{
                "term": {
                    f"metadata.{key}.keyword": {
                        "value": value,
                    }
                }
            }]
            if "must" in result['bool']:
                result['bool']['must'].extend(operand)
            else:
                result['bool'].update({"must": operand})
    return result


# The following decorator '@ray.remote' is used to define a function or class that should be executed remotely
# by Ray. This facilitates parallel and distributed computation. However, due to the instruction constraints,
# no modification or additional explanation is provided for this part.
@ray.remote
class _LlamaIndexEsMemoryStore(BaseMemoryStore):

    def __init__(self,
                 embedding_model: dict,
                 index_name: str,
                 es_url: str,
                 use_hybrid: bool = True,
                 **kwargs):

        from memory_scope.models.llama_index_embedding_model import LlamaIndexEmbeddingModel
        embedding_model = LlamaIndexEmbeddingModel(**embedding_model)
        self.embedding_model: BaseModel = embedding_model
        self.es_store = _ElasticsearchStore(index_name=index_name,
                                            es_url=es_url,
                                            retrieval_strategy=_AsyncDenseVectorStrategy(hybrid=use_hybrid),
                                            **kwargs)
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

    async def a_retrieve_memories(self, query: str, top_k: int, filter_dict: Dict[str, List[str]]) -> List[MemoryNode]:
        pass

    def batch_insert(self, nodes: List[MemoryNode]):
        pass

    def batch_update(self, nodes: List[MemoryNode], update_embedding: bool = True):
        pass

    def batch_delete(self, nodes: List[MemoryNode]):
        pass

    def insert(self, node: MemoryNode):
        """
        Inserts a MemoryNode into the Elasticsearch store by converting it to aTextNode.

        Args:
            node (MemoryNode): The MemoryNode to be inserted into the store.
        """
        self.index.insert_nodes([self._memory_node_2_text_node(node)])

    def delete(self, node: MemoryNode):
        """
        Deletes a MemoryNode from the Elasticsearch store based on its memory_id.

        Args:
            node (MemoryNode): The MemoryNode to be deleted, identified by its memory_id.

        Returns:
            bool: The result of the deletion operation, typically True if successful.
        """
        memory_id = node.memory_id
        return self.es_store.delete(memory_id)

    def update(self, node: MemoryNode):
        self.delete(node)
        self.insert(node)

    def update_batch(self, nodes: List[MemoryNode]):
        for node in nodes:
            self.update(node)

    def close(self):
        """
        Closes the Elasticsearch store, releasing any resources associated with it.
        
        This method ensures that the connection to the Elasticsearch instance is properly closed,
        which is a good practice to prevent resource leaks when you're done interacting with the store.
        """
        self.es_store.close()

    @staticmethod
    def _memory_node_2_text_node(memory_node: MemoryNode) -> TextNode:
        """
        Converts a MemoryNode object into a TextNode object.

        Args:
            memory_node (MemoryNode): The MemoryNode to be converted.

        Returns:
            TextNode: The converted TextNode object with the content and metadata from the MemoryNode.
        """
        return TextNode(id_=memory_node.memory_id,
                        text=memory_node.content,
                        metadata=memory_node.model_dump(exclude={"content"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        """
        Converts a NodeWithScore object into a MemoryNode object.

        Args:
            text_node (NodeWithScore): The NodeWithScore to be converted.

        Returns:
            MemoryNode: The converted MemoryNode object with the text and metadata from the NodeWithScore.
        """
        return MemoryNode(content=text_node.text, **text_node.metadata)


class LlamaIndexEsMemoryStore():
    def __init__(self,
                 embedding_model: BaseModel,
                 index_name: str,
                 es_url: str,
                 use_hybrid: bool = True,
                 **kwargs):
        if 'embedding_model' in kwargs: kwargs.pop('embedding_model')
        self.proxy_obj = _LlamaIndexEsMemoryStore.remote(embedding_model.kwargs, index_name, es_url, use_hybrid,
                                                         **kwargs)

    def retrieve_memories(self,
                          query: str,
                          top_k: int,
                          filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        return ray.get(self.proxy_obj.retrieve_memories.remote(query, top_k, filter_dict))

    def insert(self, node: MemoryNode):
        return ray.get(self.proxy_obj.insert.remote(node))

    def delete(self, node: MemoryNode):
        return ray.get(self.proxy_obj.delete.remote(node))

    def update(self, node: MemoryNode):
        return ray.get(self.proxy_obj.update.remote(node))

    def update_batch(self, nodes: List[MemoryNode]) -> Any:
        """
        Updates a batch of memory nodes asynchronously using Ray.

        Args:
            nodes (List[MemoryNode]): A list of MemoryNode objects to be updated.

        Returns:
            Any: The result from the remote task once completed.
        """
        return ray.get(self.proxy_obj.update_batch.remote(nodes))

    def close(self) -> Any:
        """
        Closes the Elasticsearch memory store asynchronously using Ray.

        Returns:
            Any: The result from the remote task once completed.
        """
        return ray.get(self.proxy_obj.close.remote())

    def update_memories(self, nodes: MemoryNode | List[MemoryNode]) -> Any:
        """
        Updates one or more memory nodes asynchronously using Ray.

        Args:
            nodes (MemoryNode | List[MemoryNode]): A single MemoryNode or a list of MemoryNode objects to be updated.

        Returns:
            Any: The result from the remote task once completed.
        """
        return ray.get(self.proxy_obj.update_memories.remote(nodes))

    @staticmethod
    def _memory_node_2_text_node(memory_node: MemoryNode) -> TextNode:
        """
        Converts a MemoryNode object into a TextNode object.

        Args:
            memory_node (MemoryNode): The MemoryNode to convert.

        Returns:
            TextNode: The converted TextNode object with content and metadata.
        """
        return TextNode(id_=memory_node.memory_id,
                        text=memory_node.content,
                        metadata=memory_node.model_dump(exclude={"content"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        """
        Converts a TextNode (with score) into a MemoryNode object.

        Args:
            text_node (NodeWithScore): The TextNode to convert, which includes a 'score' attribute.

        Returns:
            MemoryNode: The converted MemoryNode object with content and metadata.
        """
        return MemoryNode(content=text_node.text, **text_node.metadata)
