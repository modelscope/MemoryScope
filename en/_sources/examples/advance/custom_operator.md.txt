# Custom Operator and Worker

1. Create a new worker named `example_query_worker.py` in the `contrib` directory:
    ```bash
    vim memoryscope/contrib/example_query_worker.py
    ```

2. Write the program for the new custom worker. Note that the class name must match the filename, which is `ExampleQueryWorker`:
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
                query = query.strip() + "\n You must add a `meow~` at the end of each of your answers."
            # Store the determined query and its timestamp in the context
            self.set_workflow_context(QUERY_WITH_TS, (query, timestamp))
    ```

3. Create a YAML startup file (copying `demo_config.yaml`):
    ```
    cp memoryscope/core/config/demo_config.yaml examples/advance/replacement.yaml
    vim examples/advance/replacement.yaml
    ```

4. At the bottom, insert the definition for the new worker and replace the previous default `set_query` worker, and update the operation's workflow:
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

5. Verify:
    ```
    python quick-start-demo.py --config examples/advance/replacement.yaml
    ```