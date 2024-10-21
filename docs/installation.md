# Installing MemoryScope

## I. Install with docker [Recommended] [x86_64]

1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config.yaml
    ```

2. Build Docker image
    ```bash
    sudo docker build --network=host -t memoryscope .
    ```
    If you are using arm-based computers, modify command above into: `sudo docker build -f DockerfileArm --network=host -t memoryscope .`

3. Launch Docker container
    ```bash
    sudo docker run -it --rm --net=host memoryscope
    ```

> [!Important]
> To inspect memory shift during the conversation, modify command in step 3 to `sudo docker run -it --name=memoryscope_container --rm --net=host memoryscope`;<br/>
> Then start a new terminal window and execute `sudo docker exec -it memoryscope_container python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml`;<br/>
> In the second window, input `/list_memory refresh_time=5` to inspect memory

## II. Install with docker compose [Recommended] [x86_64]

1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config.yaml
    ```

2. Edit `docker-compose.yml` to change environment variable.
    ```
    OPENAI_API_KEY: "sk-0000000000"
    ```

3. Run `docker-compose run memory_scope_main` to build and launch the memory-scope cli interface. (For ARM architecture, you should edit `docker-compose.yml`, changing `image: ghcr.io/modelscope/memoryscope:main` to `image: ghcr.io/modelscope/memoryscope_arm:main`)


## III. Install from PyPI

1. Install from PyPI
   ```bash
   pip install memoryscope
   ```

2. Run Elasticsearch service, refer to [elasticsearch documents](https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html).
The docker method is recommended:
    ```
    sudo docker run -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "xpack.license.self_generated.type=trial" \
    docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

3. Test Chinese / Dashscope Configuration
    ```bash
    export DASHSCOPE_API_KEY="sk-0000000000"
    memoryscope --language="cn" \
            --memory_chat_class="cli_memory_chat" \
            --human_name="用户" \
            --assistant_name="AI" \
            --generation_backend="dashscope_generation" \
            --generation_model="qwen-max" \
            --embedding_backend="dashscope_embedding" \
            --embedding_model="text-embedding-v2" \
            --enable_ranker=True \
            --rank_backend="dashscope_rank" \
            --rank_model="gte-rerank"
    ```

4. Test English / OpenAI Configuration
    ```bash
    export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    memoryscope --language="en" \
            --memory_chat_class="cli_memory_chat" \
            --human_name="User" \
            --assistant_name="AI" \
            --generation_backend="openai_generation" \
            --generation_model="gpt-4o" \
            --embedding_backend="openai_embedding" \
            --embedding_model="text-embedding-3-small" \
            --enable_ranker=False
    ```

## IV. Install from source

1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config.yaml
    ```

2. Install
    ```bash
    pip install -e .
    ```

3. Run Elasticsearch service, refer to [elasticsearch documents](https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started.html).
The docker method is recommended:
    ```
    sudo docker run -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "xpack.license.self_generated.type=trial" \
    docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

4. Launch memoryscope, also refer to [cli documents](../examples/cli/CLI_README.md)
    ```bash
    export OPENAI_API_KEY="sk-0000000000"
    python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml
    ```
