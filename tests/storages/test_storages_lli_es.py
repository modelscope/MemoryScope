import unittest

from memoryscope.core.models.llama_index_embedding_model import LlamaIndexEmbeddingModel
from memoryscope.core.storage.llama_index_es_memory_store import LlamaIndexEsMemoryStore
from memoryscope.scheme.memory_node import MemoryNode


class TestLlamaIndexElasticSearchStore(unittest.TestCase):
    """Tests for LLIEmbedding"""

    def setUp(self):
        config = {
            "module_name": "dashscope_embedding",
            "model_name": "text-embedding-v2",
            "clazz": "models.llama_index_embedding_model",
        }
        emb = LlamaIndexEmbeddingModel(**config)

        config = {
            "index_name": "0708_2",
            "es_url": "http://localhost:9200",
            "embedding_model": emb,
            "use_hybrid": True

        }
        self.es_store = LlamaIndexEsMemoryStore(**config)
        self.data = [
            MemoryNode(
                content="The lives of two mob hitmen, a boxer, a gangster and his wife, "
                        "and a pair of diner bandits intertwine in four tales of violence and redemption.",
                memory_type="observation",
                user_id="0",
                status="valid",
                memory_id="aaa123",

            ),
            MemoryNode(
                content="When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, "
                        "Batman must accept one of the greatest psychological and physical tests of his "
                        "ability to fight injustice.",
                memory_type="observation",
                user_id="1",
                status="valid",
                memory_id="bbb456",
                meta_data={"1": "1"}
            ),
            MemoryNode(
                content="An insomniac office worker and a devil-may-care soapmaker form an underground fight "
                        "club that evolves into something much, much more.",
                memory_type="insights",
                user_id="2",
                status="valid",
                memory_id="ccc789",
                meta_data={"2": "2"}
            ),
            MemoryNode(
                content="A thief who steals corporate secrets through the use of dream-sharing technology "
                        "is given the inverse task of planting an idea into thed of a C.E.O.",
                memory_type="insights",
                user_id="3",
                status="valid",
                memory_id="ddd012",
                meta_data={"3": "3"}

            ),
            MemoryNode(
                content="A computer hacker learns from mysterious rebels about the true nature of his reality "
                        "and his role in the war against its controllers.",
                memory_type="profile",
                user_id="4",
                status="valid",
                memory_id="eee345",
                meta_data={"4": "4"}

            ),
            MemoryNode(
                content="Two detectives, a rookie and a veteran, hunt a serial killer who uses the seven "
                        "deadly sins as his motives.",
                memory_type="profile",
                user_id="5",
                status="valid",
                memory_id="fff678",
                meta_data={"5": "5"},

            ),
            MemoryNode(
                content="An organized crime dynasty's aging patriarch transfers control of his clandestine "
                        "empire to his reluctant son.",
                memory_type="insights",
                user_id="6",
                status="valid",
                memory_id="ggg901",
                meta_data={"5": "5"}

            ),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                user_id="6",
                status="valid",
                memory_id="ggg234",
                meta_data={"5": "5"}

            ),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                user_id="6",
                status="valid",
                memory_id="hhh234",
                meta_data={"5": "5"}

            ),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                user_id="6",
                status="valid",
                memory_id="iii234",
                meta_data={"5": "5"}

            ),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                user_id="6",
                status="valid",
                memory_id="jjj234",
                meta_data={"5": "5"}

            ),
            MemoryNode(
                content="ggggggggg",
                memory_type="profile",
                user_id="6",
                status="valid",
                memory_id="kkk234",
                meta_data={"5": "5"}

            ),
        ]

    def test_retrieve(self):
        # filter_dict = {
        #     "user_id": "6",
        # }
        filter_dict = {}

        for node in self.data:
            self.es_store.insert(node)

        self.es_store.insert(MemoryNode(
            content="xxxxxx",
            memory_type="profile",
            user_id="6",
            status="valid",
            memory_id="ggg567",
            meta_data={"5": "5"}
        ))
        res = self.es_store.retrieve_memories(query="hacker", filter_dict=filter_dict, top_k=15)
        print(len(res))
        print(res)

        self.es_store.update(MemoryNode(
            content="test update",
            memory_type="profile",
            user_id="6",
            status="invalid",
            memory_id="ggg567"
        ))
        res = self.es_store.retrieve_memories(query="hacker", filter_dict=filter_dict, top_k=15)
        print(len(res))
        print(res)

        self.es_store.delete(MemoryNode(
            content="test update",
            memory_type="profile",
            user_id="6",
            status="invalid",
            memory_id="ggg567"
        ))
        import asyncio
        res = asyncio.run(self.es_store.a_retrieve_memories(query="hacker", filter_dict=filter_dict, top_k=15))
        # res = self.es_store.async_retrieve(query="hacker", filter_dict=filter_dict, top_k=10)
        print(len(res))
        print(res)

    def tearDown(self):
        self.es_store.close()
