""" Version of MemoryScope."""
import importlib.metadata
__version__ = importlib.metadata.version("memoryscope")

import fire

from memoryscope.core.config.arguments import Arguments  # noqa: F401
from memoryscope.core.memoryscope import MemoryScope  # noqa: F401


def cli():
    fire.Fire(MemoryScope.cli_memory_chat)
