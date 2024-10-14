# The Cli Interface of MemoryScope

## Usage
Before running, follow the [**Installation**](../../docs/installation.md#iii-install-from-pypi) guidelines in Readme, and start the Docker image first.
MemoryScope can be launched in two different ways:

### 1. Using YAML Configuration File

If you prefer to configure your settings via a YAML file, you can do so by providing the path to the configuration file as follows:
```bash
memoryscope --config_path=memoryscope/core/config/demo_config.yaml
```

### 2. Using Command Line Arguments

Alternatively, you can specify all the parameters directly on the command line:

```bash
# Chinese / Dashscope
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
# English / OpenAI
memoryscope --language="en" \
            --memory_chat_class="cli_memory_chat" \
            --human_name="user" \
            --assistant_name="AI" \
            --generation_backend="openai_generation" \
            --generation_model="gpt-4o" \
            --embedding_backend="openai_embedding" \
            --embedding_model="text-embedding-3-small" \
            --enable_ranker=False
```

Here are the available options that can be set through either method:

- `--language`: The language used for the conversation.
- `--memory_chat_class`: The class name for managing the chat history.
- `--human_name`: The name of the human user.
- `--assistant_name`: The name of the AI assistant.
- `--generation_backend`: The backend used for generating responses.
- `--generation_model`: The model used for generating responses.
- `--embedding_backend`: The backend used for text embeddings.
- `--embedding_model`: The model used for creating text embeddings.
- `--enable_ranker`: A boolean indicating whether to use a dummy ranker (default is `False`).
- `--rank_backend`: The backend used for ranking responses.
- `--rank_model`: The model used for ranking responses.

### 3. View Memory
You can open two command line windows following the method in the second step. 
In one command line window, you can have a conversation with the AI, while in the other, you can check the AI's long-term memory about the user.
Use /help to open the command line help, and find the command /list_memory along with the corresponding auto-refresh instruction.
```
/list_memory refresh_time=5
```
Then you can enjoy a pleasant conversation with the AI!