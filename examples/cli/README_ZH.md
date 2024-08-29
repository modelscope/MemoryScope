# MemoryScope 的命令行接口

## 使用方法

MemoryScope 可以通过两种不同的方式启动：

### 1. 使用 YAML 配置文件

如果您更喜欢通过 YAML 文件配置设置，可以通过提供配置文件的路径来实现：
```bash
memoryscope --config_path=memoryscope/core/config/demo_config.yaml
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