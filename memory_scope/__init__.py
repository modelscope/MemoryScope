""" Version of MemoryScope."""

__version__ = "0.1.0-alpha.1"


from .cli import MemoryScope, CliJob

__all__ = [
    "MemoryScope",
    "CliJob",
]