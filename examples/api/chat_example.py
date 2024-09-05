from memoryscope import MemoryScope, Arguments

arguments = Arguments(
    language="cn",
    human_name="用户",
    assistant_name="AI",
    memory_chat_class="api_memory_chat",
    generation_backend="dashscope_generation",
    generation_model="qwen-max",
    embedding_backend="dashscope_embedding",
    embedding_model="text-embedding-v2",
    rank_backend="dashscope_rank",
    rank_model="gte-rerank",
    enable_ranker=True)


def chat_example1():
    with MemoryScope(config_path="memoryscope/core/config/demo_config_zh.yaml") as ms:
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
            temporary_memories="张三是一只哥斯拉，这是真是的，不是虚构的。\n前天张三消灭了星系0x4be？\n大前天张三消灭了星系0x5be？")
        print("回答：\n" + response.message.content)


def chat_example4():
    with MemoryScope(arguments=arguments) as ms:
        memory_chat = ms.default_memory_chat
        memory_chat.run_service_operation("delete_all")

        response = memory_chat.chat_with_memory(query="我的爱好是弹琴。")
        print("回答1：\n" + response.message.content)
        result = memory_chat.run_service_operation("consolidate_memory")
        print(result)

        response = memory_chat.chat_with_memory(query="你知道我的乐器爱好是什么？", history_message_strategy=None)
        print("回答2：\n" + response.message.content)
        print("记忆2：\n" + response.meta_data["memories"])


def chat_example5():
    with MemoryScope(arguments=arguments) as ms:
        memory_service = ms.default_memory_service
        memory_service.init_service()

        result = memory_service.list_memory()
        print(f"list_memory result={result}")

        result = memory_service.retrieve_memory()
        print(f"retrieve_memory result={result}")

        result = memory_service.consolidate_memory()
        print(f"consolidate_memory result={result}")


def chat_example6():
    with MemoryScope(arguments=arguments) as ms:
        memory_chat = ms.default_memory_chat
        memory_chat.run_service_operation("delete_all", "张三")
        memory_chat.run_service_operation("delete_all", "李四")

        print("李四=========================")
        response = memory_chat.chat_with_memory(query="我的爱好是弹琴。", role_name="李四")
        print("回答1：\n" + response.message.content)
        result = memory_chat.run_service_operation("consolidate_memory", role_name="李四")
        print(result)
        response = memory_chat.chat_with_memory(query="你知道我的乐器爱好是什么？", role_name="李四",
                                                history_message_strategy=None)
        print("回答2：\n" + response.message.content)
        print("记忆2：\n" + response.meta_data["memories"])

        print("张三=========================")
        response = memory_chat.chat_with_memory(query="我的爱好是打羽毛球。", role_name="张三")
        print("回答1：\n" + response.message.content)
        result = memory_chat.run_service_operation("consolidate_memory", role_name="张三")
        print(result)
        response = memory_chat.chat_with_memory(query="你知道我的运动爱好是什么？", role_name="张三",
                                                history_message_strategy=None)
        print("回答2：\n" + response.message.content)
        print("记忆2：\n" + response.meta_data["memories"])


if __name__ == "__main__":
    # chat_example1()
    # chat_example2()
    # chat_example3()
    chat_example4()
    # chat_example5()
    # chat_example6()
