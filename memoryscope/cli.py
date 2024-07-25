import sys

from memoryscope.chat.base_memory_chat import BaseMemoryChat
from memoryscope.memoryscope import MemoryScope

sys.path.append(".")  # noqa: E402

import fire


def cli_job(config_path: str):
    ms = MemoryScope(config_path=config_path)
    memory_chat: BaseMemoryChat = ms.default_memory_chat
    memory_chat.run()


if __name__ == "__main__":
    fire.Fire(cli_job)
