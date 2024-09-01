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

3. 启动 Docker 容器
    ```bash
    sudo docker run -it --rm --net=host memoryscope
    ```


## 二、使用 Docker Compose 安装 [推荐]

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

3. 运行 `docker-compose up` 命令来构建并启动 MemoryScope CLI 界面。


## 三、通过 PYPI 安装 [仅限 Linux]

1. 从 PyPI 安装：
    ```bash
    pip install memoryscope
    ```

2. 测试中文 / Dashscope 对话配置：
    ```bash
    export DASHSCOPE_API_KEY="sk-0000000000"
    memoryscope --config_path=memoryscope/core/config/demo_config_zh.yaml
    ```

3. 测试英文 / OpenAI 对话配置：
    ```bash
    export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    memoryscope --config_path=memoryscope/core/config/demo_config.yaml
    ```


## 四、从源码安装 [仅限 Linux]

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

4. 启动 MemoryScope，同时参考 [CLI 文档](../examples/cli/README.md)
    ```bash
    pip install -r requirements.txt
    export DASHSCOPE_API_KEY="sk-0000000000"
    python quick-start-demo.py --config_path=memoryscope/core/config/demo_config_zh.yaml
    ```

