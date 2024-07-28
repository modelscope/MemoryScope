"""Elasticsearch vector store."""

from logging import getLogger
from typing import Any, Callable, Dict, List, Literal, Optional, Union, cast

import nest_asyncio
import numpy as np
from elasticsearch import AsyncElasticsearch, Elasticsearch
from elasticsearch.helpers.vectorstore import (
    AsyncBM25Strategy,
    AsyncSparseVectorStrategy,
    AsyncDenseVectorStrategy,
    AsyncRetrievalStrategy,
    DistanceMetric,
)
from elasticsearch.helpers.vectorstore import VectorStore
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode, MetadataMode, TextNode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryMode,
    VectorStoreQueryResult,
)
from llama_index.core.vector_stores.utils import (
    metadata_dict_to_node,
    node_to_metadata_dict,
)
from llama_index.vector_stores.elasticsearch.utils import (
    get_user_agent,
)

logger = getLogger(__name__)

DISTANCE_STRATEGIES = Literal[
    "COSINE",
    "DOT_PRODUCT",
    "EUCLIDEAN_DISTANCE",
]

SPECIAL_QUERY: str = "**--**"


def get_elasticsearch_client(
        url: Optional[str] = None,
        cloud_id: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_async: Optional[bool] = False,
) -> AsyncElasticsearch:
    if url and cloud_id:
        raise ValueError(
            "Both es_url and cloud_id are defined. Please provide only one."
        )

    connection_params: Dict[str, Any] = {}

    if url:
        connection_params["hosts"] = [url]
    elif cloud_id:
        connection_params["cloud_id"] = cloud_id
    else:
        raise ValueError("Please provide either elasticsearch_url or cloud_id.")

    if api_key:
        connection_params["api_key"] = api_key
    elif username and password:
        connection_params["basic_auth"] = (username, password)
    if use_async:
        es_client = AsyncElasticsearch(
            **connection_params, headers={"user-agent": get_user_agent()}
        )
    else:
        es_client = Elasticsearch(
            **connection_params, headers={"user-agent": get_user_agent()}
        )

    es_client.info()  # use sync client so don't have to 'await' to just get info

    return es_client


def _to_llama_similarities(scores: List[float]) -> List[float]:
    """
    Converts a list of similarity scores into a normalized form for LlamaIndex compatibility.
    The normalization involves an exponential transformation based on the maximum score in the list.

    Args:
        scores (List[float]): A list of raw similarity scores.

    Returns:
        List[float]: A list of normalized similarity scores suitable for LlamaIndex.
    """
    if scores is None or len(scores) == 0:
        return []

    scores_to_norm: np.ndarray = np.array(scores)
    # Normalize scores by subtracting the max score and applying the exponential function
    return np.exp(scores_to_norm - np.max(scores_to_norm)).tolist()


def _mode_must_match_retrieval_strategy(
        mode: VectorStoreQueryMode, retrieval_strategy: AsyncRetrievalStrategy
) -> None:
    """
    Different retrieval strategies require different ways of indexing that must be known at the
    time of adding data. The query mode is known at query time. This function checks if the
    retrieval strategy (and way of indexing) is compatible with the query mode and raises and
    exception in the case of a mismatch.
    """
    if mode == VectorStoreQueryMode.DEFAULT:
        # it's fine to not specify an explicit other mode
        return

    mode_retrieval_dict = {
        VectorStoreQueryMode.SPARSE: AsyncSparseVectorStrategy,
        VectorStoreQueryMode.TEXT_SEARCH: AsyncBM25Strategy,
        VectorStoreQueryMode.HYBRID: AsyncDenseVectorStrategy,
    }

    required_strategy = mode_retrieval_dict.get(mode)
    if not required_strategy:
        raise NotImplementedError(f"query mode {mode} currently not supported")

    if not isinstance(retrieval_strategy, required_strategy):
        raise ValueError(
            f"query mode {mode} incompatible with retrieval strategy {type(retrieval_strategy)}, "
            f"expected {required_strategy}"
        )

    if mode == VectorStoreQueryMode.HYBRID and not retrieval_strategy.hybrid:
        raise ValueError(f"to enable hybrid mode, it must be set in retrieval strategy")


