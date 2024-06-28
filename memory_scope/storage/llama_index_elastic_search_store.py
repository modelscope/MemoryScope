from typing import Dict, List, Any

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode, NodeWithScore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore, AsyncDenseVectorStrategy

from memory_scope.models.base_model import BaseModel
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.base_vector_store import BaseVectorStore


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
    Convert standard filters to Elasticsearch filter.

    Args:
        standard_filters: Standard Llama-index filters.

    Returns:
        Elasticsearch filter.
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


class LlamaIndexElasticSearchStore(BaseVectorStore):
    def __init__(self,
                 embedding_model: BaseModel,
                 index_name: str,
                 es_url: str,
                 use_hybrid: bool = True,
                 **kwargs):

        self.embedding_model: BaseModel = embedding_model
        self.es_store = _ElasticsearchStore(index_name=index_name,
                                            es_url=es_url,
                                            retrieval_strategy=AsyncDenseVectorStrategy(hybrid=use_hybrid),
                                            **kwargs)
        self.index = VectorStoreIndex.from_vector_store(vector_store=self.es_store,
                                                        embed_model=self.embedding_model.model)

    def retrieve(self,
                 query: str,
                 top_k: int,
                 filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(
            vector_store_kwargs={"es_filter": es_filter},
            similarity_top_k=top_k)
        text_nodes = retriever.retrieve(query)
        return [self._text_node_2_memory_node(n) for n in text_nodes]

    async def async_retrieve(self,
                             query: str,
                             top_k: int,
                             filter_dict: Dict[str, List[str]] | Dict[str, str] = None) -> List[MemoryNode]:
        if filter_dict is None:
            filter_dict = {}

        es_filter = _to_elasticsearch_filter(filter_dict)
        retriever = self.index.as_retriever(
            vector_store_kwargs={"es_filter": es_filter},
            similarity_top_k=top_k)
        text_nodes: List[NodeWithScore] = await retriever.aretrieve(query)
        return [self._text_node_2_memory_node(n) for n in text_nodes]

    def insert(self, node: MemoryNode):
        self.index.insert_nodes([self._memory_node_2_text_node(node)])

    def delete(self, node: MemoryNode):
        memory_id = node.memory_id
        return self.es_store.delete(memory_id)

    def update(self, node: MemoryNode):
        self.delete(node)
        self.insert(node)

    def close(self):
        self.es_store.close()

    @staticmethod
    def _memory_node_2_text_node(memory_node: MemoryNode) -> TextNode:
        return TextNode(id_=memory_node.memory_id,
                        text=memory_node.content,
                        metadata=memory_node.model_dump(exclude={"content"}))

    @staticmethod
    def _text_node_2_memory_node(text_node: NodeWithScore) -> MemoryNode:
        return MemoryNode(content=text_node.text, **text_node.metadata)
