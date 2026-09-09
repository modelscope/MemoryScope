"""Abstract interface for file-level tag indexes derived from graph nodes."""

from abc import abstractmethod

from ..base_component import BaseComponent
from ...enumeration import ComponentEnum
from ...schema import FileNode


class BaseTagIndex(BaseComponent):
    """A rebuildable index of normalized ``FileNode`` frontmatter tags."""

    component_type = ComponentEnum.TAG_INDEX

    def __init__(self, tag_key="tags", **kwargs):
        super().__init__(**kwargs)
        self.tag_key = tag_key
        self.is_healthy = True

    @property
    def tag_key(self) -> str:
        """Frontmatter field from which this index derives tags."""
        return self._tag_key

    @tag_key.setter
    def tag_key(self, value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("tag_key must be a non-empty string")
        self._tag_key = value.strip()

    def set_healthy(self, healthy: bool) -> None:
        """Mark whether lookups can safely use the current derived state."""
        self.is_healthy = healthy

    @property
    @abstractmethod
    def n_files(self) -> int:
        """Return the number of files that currently have indexed tags."""

    @abstractmethod
    def normalize_tags(self, value: object) -> list[str]:
        """Return canonical tags according to this index's configured limits."""

    def normalize_query_tags(self, value: object) -> list[str]:
        """Return canonical lookup tags.

        Existing third-party indexes remain compatible by inheriting their
        normal tag canonicalization. Implementations with per-file count limits
        should override this method so lookup expressions are not truncated.
        """
        return self.normalize_tags(value)

    @abstractmethod
    async def rebuild(self, nodes: list[FileNode]) -> None:
        """Replace the complete index with relationships derived from ``nodes``."""

    @abstractmethod
    async def upsert_nodes(self, nodes: list[FileNode]) -> None:
        """Insert or replace relationships derived from ``nodes``."""

    @abstractmethod
    async def delete(self, paths: list[str]) -> None:
        """Delete relationships by workspace-relative path."""

    @abstractmethod
    async def paths_for_tags(self, tags: object, *, match_all: bool = True) -> list[str]:
        """Return sorted paths matching all or any normalized tags."""

    @abstractmethod
    async def tags_for_path(self, path: str) -> list[str]:
        """Return normalized tags for one workspace-relative path."""

    @abstractmethod
    async def list_tags(
        self,
        *,
        page: int = 1,
        order_by: str = "tag",
        order: str | None = None,
        page_size: int = 100,
    ) -> dict[str, object]:
        """Return a page of active tags with counts and a 1-based result range."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear memory and persisted state."""
