import random
from typing import Dict, List

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode, NodeWithScore, QueryBundle

from memoryscope.core.models.base_model import BaseModel
from memoryscope.core.storage.base_memory_store import BaseMemoryStore
from memoryscope.core.storage.llama_index_sync_elasticsearch import (SyncElasticsearchStore,
                                                                     ESCombinedRetrieveStrategy,
                                                                     _to_elasticsearch_filter,
                                                                     SPECIAL_QUERY)
from memoryscope.core.utils.logger import Logger
from memoryscope.scheme.memory_node import MemoryNode


class LlamaIndexEsMemoryStore(BaseMemoryStore):

    def __init__(self,
                 embedding_model: BaseModel,
                 index_name: str,
                 es_url: str,
                 retrieve_mode: str = "dense",
                 hybrid_alpha: float = None,
                 **kwargs):
        self.emb_dims = None
        self.index_name = index_name
        self.embedding_model: BaseModel = embedding_model
        retrieval_strategy = ESCombinedRetrieveStrategy(retrieve_mode=retrieve_mode, hybrid_alpha=hybrid_alpha)
        self.es_store = SyncElasticsearchStore(index_name=index_name,
                                               es_url=es_url,
                                               retrieval_strategy=retrieval_strategy,
                                               **kwargs)

        # TODO The llamaIndex utilizes some deprecated functions, hence langchain logs warning messages. By
        #  adding the following lines of code, the display of deprecated information is suppressed.
        self.index = VectorStoreIndex.from_vector_store(vector_store=self.es_store,
                                                        embed_model=self.embedding_model.model)

        self.logger = Logger.get_logger()

    def retrieve_memories(self,
                          query: str = "",
                          top_k: int = 3,
                          filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        # if index is not created, return []
        exists = self.es_store.client.indices.exists(index=self.index_name)
        if not exists:
            return []

        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(vector_store_kwargs={"es_filter": es_filter, "fields": ['embedding']},
                                            similarity_top_k=top_k,
                                            sparse_top_k=top_k)

        if not query:
            query = SPECIAL_QUERY

        if not query and self.emb_dims:
            query = QueryBundle(query_str=SPECIAL_QUERY, embedding=self.dummy_query_vector())

        text_nodes = retriever.retrieve(query)
        if text_nodes and text_nodes[0].embedding:
            self.emb_dims = len(text_nodes[0].embedding)

        return [self._text_node_2_memory_node(n) for n in text_nodes]

    async def a_retrieve_memories(self,
                                  query: str = "",
                                  top_k: int = 3,
                                  filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        # if index is not created, return []
        exists = self.es_store.client.indices.exists(index=self.index_name)
        if not exists:
            return []

        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(vector_store_kwargs={"es_filter": es_filter, "fields": ['embedding']},
                                            similarity_top_k=top_k,
                                            sparse_top_k=top_k)

        if not query:
            query = SPECIAL_QUERY

        if not query:
            query = QueryBundle(query_str=SPECIAL_QUERY, embedding=self.dummy_query_vector())

        text_nodes: List[NodeWithScore] = await retriever.aretrieve(query)

        if text_nodes and text_nodes[0].embedding:
            self.emb_dims = len(text_nodes[0].embedding)

        return [self._text_node_2_memory_node(n) for n in text_nodes]

    def batch_insert(self, nodes: List[MemoryNode]):
        # TODO batch insert
        for node in nodes:
            self.insert(node)

    def batch_update(self, nodes: List[MemoryNode], update_embedding: bool = True):
        # TODO batch_update
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
        if update_embedding:
            node.vector = []

        self.delete(node)
        self.insert(node)

    def close(self):
        """
        Closes the Elasticsearch store, releasing any resources associated with it.
        """
        self.es_store.close()

    def dummy_query_vector(self):
        random_floats = [random.uniform(0, 1) for _ in range(self.emb_dims)]
        return random_floats

    @staticmethod
    def _memory_node_2_text_node(memory_node: MemoryNode) -> TextNode:
        """
        Converts a MemoryNode object into a TextNode object.

        Args:
            memory_node (MemoryNode): The MemoryNode to be converted.

        Returns:
            TextNode: The converted TextNode with content and metadata from the MemoryNode.
        """
        embedding = memory_node.vector
        if not embedding:
            embedding = None
        return TextNode(id_=memory_node.memory_id,
                        text=memory_node.content,
                        embedding=embedding,
                        metadata=memory_node.model_dump(exclude={"content",
                                                                 "vector",
                                                                 "score_recall",
                                                                 "score_rank",
                                                                 "score_rerank"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        """
        Converts a NodeWithScore object into a MemoryNode object.

        Args:
            text_node (NodeWithScore): The NodeWithScore to be converted, typically retrieved from search results.

        Returns:
            MemoryNode: The converted MemoryNode with text and metadata from the NodeWithScore.
        """
        text_node.metadata["vector"] = text_node.embedding if text_node.embedding else []
        text_node.metadata["score_recall"] = text_node.score
        return MemoryNode(content=text_node.text, **text_node.metadata)
