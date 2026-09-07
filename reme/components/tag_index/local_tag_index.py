"""In-memory tag index derived from ``FileNode.front_matter``."""

import asyncio
from pathlib import PurePosixPath

from .base_tag_index import BaseTagIndex
from ..component_registry import R
from ...schema import FileNode


@R.register("local")
class LocalTagIndex(BaseTagIndex):
    """Maintain bidirectional path/tag relationships without separate source I/O."""

    def __init__(self, max_tags_per_file: int = 8, max_tag_length: int = 64, **kwargs):
        super().__init__(**kwargs)
        self.max_tags_per_file = self._positive_int("max_tags_per_file", max_tags_per_file)
        self.max_tag_length = self._positive_int("max_tag_length", max_tag_length)
        self.path_to_tags: dict[str, tuple[str, ...]] = {}
        self.tag_to_paths: dict[str, set[str]] = {}
        self._maintenance_lock = asyncio.Lock()

    @property
    def n_files(self) -> int:
        return len(self.path_to_tags)

    @staticmethod
    def _positive_int(name: str, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    def _normalize_tags(self, value: object, *, limit: int | None) -> list[str]:
        """Normalize a strict tag list, optionally limiting the result count."""
        if not isinstance(value, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (str, int)):
                continue
            raw = str(item).strip()
            if not raw or len(raw) > self.max_tag_length or any(char.isspace() for char in raw):
                continue
            if not any(char.isalnum() for char in raw):
                continue
            canonical = raw.casefold()
            if canonical in seen:
                continue
            seen.add(canonical)
            result.append(canonical)
            if limit is not None and len(result) >= limit:
                break
        return result

    def normalize_tags(self, value: object) -> list[str]:
        """Normalize frontmatter tags according to the per-file count limit."""
        return self._normalize_tags(value, limit=self.max_tags_per_file)

    @staticmethod
    def _validate_path(path: str) -> str:
        if not isinstance(path, str) or not path or "\\" in path:
            raise ValueError(f"Invalid workspace-relative tag-index path: {path!r}")
        pure = PurePosixPath(path)
        if pure.is_absolute() or path != pure.as_posix() or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError(f"Invalid workspace-relative tag-index path: {path!r}")
        return path

    def _prepare_nodes(self, nodes: list[FileNode]) -> list[tuple[str, tuple[str, ...]]]:
        prepared: list[tuple[str, tuple[str, ...]]] = []
        for node in nodes:
            path = self._validate_path(node.path)
            tags = self.normalize_tags(node.front_matter.model_dump().get("tags"))
            prepared.append((path, tuple(tags)))
        return prepared

    @staticmethod
    def _replace(
        path_to_tags: dict[str, tuple[str, ...]],
        tag_to_paths: dict[str, set[str]],
        path: str,
        tags: tuple[str, ...],
    ) -> None:
        old_tags = path_to_tags.pop(path, ())
        for tag in old_tags:
            paths = tag_to_paths[tag]
            paths.discard(path)
            if not paths:
                del tag_to_paths[tag]
        if not tags:
            return
        path_to_tags[path] = tags
        for tag in tags:
            tag_to_paths.setdefault(tag, set()).add(path)

    async def rebuild(self, nodes: list[FileNode]) -> None:
        prepared = self._prepare_nodes(nodes)
        path_to_tags: dict[str, tuple[str, ...]] = {}
        tag_to_paths: dict[str, set[str]] = {}
        for path, tags in prepared:
            self._replace(path_to_tags, tag_to_paths, path, tags)
        async with self._maintenance_lock:
            self.path_to_tags = path_to_tags
            self.tag_to_paths = tag_to_paths
            self.is_healthy = True
        self.logger.info(f"Rebuilt tag index: files={len(path_to_tags)}, tags={len(tag_to_paths)}")

    async def upsert_nodes(self, nodes: list[FileNode]) -> None:
        prepared = self._prepare_nodes(nodes)
        if not prepared:
            return
        async with self._maintenance_lock:
            for path, tags in prepared:
                self._replace(self.path_to_tags, self.tag_to_paths, path, tags)

    async def delete(self, paths: list[str]) -> None:
        validated = [self._validate_path(path) for path in paths]
        if not validated:
            return
        async with self._maintenance_lock:
            for path in validated:
                self._replace(self.path_to_tags, self.tag_to_paths, path, ())

    async def paths_for_tags(self, tags: object, *, match_all: bool = True) -> list[str]:
        if not self.is_healthy:
            return []
        # ``max_tags_per_file`` constrains indexed documents, not lookup
        # expressions. Truncating here would silently weaken AND queries and
        # omit valid matches from OR queries.
        normalized = self._normalize_tags(tags, limit=None)
        if not normalized:
            return []
        async with self._maintenance_lock:
            postings = [self.tag_to_paths.get(tag, set()) for tag in normalized]
            matches = set.intersection(*postings) if match_all else set.union(*postings)
            return sorted(matches)

    async def tags_for_path(self, path: str) -> list[str]:
        if not self.is_healthy:
            return []
        path = self._validate_path(path)
        async with self._maintenance_lock:
            return list(self.path_to_tags.get(path, ()))

    async def clear(self) -> None:
        async with self._maintenance_lock:
            self.path_to_tags = {}
            self.tag_to_paths = {}
            self.is_healthy = True

    async def _close(self) -> None:
        await self.clear()
