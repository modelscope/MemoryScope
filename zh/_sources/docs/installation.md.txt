# MemoryScope 安装指南

## 一、使用 Docker 安装 [推荐]

1. 克隆仓库并编辑配置
    ```bash
    # 克隆项目
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # 编辑配置，例如添加 API 密钥
    vim memoryscope/core/config/demo_config_zh.yaml
    ```

2. 构建 Docker 镜像
    ```bash
    sudo docker build --network=host -t memoryscope .
    ```
   备注：如果是arm架构的电脑，则必须使用另一个命令：`sudo docker build -f DockerfileArm --network=host -t memoryscope .`

3. 启动 Docker 容器
    ```bash
    sudo docker run -it --rm --net=host memoryscope
    ```


> [!Important]
> 如果需要观察Memory的变化请调整第3步的运行命令。首先执行 `sudo docker run -it --name=memoryscope_container --rm --net=host memoryscope`启动memoryscope；<br/>
> 然后新建命令行窗口，运行`sudo docker exec -it memoryscope_container python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml`；<br/>
> 在第二个窗口，继续输入`/list_memory refresh_time=5`来检查实时的memory

## 二、使用 Docker Compose 安装 [推荐] [x86_64]

1. 克隆仓库并编辑配置
    ```bash
    # 克隆项目
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # 编辑配置，例如添加 API 密钥
    vim memoryscope/core/config/demo_config_zh.yaml
    ```

2. 编辑 `docker-compose.yml` 文件以更改环境变量。
    ```
    DASHSCOPE_API_KEY: "sk-0000000000"
    ```

3. 运行 `docker-compose run memory_scope_main` 命令来构建并启动 MemoryScope CLI 界面。(备注：如果是arm架构，还需要手动将docker-compose.yml中的`ghcr.io/modelscope/memoryscope:main`修改成`ghcr.io/modelscope/memoryscope_arm:main`)


## 三、通过 PYPI 安装

1. 从 PyPI 安装：
    ```bash
    pip install memoryscope
    ```

2. 运行 Elasticsearch 服务，参照 [Elasticsearch 文档](https://www.elastic.co/guide/cn/elasticsearch/reference/current/getting-started.html)。
推荐使用 Docker 方法：
    ```
    sudo docker run -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "xpack.license.self_generated.type=trial" \
    docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

3. 测试中文 / Dashscope 对话配置：
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

4. 测试英文 / OpenAI 对话配置：
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


## 四、从源码安装

1. 克隆仓库并编辑设置
    ```bash
    # 克隆项目
    git clone https://github.com/modelscope/memoryscope
    cd memoryscope
    # 编辑配置，例如添加 API 密钥
    vim memoryscope/core/config/demo_config_zh.yaml
    ```

2. 安装依赖
    ```bash
    pip install -e .
    ```

3. 运行 Elasticsearch 服务，参照 [Elasticsearch 文档](https://www.elastic.co/guide/cn/elasticsearch/reference/current/getting-started.html)。
推荐使用 Docker 方法：
    ```
    sudo docker run -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -e "xpack.license.self_generated.type=trial" \
    docker.elastic.co/elasticsearch/elasticsearch:8.13.2
    ```

4. 启动 MemoryScope，同时参考 [CLI 文档](../examples/cli/CLI_README_ZH.md)
    ```bash
    export DASHSCOPE_API_KEY="sk-0000000000"
    python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml
    ```

