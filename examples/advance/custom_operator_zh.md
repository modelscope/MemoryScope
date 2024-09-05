# 自定义 Operator 和 Worker

1. 在 `contrib` 路径下创建新worker，命名为 `example_query_worker.py`:
    ```bash
    vim memoryscope/contrib/example_query_worker.py
    ```

2. 写入新的自定义worker的程序，注意`class`的命名需要与文件名保持一致，为`ExampleQueryWorker`：
    ```python
    import datetime
    from memoryscope.constants.common_constants import QUERY_WITH_TS
    from memoryscope.core.worker.memory_base_worker import MemoryBaseWorker

    class ExampleQueryWorker(MemoryBaseWorker):

        def _run(self):

            timestamp = int(datetime.datetime.now().timestamp())  # Current timestamp as default

            assert "query" in self.chat_kwargs
            query = self.chat_kwargs["query"]
            if not query:
                query = ""
            else:
                query = query.strip() + "\n You must add a `meow~` at the end of each of your answer."

            # Store the determined query and its timestamp in the context
            self.set_workflow_context(QUERY_WITH_TS, (query, timestamp))
    ```

3. 创建yaml启动文件（复制demo_config_zh.yaml）
    ```
    cp memoryscope/core/config/demo_config_zh.yaml examples/advance/replacement.yaml
    vim examples/advance/replacement.yaml
    ```

4. 在最下面插入新worker的定义，并且取代之前的默认`set_query`worker，并替换operation的workflow
    ```
    rewrite_query:
      class: contrib.example_query_worker
      generation_model: generation_model
    ```
    ```
      retrieve_memory:
        class: core.operation.frontend_operation
        workflow: rewrite_query,[extract_time|retrieve_obs_ins,semantic_rank],fuse_rerank
        description: "retrieve long-term memory"     
    ```

5. 验证：
    ```
    python quick-start-demo.py --config examples/advance/replacement.yaml
    ```
