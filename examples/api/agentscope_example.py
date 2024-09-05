from typing import Optional, Union, Sequence

import agentscope
from agentscope.agents import AgentBase, UserAgent
from agentscope.message import Msg

from memoryscope import MemoryScope, Arguments


class MemoryScopeAgent(AgentBase):
    def __init__(self, name: str, arguments: Arguments, **kwargs) -> None:
        # Disable AgentScope memory and use MemoryScope memory instead
        super().__init__(name, use_memory=False, **kwargs)

        # Create a memory client in MemoryScope
        self.memory_scope = MemoryScope(arguments=arguments)
        self.memory_chat = self.memory_scope.default_memory_chat

    def reply(self, x: Optional[Union[Msg, Sequence[Msg]]] = None) -> Msg:
        # Generate response
        response = self.memory_chat.chat_with_memory(query=x.content)

        # Wrap the response in a message object in AgentScope
        msg = Msg(name=self.name, content=response.message.content, role="assistant")

        # Print/speak the message in this agent's voice
        self.speak(msg)

        return msg

    def close(self):
        # Close the backend service of MemoryScope
        self.memory_scope.close()


def main():
    # Setting of MemoryScope
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
        rank_model="gte-rerank")

    # Initialize AgentScope
    agentscope.init(project="MemoryScope")

    memoryscope_agent = MemoryScopeAgent(name="Assistant", arguments=arguments)

    user_agent = UserAgent()

    # Dialog
    msg = None
    while True:
        # User input
        msg = user_agent(msg)
        if msg.content == "exit":
            break
        # Agent speaks
        msg = memoryscope_agent(msg)

    # End memory
    memoryscope_agent.close()


if __name__ == "__main__":
    main()
