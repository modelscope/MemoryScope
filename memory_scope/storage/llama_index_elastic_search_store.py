from typing import Dict, List, Any

from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import VectorStoreQuery
from llama_index.core import VectorStoreIndex, StorageContext, ServiceContext
from llama_index.vector_stores.elasticsearch import ElasticsearchStore, AsyncDenseVectorStrategy
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter, VectorStoreQueryMode
from memory_scope.models.base_model import BaseModel
from memory_scope.storage.base_vector_store import BaseVectorStore
from memory_scope.scheme.memory_node import MemoryNode


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
        return await self._store.delete(
            query={"term": {"_id": ref_doc_id}}, **delete_kwargs
        )


def _to_elasticsearch_filter(standard_filters: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Convert standard filters to Elasticsearch filter.

    Args:
        standard_filters: Standard Llama-index filters.

    Returns:
        Elasticsearch filter.
    """

    result = {
        "bool" : {}
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


class LlamaIndexElasticSearchStore(BaseVectorStore):
    def __init__(self, 
                 index_name: str, 
                 embedding_model: BaseModel, 
                 content_key: str = "text", 
                 **kwargs):

        self.index_name: str = index_name
        self.embedding_model: BaseModel = embedding_model

        self.es_store = _ElasticsearchStore(index_name=self.index_name,
                                           retrieval_strategy=AsyncDenseVectorStrategy(hybrid=True),
                                           **kwargs)
        
        self.service_context = ServiceContext.from_defaults(embed_model=self.embedding_model, llm=None)
        self.index = VectorStoreIndex.from_vector_store(vector_store=self.es_store,
                                                        service_context=self.service_context)
        
    
    def retrieve(self, query: str, top_k: int = 3, filter_dict: Dict[str, List[str]] = {}) -> MemoryNode:
        
        filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(
            vector_store_kwargs={
               "es_filter": filter
            },
            similarity_top_k=top_k
        )
        textnodes = retriever.retrieve(query)
        results = self._textnodes2memorynodes(textnodes)

        return results
    
    async def async_retrieve(self, query: str, top_k: int = 3, filter_dict: Dict[str, List[str]] = {}) -> MemoryNode:
        filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(
            vector_store_kwargs={
               "es_filter": filter
            },
            similarity_top_k=top_k
        )
        textnodes = await retriever.aretrieve(query)
        results = self._textnodes2memorynodes(textnodes)

        return results
    
    def insert(self, node: MemoryNode):
        node = self._memorynode2textnode(node)
        self.index.insert_nodes([node])

    def insert_batch(self, node: MemoryNode) -> None:
        raise NotImplementedError

    def delete(self, node: MemoryNode) -> None:
        memory_id = node.memory_id
        self.es_store.delete(memory_id)
   
    def update(self, node: MemoryNode) -> None:
        self.delete(node)
        self.insert(node)

    def flush(self):
        raise NotImplementedError
    
    def _memorynode2textnode(self, memory_node: MemoryNode) -> TextNode:
        content = memory_node.content
        memory_id = memory_node.memory_id
        meta = memory_node.model_dump(exclude={"content"})
        return TextNode(id_=memory_id, text=content, metadata=meta)

    def _textnode2memorynode(self, text_node: TextNode) -> MemoryNode:
        content = text_node.text
        meta = text_node.metadata   
        mem_node = MemoryNode(content=content, **meta)
        return mem_node

    def _textnodes2memorynodes(self, text_nodes: TextNode) -> MemoryNode:
        mem_nodes = [self._textnode2memorynode(node) for node in text_nodes]
        return mem_nodes
        
