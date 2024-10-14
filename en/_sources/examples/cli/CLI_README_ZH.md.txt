# MemoryScope 的命令行接口

## 使用方法
在运行之前，请先按照 Readme 中的 [**Installation**](../../docs/installation_zh.md#三通过-pypi-安装) 指南进行安装，并启动 Docker 镜像。
MemoryScope 可以通过两种不同的方式启动：

### 1. 使用 YAML 配置文件

如果您更喜欢通过 YAML 文件配置设置，可以通过提供配置文件的路径来实现：
```bash
memoryscope --config_path=memoryscope/core/config/demo_config_zh.yaml
```
 
### 2. 使用命令行参数

或者，您可以直接在命令行上指定所有参数：

```
# 中文
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
# 英文
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

以下是可以通过任一方法设置的可用选项：

- `--language`: 对话中使用的语言。
- `--memory_chat_class`: 管理聊天记录的类名。
- `--human_name`: 人类用户的名字。
- `--assistant_name`: AI 助手的名字。
- `--generation_backend`: 用于生成回复的后端。
- `--generation_model`: 用于生成回复的模型。
- `--embedding_backend`: 用于文本嵌入的后端。
- `--embedding_model`: 用于创建文本嵌入的模型。
- `--enable_ranker`: 一个布尔值，指示是否使用排名器（默认为 False）。
- `--rank_backend`: 用于排名回复的后端。
- `--rank_model`: 用于排名回复的模型。

### 3. 查看记忆
按照第二步的方式可以打开两个命令行的窗口。
其中一个命令行窗口可以和AI进行对话，另一个命令行窗口可以查看AI关于用户的长期记忆
使用/help打开命令行帮助，找到/list_memory的命令和对应自动刷新的指令。
```
/list_memory refresh_time=5
```
接下来就可以和AI进行愉快地交流啦。