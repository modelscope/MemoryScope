import sys

sys.path.append(".")  # noqa: E402

import fire

from memoryscope.core.memoryscope import MemoryScope


def cli_job(**kwargs):
    kwargs["memory_chat_type"] = "cli_chat"
    MemoryScope(**kwargs).default_memory_chat.run()


if __name__ == "__main__":
    fire.Fire(cli_job)
