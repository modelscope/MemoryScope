# __  __                                 ____                       
# |  \/  | ___ _ __ ___   ___  _ __ _   _/ ___|  ___ ___  _ __   ___ 
# | |\/| |/ _ \ '_ ` _ \ / _ \| '__| | | \___ \ / __/ _ \| '_ \ / _ \
# | |  | |  __/ | | | | | (_) | |  | |_| |___) | (_| (_) | |_) |  __/
# |_|  |_|\___|_| |_| |_|\___/|_|   \__, |____/ \___\___/| .__/ \___|
#                                   |___/                |_|         

# Instruction

# To construct docker image: 
#    sudo docker build --network=host -t memoryscope .

# To run docker image: 
#    sudo docker run -it --rm --net=host memoryscope


FROM python:3.11

# (Not necessary) Change pip source
RUN echo '[global]' > /etc/pip.conf && \
    echo 'index-url = https://mirrors.aliyun.com/pypi/simple/' >> /etc/pip.conf && \
    echo 'trusted-host = mirrors.aliyun.com' >> /etc/pip.conf

# Install Elastic Search
RUN useradd -m elastic_search_user
USER elastic_search_user
WORKDIR /home/elastic_search_user/elastic_search
# COPY elasticsearch-8.15.0-linux-x86_64.tar.gz ./elasticsearch-8.15.0-linux-x86_64.tar.gz
RUN wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.15.0-linux-x86_64.tar.gz
RUN tar -xzf elasticsearch-8.15.0-linux-x86_64.tar.gz
WORKDIR /home/elastic_search_user/elastic_search/elasticsearch-8.15.0
ENV DISCOVERY_TYPE=single-node \
    XPACK_SECURITY_ENABLED=false \
    XPACK_LICENSE_SELF_GENERATED_TYPE=trial

# Change user back to root and fix ownership
USER root
RUN chown -R elastic_search_user:elastic_search_user /home/elastic_search_user/
WORKDIR /memory_scope_project

# (Not necessary) Install the majority of deps, using docker build cache to accelerate future building
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Enter working dir
WORKDIR /memory_scope_project
COPY . .
# RUN pip3 install poetry
# RUN poetry install
RUN pip3 install -r requirements.txt

# Launch!
# CMD ["bash"]
CMD ["bash", "examples/docker/entrypoint.sh"]