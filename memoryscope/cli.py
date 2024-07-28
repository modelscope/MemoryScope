import sys

sys.path.append(".")  # noqa: E402

import fire

from memoryscope.core.memoryscope import MemoryScope


def cli_job(**kwargs):
    with MemoryScope(**kwargs) as ms:
        memory_chat = ms.default_memory_chat
        memory_chat.run()


if __name__ == "__main__":
    fire.Fire(cli_job)
