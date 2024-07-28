python memoryscope/cli.py \
  -language="cn" \
  -memory_chat_class="cli_memory_chat" \
  -generation_backend="dashscope_generation" \
  -generation_model="qwen-max" \
  -embedding_backend="dashscope_embedding" \
  -embedding_model="text-embedding-v2" \
  -use_dummy_ranker=False \
  -rank_backend="dashscope_rank" \
  -rank_model="gte-rerank"