class ESCombinedRetrieveStrategy(AsyncDenseVectorStrategy):

    def __init__(
            self,
            *,
            distance: DistanceMetric = DistanceMetric.COSINE,
            model_id: Optional[str] = None,
            retrieve_mode: str = "dense",
            rrf: Union[bool, Dict[str, Any]] = True,
            text_field: Optional[str] = "text_field",
            hybrid_alpha: Optional[float] = None,
    ):
        if retrieve_mode == "dense":
            self.alpha = 1.0
        elif retrieve_mode == "sparse":
            # self.alpha = 0.0
            raise NotImplementedError
        elif retrieve_mode == "hybrid":
            # self.alpha = hybrid_alpha
            raise NotImplementedError

        super().__init__(distance=distance, model_id=model_id, hybrid=True, rrf=rrf, text_field=text_field)

    def _hybrid(self, query: str, knn: Dict[str, Any], filter: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
        # Add a query to the knn query.
        # RRF is used to even the score from the knn query and text query
        # RRF has two optional parameters: {'rank_constant':int, 'window_size':int}
        # https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
        if query == SPECIAL_QUERY:
            query_body = {
                "query": {
                    "bool": {
                        "filter": filter,
                    }
                },
            }
        else:
            query_body = {
                "knn": knn,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    self.text_field: {
                                        "query": query,
                                        "boost": (1 - self.alpha) if self.alpha is not None else 1.0,
                                    }
                                },
                            }
                        ],
                        "filter": filter,
                    },
                },
            }

            if self.alpha is None and isinstance(self.rrf, Dict):
                query_body["rank"] = {"rrf": self.rrf}
            elif self.alpha is None and isinstance(self.rrf, bool) and self.rrf is True:
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
            "boost": self.alpha if self.alpha is not None else 1.0,
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
            result['bool'].update({"should": operands})  # Add 'should' clause for OR logic
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


