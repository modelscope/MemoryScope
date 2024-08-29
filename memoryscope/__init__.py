""" Version of MemoryScope."""
__version__ = "0.1.0.5"
import fire

from memoryscope.core.config.arguments import Arguments  # noqa: F401
from memoryscope.core.memoryscope import MemoryScope  # noqa: F401


def cli():
    fire.Fire(MemoryScope.cli_memory_chat)
