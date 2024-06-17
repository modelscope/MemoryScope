from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from common.dash_embedding_client import DashEmbeddingClient
from common.logger import Logger
from constants.common_constants import ES_ENV_URL_DICT
from enumeration.env_type import EnvType


class ElasticSearchClient(object):
    def __init__(self,
                 es_user_name: str,
                 es_password: str,
                 es_index_name: str,
                 embedding_client: DashEmbeddingClient | None = None,
                 env_type: EnvType | str = EnvType.DAILY,
                 content_key: str = "content",
                 vector_key: str = "vector",
                 **kwargs):

        self.es_index_name: str = es_index_name
        self.embedding_client: DashEmbeddingClient = embedding_client
        self.content_key: str = content_key
        self.vector_key: str = vector_key

        self.es_client = Elasticsearch(
            hosts=[ES_ENV_URL_DICT.get(EnvType(env_type))],
            basic_auth=(es_user_name, es_password),
            **kwargs)

        self.logger = Logger.get_logger()
        self.logger.debug(f"connect es_client info={self.es_client.info()}")

    def log_index_info(self):
        index_info = self.es_client.indices.get(index=self.es_index_name)
        self.logger.info(f"index={self.es_index_name} exists. index_info={index_info}")

    def insert(self, _id: str, body: dict):
        assert body and self.content_key in body, f"body={body} is illegal!"

        # text_type: document
        content = body[self.content_key]
        vector = self.embedding_client.call(text=content, text_type="document")
        if not vector:
            self.logger.warning(f"embedding_client call failed, stop es insert!")
            return

        body[self.vector_key] = vector
        response = self.es_client.index(id=_id, index=self.es_index_name, body=body)
        self.logger.info(f"insert response={response}")

    def insert_batch(self, doc_list: list):
        """
        doc_list = [
            {
                "_id": 2,
                "_source": {
                    "author": "john",
                    "text": "Elasticsearch: cool.",
                    "timestamp": "2023-03-23T10:00:00"
                }
            },
            {
                "_id": 3,
                "_source": {
                    "author": "jane",
                    "text": "Elasticsearch: very cool.",
                    "timestamp": "2023-03-23T11:00:00"
                }
            }
        ]
        """
        text_list = []
        for doc in doc_list:
            assert "_id" in doc and "_source" in doc
            content = doc["_source"][self.content_key]
            text_list.append(content)

        vector_dict = self.embedding_client.call(text=text_list, text_type="document")
        if not vector_dict:
            self.logger.warning(f"embedding_client call failed, stop es insert!")
            return

        # add _index
        for i, doc in enumerate(doc_list):
            doc["_index"] = self.es_index_name
            vector = vector_dict[i]
            doc["_source"][self.vector_key] = vector

        # 执行批量插入
        responses = bulk(self.es_client, doc_list)

        # 输出批量插入的响应
        for response in responses[1]:
            self.logger.info(f"insert_batch response={response}")

    def print_hits(self, hits: list):
        for hit in hits:
            print_kwargs = {
                "_id": hit['_id'],
                "_score": hit['_score'],
            }
            for k, v in hit['_source'].items():
                # 不打印vector
                if k == self.vector_key:
                    v = len(v)
                print_kwargs[k] = v
            self.logger.info(" ".join([f"{k}={v}" for k, v in print_kwargs.items()]))

    def exact_search(self,
                     size: int,
                     exact_filters: dict = None,
                     wildcard_filters: dict = None,
                     print_hits: bool = False,
                     exclude_vector: bool = True):
        """
        {
            "match": {
                "category": "electronics"  # 一级字段过滤
            }
        },
        {
            "match": {
                "product.name": "laptop"  # 二级字段过滤
            }
        }
        {
            "terms": {
                "product.keyA": ["a", "b", "c"]  # 二级字段keyA的精确值必须为a、b、c中的一
            }
        }
        """
        must_list = []
        for key, value in exact_filters.items():
            if not key:
                continue
            if isinstance(value, str):
                must_list.append({"match": {key: value}})
            elif isinstance(value, list):
                must_list.append({"terms": {key: value}})

        query = {
            "size": size,
            "query": {
                "bool": {
                    "must": must_list
                }
            },
            # 添加_source配置以排除vector字段
            "_source": {
                "excludes": [self.vector_key] if exclude_vector else []
            }
        }

        if wildcard_filters:
            should_list = []
            for key, value in wildcard_filters.items():
                if not key:
                    continue
                if isinstance(value, str):
                    should_list.append({"wildcard": {key: f"*{value}*"}})
                elif isinstance(value, list):
                    for v in value:
                        should_list.append({"wildcard": {key: f"*{v}*"}})

            query["query"]["bool"].update({
                "should": should_list,
                "minimum_should_match": 1,
            })
        self.logger.info(f"query={query}")

        response = self.es_client.search(index=self.es_index_name, body=query)
        hits = response['hits']['hits']

        # 耗时log
        self.logger.info(f"exact_search cost={response['took']}ms "
                         f"size={len(hits)} "
                         f"timed_out={response['timed_out']} "
                         f"shards={response['_shards']} "
                         f"exact_filters={exact_filters}", stacklevel=2)

        # 每一条结果log一次
        if print_hits:
            self.print_hits(hits)

        return hits

    def exact_search_v2(self,
                        size: int,
                        term_filters: dict = None,
                        match_filters: dict = None,
                        print_hits: bool = False,
                        exclude_vector: bool = True):

        """
"bool": {
    "must": [
        {"term": {"field1": "固定值"}},  # 一级目录关键字过滤（等于某个值）
        {"terms": {"field2": ["a", "b", "c"]}}  # 二级目录关键字过滤（等于三个中的任意一个）
    ],
    "should": [  # 至少匹配其中之一
        {"match": {"key": "ccc"}},  # key包含"ccc"
        {"match": {"key": "bbb"}}  # 或者key包含"bbb"
    ],
    "minimum_should_match": 1  # 至少有一个`should`条件匹配
}
        """

        query = {
            "size": size,
            "query": {
                "bool": {

                }
            },
            # 添加_source配置以排除vector字段
            "_source": {
                "excludes": [self.vector_key] if exclude_vector else []
            }
        }

        if term_filters:
            must_list = []
            for k, v in term_filters.items():
                if isinstance(v, list):
                    must_list.append({"terms": {k: v}})
                elif isinstance(v, str):
                    must_list.append({"term": {k: v}})
                else:
                    raise NotImplemented
            query["query"]["bool"]["must"] = must_list

        if match_filters:
            match_list = []
            for k, v in match_filters.items():
                if isinstance(v, list):
                    for v_sub in v:
                        match_list.append({"match": {k: v_sub}})
                elif isinstance(v, str):
                    match_list.append({"match": {k: v}})
                else:
                    raise NotImplemented
            query["query"]["bool"]["should"] = match_list
            query["query"]["bool"]["minimum_should_match"] = 1

        self.logger.info(query)
        response = self.es_client.search(index=self.es_index_name, body=query)
        hits = response['hits']['hits']

        # 耗时log
        self.logger.info(f"exact_search cost={response['took']}ms "
                         f"size={len(hits)} "
                         f"timed_out={response['timed_out']} "
                         f"shards={response['_shards']}", stacklevel=2)

        # 每一条结果log一次
        if print_hits:
            self.print_hits(hits)

        return hits

    def similar_search(self,
                       text: str,
                       size: int,
                       exact_filters: dict = None,
                       print_hits: bool = False,
                       exclude_vector: bool = True):

        if exact_filters is None:
            exact_filters = {}

        # 过滤or
        or_filters = {}
        for k in list(exact_filters.keys()):
            v = exact_filters[k]
            if isinstance(v, list):
                exact_filters.pop(k)
                or_filters[k] = v

        vector = self.embedding_client.call(text=text)
        if not vector:
            self.logger.warning(f"embedding_client call failed, stop select from es!")
            return

        query = {
            # 返回最相似的top_k个文档
            "size": size,
            "query": {
                "bool": {
                    "must": {
                        "script_score": {
                            # 对所有文档执行
                            "query": {
                                "match_all": {}
                            },
                            "script": {
                                # 使用余弦相似度+1,es不能返回负数
                                "source": f"cosineSimilarity(params.query_vector, '{self.vector_key}') + 1.0",
                                "params": {"query_vector": vector}
                            }
                        }
                    },
                    "filter": [
                        {"term": {k: v}} for k, v in exact_filters.items()
                    ],
                }
            },
            # 添加_source配置以排除vector字段
            "_source": {
                "excludes": [self.vector_key] if exclude_vector else []
            }
        }

        if or_filters:
            k_v_pair = []
            for k, v_list in or_filters.items():
                for v in v_list:
                    k_v_pair.append((k, v))
            query["query"]["bool"]["should"] = [{"term": {k: v}} for k, v in k_v_pair]
            query["query"]["bool"]["minimum_should_match"] = 1

        response = self.es_client.search(index=self.es_index_name, body=query)
        hits = response['hits']['hits']

        # 耗时log
        self.logger.info(f"similar_search cost={response['took']}ms "
                         f"size={len(hits)} "
                         f"timed_out={response['timed_out']} "
                         f"shards={response['_shards']} "
                         f"text={text} "
                         f"exact_filters={exact_filters}", stacklevel=2)

        # 还原打分
        for hit in hits:
            hit['_score'] -= 1

        # 每一条结果log一次
        if print_hits:
            self.print_hits(hits)

        return hits
