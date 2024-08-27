# Installing MemoryScope

## I. Install with docker [Recommended]
1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config_zh.yaml
    ```

2. Build Docker image
    ```bash
    sudo docker build --network=host -t memoryscope .
    ```


3. Launch Docker container
    ```bash
    sudo docker run -it --rm --net=host memoryscope
    ```


## II. Install with docker compose [Recommended]


1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config_zh.yaml
    ```


2. Edit `docker-compose.yml` to change environment variable.
    ```
    DASHSCOPE_API_KEY: "sk-0000000000"
    ```

3. Run `docker-compose up` to build and launch the memory-scope cli interface.


## III. Install from PyPI [Linux]

```bash
pip install memoryscope
export DASHSCOPE_API_KEY="sk-0000000000"
memoryscope --config_path=memoryscope/core/config/demo_config_zh.yaml
```


## IV. Install from source [Linux only]

1. Clone the repository and edit settings
    ```bash
    # clone project
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # edit configuration, e.g. add api keys
    vim memoryscope/core/config/demo_config_zh.yaml
    ```

2. Install 
    ```bash
    poetry install
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

4. Launch memoryscope, also refer to [cli documents](../examples/cli/README.md)
    ```bash
    pip install -r requirements.txt
    export DASHSCOPE_API_KEY="sk-0000000000"
    python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml
    ```
