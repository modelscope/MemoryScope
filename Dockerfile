# sudo docker build --network=host -t memoryscope .
# sudo docker run -it --net=host memoryscope
FROM python:3.11

# 非必要步骤，更换pip源 （以下三行，可以删除）
RUN echo '[global]' > /etc/pip.conf && \
    echo 'index-url = https://mirrors.aliyun.com/pypi/simple/' >> /etc/pip.conf && \
    echo 'trusted-host = mirrors.aliyun.com' >> /etc/pip.conf

# 安装大部分依赖，利用Docker缓存加速以后的构建 （以下两行，可以删除）
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# 进入工作路径（必要）
WORKDIR /memory_scope_project
COPY . .
RUN pip install -r requirements.txt

# 启动（必要）
CMD ["python3", "memory_scope/cli.py", "config/docker_config.yaml"]
