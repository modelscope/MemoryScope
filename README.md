English | [**中文**](./README_ZH.md)

# MemoryScope


# Installation

## (1) Docker-Compose (Recommanded)
1. Clone the project and edit the config.

    ```
    git clone https://...
    nano config/demo_config_cn.yaml
    ```

2. Edit `docker-compose.yml` to change environment variable.

    ```
    DASHSCOPE_API_KEY: "sk-0000000000"
    ```

3. Run `docker-compose up` to build and launch the memory-scope cli interface.


## (2) Docker

1. Clone the project and edit the config.

    ```
    git clone https://...
    nano config/demo_config_cn.yaml
    ```

2. Build the `Dockerfile` with command: 
    ```
    sudo docker build --network=host -t memoryscope .
    ```

3. Run `ElasticSearch` Container with command: 
    ```
    docker run -p 9200:9200 \
        -e "discovery.type=single-node" \
        -e "xpack.security.enabled=false" \
        -e "xpack.license.self_generated.type=trial" \
        docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

4. Launch the built image with command: 
    ```
    sudo docker run -it --rm --net=host memoryscope
    ```