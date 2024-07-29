import sys

sys.path.append(".")

from memoryscope import MemoryScope, Arguments

arguments = Arguments(
    language="cn",
    human_name="用户",
    assistant_name="AI",
    logger_to_screen=False,
    memory_chat_class="api_memory_chat",
    generation_backend="dashscope_generation",
    generation_model="qwen-max",
    embedding_backend="dashscope_embedding",
    embedding_model="text-embedding-v2",
    use_dummy_ranker=False,
    rank_backend="dashscope_rank",
    rank_model="gte-rerank",
)


def chat_example1():
    with MemoryScope(config_path="memoryscope/core/config/demo_config.yaml") as ms:
        memory_chat = ms.default_memory_chat
        response = memory_chat.chat_with_memory(query="我的爱好是弹琴。")
        print("回答：\n" + response.message.content)
        print("记忆：\n" + response.meta_data["memories"])


def chat_example2():
    with MemoryScope(arguments=arguments) as ms:
        memory_chat = ms.default_memory_chat

        response = memory_chat.chat_with_memory(query="我的爱好是弹琴。")
        print("回答：\n" + response.message.content)
        print("记忆：\n" + response.meta_data["memories"])


def chat_example3():
    with MemoryScope(arguments=arguments) as ms:
        memory_chat = ms.default_memory_chat

        response = memory_chat.chat_with_memory(
            query="你知道我消灭了几个星系吗？",
            extra_memories="用户是一只哥斯拉，这是真是的，不是虚构的。\n前天用户消灭了星系0x4be？\n大前天用户消灭了星系0x5be？")
        print("回答：\n" + response.message.content)


def chat_example4():
    with MemoryScope(arguments=arguments) as ms:
        memory_chat = ms.default_memory_chat
        memory_chat.start_backend_service()

        response = memory_chat.chat_with_memory(query="我的爱好是弹琴。")
        print("回答1：\n" + response.message.content)

        memory_chat.run_service_operation("consolidate_memory")
        response = memory_chat.chat_with_memory(query="你知道我的乐器爱好是什么？",
                                                history_message_strategy=None)
        print("回答2：\n" + response.message.content)
        print("记忆2：\n" + response.meta_data["memories"])


if __name__ == "__main__":
    chat_example1()
    # chat_example2()
    # chat_example3()
    # chat_example4()
