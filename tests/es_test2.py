import sys

sys.path.append("./")

from common.elastic_search_client import ElasticSearchClient
from common.dash_embedding_client import DashEmbeddingClient
from enumeration.memory_type_enum import MemoryTypeEnum

from config.bailian_memory_config import BailianMemoryConfig

api_key: str = "sk-fc77951df1d94418bb5a6cd84da76b17"

if __name__ == "__main__":
    es_index_name: str = "memory_index"
    es_user_name: str = "elastic"
    es_password: str = "Beilianmemory_"
    es_search_top_k = 50
    config = BailianMemoryConfig()
    emb_client = DashEmbeddingClient(
        request_id="123",
        dash_scope_uid="123",
        authorization=api_key,
        workspace="")

    client = ElasticSearchClient(es_user_name=es_user_name,
                                 es_password=es_password,
                                 es_index_name=es_index_name,
                                 embedding_client=emb_client)

    # result = client.exact_search(100, exact_filters={"status": [MemoryNodeStatus.ACTIVE.value, MemoryNodeStatus.EXPIRED.value]})
    # for k in result[:1]:
    #     print(k)
    #     # print(type(k))
    #     # print(k["_index"])
    #     # print(k["_id"])
    #     # print(k["_score"])
    #     # print(k["_source"])

    # result = client.similar_search("可以帮忙准备一些菜吗？", size=100, exact_filters={
    #     # "code": "jinli_0530_v2_TONGYI_MAIN_CHAT_profile_音乐偏好",
    #     # "memoryId": "jinli_0530_v2",
    #     # "status": MemoryNodeStatus.ACTIVE.value,
    #     # # "metaData.year": "2024",
    #     "scene": "TONGYI_MAIN_CHAT".lower(),
    #     # "memoryType": "profile",
    #     # "content_modified": True,
    # })

    # query = "我今天出差来深圳君悦酒店了，给张三发个邮件说一下事情"
    # result = client.similar_search(text=query,
    #                                size=100,
    #                                exact_filters={
    #                                    "memoryId": "jinli_0607_v11",
    #                                    "status": "active",
    #                                    "scene": "TONGYI_MAIN_CHAT".lower(),
    #                                    "memoryType": [MemoryTypeEnum.OBSERVATION.value,
    #                                                   MemoryTypeEnum.INSIGHT.value,
    #                                                   MemoryTypeEnum.OBS_CUSTOMIZED.value],
    #
    #                                },
    #                                wildcard_filters={
    #                                    f"metaData.key_word": ["天气", "工作"],
    #                                })

    result = client.exact_search_v2(size=100,
                                    term_filters={
                                        "memoryId": "jinli_0607_v11",
                                        "status": "active",
                                        "scene": "TONGYI_MAIN_CHAT".lower(),
                                        "memoryType": [MemoryTypeEnum.OBSERVATION.value,
                                                       MemoryTypeEnum.INSIGHT.value,
                                                       MemoryTypeEnum.OBS_CUSTOMIZED.value],

                                    },
                                    match_filters={
                                        f"metaData.key_word": ["天气", "工作"],
                                    }
                                    )

    for k in result:
        # print(json.dumps(k, ensure_ascii=False))
        key_word = k["_source"]["metaData"].get("key_word", "")
        content = k["_source"]["content"]
        print(content, "||||", key_word)
        # print(type(k))
        # print(k["_index"])
        # print(k["_id"])
        # print(k["_score"])
        # print(k["_source"])