class SyncElasticsearchStore(BasePydanticVectorStore):
    """
    Elasticsearch vector store.

    Args:
        index_name: Name of the Elasticsearch index.
        es_client: Optional. Pre-existing AsyncElasticsearch client.
        es_url: Optional. Elasticsearch URL.
        es_cloud_id: Optional. Elasticsearch cloud ID.
        es_api_key: Optional. Elasticsearch API key.
        es_user: Optional. Elasticsearch username.
        es_password: Optional. Elasticsearch password.
        text_field: Optional. Name of the Elasticsearch field that stores the text.
        vector_field: Optional. Name of the Elasticsearch field that stores the
                    embedding.
        batch_size: Optional. Batch size for bulk indexing. Defaults to 200.
        distance_strategy: Optional. Distance strategy to use for similarity search.
                        Defaults to "COSINE".
        retrieval_strategy: Retrieval strategy to use. AsyncBM25Strategy /
            AsyncSparseVectorStrategy / AsyncDenseVectorStrategy / AsyncRetrievalStrategy.
            Defaults to AsyncDenseVectorStrategy.

    Raises:
        ConnectionError: If AsyncElasticsearch client cannot connect to Elasticsearch.
        ValueError: If neither es_client nor es_url nor es_cloud_id is provided.

    Examples:
        `pip install llama-index-vector-stores-elasticsearch`

        ```python
        from llama_index.vector_stores import ElasticsearchStore

        # Additional setup for ElasticsearchStore class
        index_name = "my_index"
        es_url = "http://localhost:9200"
        es_cloud_id = "<cloud-id>"  # Found within the deployment page
        es_user = "elastic"
        es_password = "<password>"  # Provided when creating deployment or can be reset
        es_api_key = "<api-key>"  # Create an API key within Kibana (Security -> API Keys)

        # Connecting to ElasticsearchStore locally
        es_local = ElasticsearchStore(
            index_name=index_name,
            es_url=es_url)

        # Connecting to Elastic Cloud with username and password
        es_cloud_user_pass = ElasticsearchStore(
            index_name=index_name,
            es_cloud_id=es_cloud_id,
            es_user=es_user,
            es_password=es_password)

        # Connecting to Elastic Cloud with API Key
        es_cloud_api_key = ElasticsearchStore(
            index_name=index_name,
            es_cloud_id=es_cloud_id,
            es_api_key=es_api_key,
        )
        ```

    """

    class Config:
        # allow pydantic to tolarate its inability to validate AsyncRetrievalStrategy
        arbitrary_types_allowed = True

    stores_text: bool = True
    index_name: str
    es_client: Optional[Any]
    es_url: Optional[str]
    es_cloud_id: Optional[str]
    es_api_key: Optional[str]
    es_user: Optional[str]
    es_password: Optional[str]
    text_field: str = "content"
    vector_field: str = "embedding"
    batch_size: int = 200
    distance_strategy: Optional[DISTANCE_STRATEGIES] = "COSINE"
    retrieval_strategy: AsyncRetrievalStrategy

    _store = PrivateAttr()

    def __init__(
            self,
            index_name: str,
            es_client: Optional[Any] = None,
            es_url: Optional[str] = None,
            es_cloud_id: Optional[str] = None,
            es_api_key: Optional[str] = None,
            es_user: Optional[str] = None,
            es_password: Optional[str] = None,
            text_field: str = "content",
            vector_field: str = "embedding",
            batch_size: int = 200,
            distance_strategy: Optional[DISTANCE_STRATEGIES] = "COSINE",
            retrieval_strategy: Optional[AsyncRetrievalStrategy] = None,
    ) -> None:
        nest_asyncio.apply()

        if not es_client:
            es_client = get_elasticsearch_client(
                url=es_url,
                cloud_id=es_cloud_id,
                api_key=es_api_key,
                username=es_user,
                password=es_password,
            )

        if retrieval_strategy is None:
            retrieval_strategy = AsyncDenseVectorStrategy(
                distance=DistanceMetric[distance_strategy]
            )

        metadata_mappings = {
            "document_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "ref_doc_id": {"type": "keyword"},
        }

        self._store = VectorStore(
            user_agent=get_user_agent(),
            client=es_client,
            index=index_name,
            retrieval_strategy=retrieval_strategy,
            text_field=text_field,
            vector_field=vector_field,
            metadata_mappings=metadata_mappings,
        )

        super().__init__(
            index_name=index_name,
            es_client=es_client,
            es_url=es_url,
            es_cloud_id=es_cloud_id,
            es_api_key=es_api_key,
            es_user=es_user,
            es_password=es_password,
            text_field=text_field,
            vector_field=vector_field,
            batch_size=batch_size,
            distance_strategy=distance_strategy,
            retrieval_strategy=retrieval_strategy,
        )

    @property
    def client(self) -> Any:
        """
        Get the asynchronous Elasticsearch client.

        Returns:
            Any: The asynchronous Elasticsearch client instance configured for this store.
        """
        return self._store.client

    def close(self) -> None:
        return self._store.close()

    def add(
            self,
            nodes: List[BaseNode],
            *,
            create_index_if_not_exists: bool = True,
            **add_kwargs: Any,
    ) -> List[str]:
        """
        Adds a list of nodes, each containing embeddings, to an Elasticsearch index.
        Optionally creates the index if it does not already exist.

        Args:
            nodes (List[BaseNode]): A list of node objects, each encapsulating an embedding.
            create_index_if_not_exists (bool, optional): 
                A flag indicating whether to create the Elasticsearch index if it's not present. 
                Defaults to True.

        Returns:
            List[str]: A list of node IDs that have been successfully added to the index.

        Raises:
            ImportError: If the 'elasticsearch[async]' Python package is not installed.
            BulkIndexError: If there is a failure during the asynchronous bulk indexing with AsyncElasticsearch.
        
        Note:
            This method delegates the actual operation to the `sync_add` method.
        """
        return self.sync_add(nodes, create_index_if_not_exists=create_index_if_not_exists)

    def sync_add(
            self,
            nodes: List[BaseNode],
            *,
            create_index_if_not_exists: bool = True,
            **add_kwargs: Any,
    ) -> List[str]:
        """
        Asynchronously adds a list of nodes, each containing an embedding, to the Elasticsearch index.
        
        This method processes each node to extract its ID, embedding, text content, and metadata, 
        preparing them for batch insertion into the index. It ensures the index is created if not present 
        and respects the dimensionality of the embeddings for consistency.

        Args:
            nodes (List[BaseNode]): A list of node objects, each encapsulating an embedding.
            create_index_if_not_exists (bool, optional): A flag indicating whether to create the Elasticsearch 
                                                          index if it does not already exist. Defaults to True.
            **add_kwargs (Any): Additional keyword arguments passed to the underlying add_texts method 
                                for customization during the indexing process.

        Returns:
          List[str]: A list of node IDs that were successfully added to the index.

        Raises:
            ImportError: If the Elasticsearch Python client is not installed.
            BulkIndexError: If there's a failure during the asynchronous bulk indexing operation.
        """
        if len(nodes) == 0:
            return []

        # Extract necessary components from each node
        embeddings: List[List[float]] = []  # Embedding vectors
        texts: List[str] = []  # Textual contents of nodes
        metadatas: List[dict] = []  # Metadata associated with nodes
        ids: List[str] = []  # Unique identifiers for nodes

        for node in nodes:
            ids.append(node.node_id)  # Node identifier
            embeddings.append(node.get_embedding())  # Node's embedding vector
            texts.append(node.get_content(metadata_mode=MetadataMode.NONE))  # Node's raw text content
            metadatas.append(node_to_metadata_dict(node, remove_text=True))  # Convert node to metadata dictionary

        # Initialize the number of dimensions in the store if not set
        if not self._store.num_dimensions:
            self._store.num_dimensions = len(embeddings[0])  # Set based on the first node's embedding size

        # Add the prepared data to the Elasticsearch index asynchronously
        return self._store.add_texts(
            texts=texts,
            metadatas=metadatas,
            vectors=embeddings,
            ids=ids,
            create_index_if_not_exists=create_index_if_not_exists,
            bulk_kwargs=add_kwargs,
        )

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """
        Deletes a node from the Elasticsearch index using the provided reference document ID.
        
        Optionally, extra keyword arguments can be supplied to customize the deletion behavior,
        which are passed directly to Elasticsearch's `delete_by_query` operation.
        
        Args:
            ref_doc_id (str): The unique identifier of the node/document to be deleted.
            delete_kwargs (Any): Additional keyword arguments for Elasticsearch's 
                                 `delete_by_query`. These might include query filters, 
                                 timeouts, or other operational configurations.
            
        Raises:
            Exception: If the deletion operation via Elasticsearch's `delete_by_query` fails.
            
        Note:
            This method internally calls a synchronous delete method (`sync_delete`) 
            to execute the deletion operation against Elasticsearch.
        """
        return self.sync_delete(ref_doc_id, **delete_kwargs)

    def sync_delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """
        Synchronously deletes a node from the Elasticsearch index based on the reference document ID.

        Args:
            ref_doc_id (str): The unique identifier of the node/document to be deleted.
            delete_kwargs (Any): Optional keyword arguments to be passed 
                                 to the delete_by_query operation of AsyncElasticsearch, 
                                 allowing for additional customization of the deletion process.

        Raises:
            Exception: If the deletion operation via AsyncElasticsearch's delete_by_query fails.
        
        Note:
            The function directly uses '_id' field to match the document for deletion instead of 'metadata.ref_doc_id',
            ensuring targeted removal based on the document's unique identifier within Elasticsearch.
        """
        # The original commented line suggests an alternative query using 'metadata.ref_doc_id',
        # but the active code line performs the deletion based on '_id', which typically aligns with 'ref_doc_id'.
        return self._store.delete(query={"term": {"_id": ref_doc_id}}, **delete_kwargs)

    def query(
            self,
            query: VectorStoreQuery,
            custom_query: Optional[
                Callable[[Dict, Union[VectorStoreQuery, None]], Dict]
            ] = None,
            es_filter: Optional[List[Dict]] = None,
            **kwargs: Any,
    ) -> VectorStoreQueryResult:
        """
        Executes a query against the Elasticsearch index to retrieve the top k most similar nodes 
        based on the input query embedding. Supports customization of the query process and 
        application of Elasticsearch filters.

        Args:
            query (VectorStoreQuery): The query containing the embedding and other parameters.
            custom_query (Callable[[Dict, Union[VectorStoreQuery, None]], Dict], optional): 
                An optional custom function to modify the Elasticsearch query body, allowing for 
                additional query parameters or logic. Defaults to None.
            es_filter (Optional[List[Dict]], optional): An optional Elasticsearch filter list to 
                apply to the query. If a filter is directly included in the `query`, this argument 
                will not be used. Defaults to None.
            **kwargs (Any): Additional keyword arguments that might be used in the query process.

        Returns:
            VectorStoreQueryResult: The result of the query operation, including the most similar nodes.

        Raises:
            Exception: If an error occurs during the Elasticsearch query execution.

        """
        return self.sync_query(query, custom_query, es_filter, **kwargs)

    def sync_query(
            self,
            query: VectorStoreQuery,
            custom_query: Optional[
                Callable[[Dict, Union[VectorStoreQuery, None]], Dict]
            ] = None,
            es_filter: Optional[List[Dict]] = None,
            fields: List[str] = [],
    ) -> VectorStoreQueryResult:
        """
        Asynchronously queries the Elasticsearch index for the top k most similar nodes 
        based on the provided query embedding. Supports custom query modifications 
        and application of Elasticsearch filters.

        Args:
            query (VectorStoreQuery): The query containing the embedding and other details.
            custom_query (Callable[[Dict, Union[VectorStoreQuery, None]], Dict], optional): 
                A custom function to modify the Elasticsearch query body. Defaults to None.
            es_filter (List[Dict], optional): Additional filters to apply during the query. 
                If filters are present in the query, these filters will not be used. Defaults to None.
            fields (List[str], optional): .

        Returns:
            VectorStoreQueryResult: The result of the query, including nodes, their IDs, 
                                    and similarity scores.

        Raises:
            Exception: If the Elasticsearch query encounters an error.

        Note:
            The mode of the query must align with the retrieval strategy set for this store.
            In case of legacy metadata, a warning is logged and nodes are constructed accordingly.
        """
        _mode_must_match_retrieval_strategy(query.mode, self.retrieval_strategy)

        if query.filters is not None and len(query.filters.legacy_filters()) > 0:
            filter = [_to_elasticsearch_filter(query.filters)]
        else:
            filter = es_filter or []
        num_candidates = query.similarity_top_k * 10 if query.similarity_top_k <= 1000 else query.similarity_top_k

        hits = self._store.search(
            query=query.query_str,
            query_vector=query.query_embedding,
            k=query.similarity_top_k,
            num_candidates=num_candidates,  # query.similarity_top_k * 10,
            filter=filter,
            custom_query=custom_query,
            fields=fields,
        )
        top_k_nodes = []
        top_k_ids = []
        top_k_scores = []
        for hit in hits:
            source = hit["_source"]
            metadata = source.get("metadata", None)
            embedding = source.get("embedding", None)
            text = source.get(self.text_field, None)
            node_id = hit["_id"]

            try:
                # Attempt to parse metadata using the standard method
                node = metadata_dict_to_node(metadata)
                node.text = text
                node.embedding = embedding
            except Exception:
                # Legacy support for old metadata format
                logger.warning(
                    f"Could not parse metadata from hit {hit['_source']['metadata']}"
                )
                node_info = source.get("node_info")
                relationships = source.get("relationships", {})
                start_char_idx = None
                end_char_idx = None
                if isinstance(node_info, dict):
                    start_char_idx = node_info.get("start", None)
                    end_char_idx = node_info.get("end", None)

                node = TextNode(
                    text=text,
                    metadata=metadata,
                    id_=node_id,
                    embedding=embedding,
                    start_char_idx=start_char_idx,
                    end_char_idx=end_char_idx,
                    relationships=relationships,
                )
            top_k_nodes.append(node)
            top_k_ids.append(node_id)
            top_k_scores.append(hit.get("_rank", hit["_score"]))

        if (
                isinstance(self.retrieval_strategy, AsyncDenseVectorStrategy)
                and self.retrieval_strategy.hybrid
        ):
            total_rank = sum(top_k_scores)
            top_k_scores = [rank for rank in top_k_scores]
            # top_k_scores = [(total_rank - rank) / total_rank for rank in top_k_scores]
            # top_k_scores = [total_rank - rank / total_rank for rank in top_k_scores]

        return VectorStoreQueryResult(
            nodes=top_k_nodes,
            ids=top_k_ids,
            # similarities=_to_llama_similarities(top_k_scores),
            similarities=top_k_scores
        )
