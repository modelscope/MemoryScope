# Working with AgentScope

1. First, make sure that you have installed AutoGen as well as memoryscope.
    ```
    pip install agentscope memoryscope
    ```


2. Then, ensure that es is up and running. [elasticsearch documents](https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html).
The docker method is recommended:
    ```
    sudo docker run -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "xpack.license.self_generated.type=trial" \
    docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

3. Finally, we can start the autogen demo.
    ```
    python examples/api/agentscope_example.py
    ```