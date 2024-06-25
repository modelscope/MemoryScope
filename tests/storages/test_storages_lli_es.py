import unittest

from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterCondition, FilterOperator
from llama_index.core.schema import TextNode
from memory_scope.scheme.memory_node import MemoryNode
from memory_scope.storage.llama_index_elastic_search_store import LlamaIndexElasticSearchStore
from memory_scope.models.llama_index_embedding_model import LlamaIndexEmbeddingModel

class TestLlamaIndexElasticSearchStore(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        config = {
            "method_type": "DashScopeEmbedding",
            "model_name": "text-embedding-v2",
            "clazz": "models.llama_index_embedding_model"
        }
        emb = LlamaIndexEmbeddingModel(**config).model

        config = {
            "index_name" : "0625_3",
            "es_url" : "http://localhost:9200",
            "embedding_model" : emb, 
             
        }
        self.es_store = LlamaIndexElasticSearchStore(**config)
        self.data = [
            MemoryNode(
                content="The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption.",
                memory_type="observation",
                id="0"

            ),
            MemoryNode(
                content="When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
                memory_type="observation",
                id="1"

            ),
            MemoryNode(
                content="An insomniac office worker and a devil-may-care soapmaker form an underground fight club that evolves into something much, much more.",
                memory_type="insights",
                id="2"

            ),
            MemoryNode(
                content="A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into thed of a C.E.O.",
                memory_type="insights",
                id="3"

            ),
            MemoryNode(
                content="A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
                memory_type="profile",
                id="4"
            ),
            MemoryNode(
                content="Two detectives, a rookie and a veteran, hunt a serial killer who uses the seven deadly sins as his motives.",
                memory_type="profile",
                id="5"
            ),
            MemoryNode(
                content="An organized crime dynasty's aging patriarch transfers control of his clandestine empire to his reluctant son.",
                memory_type="insights",
                id="6"),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                id="6"),
            
        ]
    # @unittest.skip("tmp")
    def test_insert(self, ):
        for node in self.data:
            self.es_store.insert(node)

    
    # @unittest.skip("tmp")
    def test_retrieve(self, ):
        
        filter = {
            "id": ["1", "2", "3"],
            "memory_type": "insights",
        }

        res = self.es_store.retrieve(query="hacker", filter_dict=filter, top_k=10)
        print(len(res))
        print(res)

        