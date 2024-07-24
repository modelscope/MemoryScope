import warnings
import random
from typing import Dict, List, Any, Optional, cast

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode, NodeWithScore, QueryBundle

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_memory_store import BaseMemoryStore
from memory_scope.storage.llama_index_sync_elasticsearch import SyncElasticsearchStore, _AsyncDenseVectorStrategy, _to_elasticsearch_filter
from memory_scope.utils.logger import Logger


class LlamaIndexEsMemoryStore(BaseMemoryStore):

    def __init__(self,
                 embedding_model: BaseModel,
                 index_name: str,
                 es_url: str,
                 use_hybrid: bool = True,
                 emb_dims: int = 1536,
                 **kwargs):
        self.index_name = index_name
        self.emb_dims = emb_dims
        self.embedding_model: BaseModel = embedding_model
        self.es_store = SyncElasticsearchStore(index_name=index_name,
                                               es_url=es_url,
                                               retrieval_strategy=_AsyncDenseVectorStrategy(hybrid=use_hybrid),
                                               **kwargs)
        # TODO The llamaIndex utilizes some deprecated functions, hence langchain logs warning messages. By
        #  adding the following lines of code, the display of deprecated information is suppressed.
        
        self.index = VectorStoreIndex.from_vector_store(vector_store=self.es_store,
                                                        embed_model=self.embedding_model.model)

        self.logger = Logger.get_logger()

    def retrieve_memories(self,
                          query: Optional[str] = None,
                          top_k: int = 3,
                          filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        # if index is not created, return []
        exists = self.es_store._store.client.indices.exists(index=self.index_name)
        if not exists:
            return []
        
        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(vector_store_kwargs={"es_filter": es_filter, "fields": ['embedding']}, 
                                            similarity_top_k=top_k,
                                            sparse_top_k=top_k, )
        if query is None:
            query = QueryBundle(query_str='**--**',
                                embedding=self.dummy_query_vector())
            
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
        
        if query is None:
            query = QueryBundle(query_str='**--**',
                                embedding=self.dummy_query_vector())
            
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

    def delete_conditional(self, filter_dict: Dict = {}):
        nodes = self.retrieve_memories(filter_dict=filter_dict, top_k=10000)
        self.batch_delete(nodes)

    def update(self, node: MemoryNode, update_embedding: bool = True):
        # TODO update without embedding?
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
                        metadata=memory_node.model_dump(exclude={"content", "vector"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        """
        Converts a NodeWithScore object into a MemoryNode object.

        Args:
            text_node (NodeWithScore): The NodeWithScore to be converted, typically retrieved from search results.

        Returns:
            MemoryNode: The converted MemoryNode with text and metadata from the NodeWithScore.
        """
        embedding = text_node.embedding
        print("textnode embedding", embedding)
        if not embedding:
            embedding = []
        return MemoryNode(content=text_node.text, vector=embedding, **text_node.metadata)
