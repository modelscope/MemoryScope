from typing import Optional, Union, Literal, Dict, List, Any, Tuple

from autogen import Agent, ConversableAgent, UserProxyAgent

from memoryscope import MemoryScope, Arguments


class MemoryScopeAgent(ConversableAgent):
    def __init__(
            self,
            name: str = "assistant",
            system_message: Optional[str] = "",
            human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
            llm_config: Optional[Union[Dict, bool]] = None,
            arguments: Arguments = None,
            **kwargs,
    ):
        super().__init__(
            name=name,
            system_message=system_message,
            human_input_mode=human_input_mode,
            llm_config=llm_config,
            **kwargs,
        )

        # Create a memory client in MemoryScope
        self.memory_scope = MemoryScope(arguments=arguments)
        self.memory_chat = self.memory_scope.default_memory_chat

        self.register_reply([Agent, None], MemoryScopeAgent.generate_reply_with_memory, remove_other_reply_funcs=True)

    def generate_reply_with_memory(
            self,
            messages: Optional[List[Dict]] = None,
            sender: Optional[Agent] = None,
            config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        # Generate response

        contents = []
        for message in messages:
            if message.get("role") != self.name:
                contents.append(message.get("content", ""))

        query = contents[-1]
        response = self.memory_chat.chat_with_memory(query=query)
        return True, response.message.content

    def close(self):
        self.memory_scope.close()


def main():
    # Create the agent of MemoryScope
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
        rank_model="gte-rerank"
    )

    assistant = MemoryScopeAgent("assistant", arguments=arguments)

    # Create the agent that represents the user in the conversation.
    user_proxy = UserProxyAgent("user", code_execution_config=False)

    # Let the assistant start the conversation.  It will end when the user types exit.
    assistant.initiate_chat(user_proxy, message="有什么需要帮忙的吗？")
    assistant.close()


if __name__ == "__main__":
    main()
