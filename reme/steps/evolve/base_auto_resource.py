"""Shared lifecycle and helpers for automatic resource processors."""

import asyncio
import errno
import hashlib
import os
import re
import stat
from abc import abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import frontmatter
from watchfiles import Change

from ...components.runtime_context import RuntimeContext
from ..base_step import BaseStep
from ..file_io import refresh_day_index, validate_filename_component
from ..file_io._path import is_relative_to, resolve_path
from ._evolve import now

_SOURCE_RESOURCE_KEY = "source_resource"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_LOOKUP_BATCH_KEY = "_auto_resource_lookup_batch"
_LookupKey = tuple[Path, str, int, int]


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    """Detect replacement, in-place edits, and edits which restore mtime."""
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


@dataclass(frozen=True)
class _ResourceDaySnapshot:
    """Metadata only: all direct Markdown files, not just currently owned notes."""

    directory: Path
    signature: tuple[int, ...]
    files: dict[str, tuple]


def _snapshot_note_day(workspace: Path, directory: Path) -> _ResourceDaySnapshot | None:
    """Inspect file metadata without reading bodies or parsing frontmatter."""
    try:
        directory_stat = directory.stat()
        if not stat.S_ISDIR(directory_stat.st_mode):
            return None
        files = {}
        with os.scandir(directory) as entries:
            for entry in entries:
                if Path(entry.name).suffix != ".md":
                    continue
                target = None
                if entry.is_symlink():
                    try:
                        target, error = resolve_path(workspace, entry.path)
                    except RuntimeError:
                        # Path.resolve reports symlink loops this way on 3.11/3.12.
                        continue
                    except OSError as exc:
                        if exc.errno == errno.ELOOP:
                            continue
                        raise
                    if error or target is None:
                        raise ValueError(f"invalid resource note path {entry.path!r}: {error}")
                try:
                    value = entry.stat()
                    if stat.S_ISREG(value.st_mode):
                        files[entry.name] = (
                            target,
                            _stat_signature(value),
                            _stat_signature(entry.stat(follow_symlinks=False)) if target is not None else None,
                        )
                except FileNotFoundError:
                    # A removed file or a dangling internal link is not a note.
                    continue
        return _ResourceDaySnapshot(directory, _stat_signature(directory_stat), files)
    except (FileNotFoundError, NotADirectoryError):
        return None


@dataclass
class _ResourceDayLookup:
    """Small, rebuildable ownership index; note bodies never enter the cache."""

    owners: dict[str, dict[str, str]] = field(default_factory=dict)
    day_sources: dict[str, set[str]] = field(default_factory=dict)
    snapshots: dict[str, _ResourceDaySnapshot] = field(default_factory=dict)

    def replace_day(self, day: str, notes: list[dict]) -> None:
        """Replace one day's owners, preserving daily_list's first-match order."""
        day_owners: dict[str, str] = {}
        for note in notes:
            source = str(note.get(_SOURCE_RESOURCE_KEY, "")).strip()
            if source and source not in day_owners:
                day_owners[source] = str(note["path"])
        for source in self.day_sources.pop(day, set()):
            owners = self.owners[source]
            owners.pop(day, None)
            if not owners:
                del self.owners[source]
        for source, path in day_owners.items():
            self.owners.setdefault(source, {})[day] = path
        self.day_sources[day] = set(day_owners)


class _ResourceLookupBatch:
    """Own modality-independent index construction, refresh and invocation lifetime."""

    def __init__(self):
        self.indexes: dict[_LookupKey, _ResourceDayLookup] = {}
        self.lock = asyncio.Lock()

    def close(self) -> None:
        """Drop ownership data; never carry it to another batch."""
        self.indexes.clear()

    async def get_lookup(
        self,
        key: _LookupKey,
        snapshot: Callable[[], dict[str, _ResourceDaySnapshot]],
        read_day: Callable[[str], Awaitable[list[dict]]],
    ) -> _ResourceDayLookup:
        """Reuse parsed ownership, checking disk changes from any writer before each lookup.

        Metadata checks still visit the files; unchanged days avoid daily_list
        and frontmatter parsing. Before/after snapshots detect writes during
        awaited reads, without requiring writers to cooperate with this batch.
        """
        async with self.lock:
            lookup = self.indexes.get(key) or _ResourceDayLookup()
            before = snapshot()
            for _ in range(4):
                changed_days = {
                    day
                    for day in before.keys() | lookup.snapshots.keys()
                    if before.get(day) != lookup.snapshots.get(day)
                }
                if not changed_days:
                    self.indexes[key] = lookup
                    return lookup
                for day in sorted(changed_days):
                    lookup.replace_day(day, await read_day(day) if day in before else [])
                    if day in before:
                        lookup.snapshots[day] = before[day]
                    else:
                        lookup.snapshots.pop(day, None)
                after = snapshot()
                if before == after:
                    # Publish only a complete, stable scan. On failure the
                    # recorded pre-read snapshots ensure the next call retries.
                    self.indexes[key] = lookup
                    return lookup
                before = after
            raise RuntimeError("Resource note ownership kept changing during lookup; retry the resource")


@contextmanager
def _resource_lookup_scope(context: RuntimeContext, *, reuse: bool = False):
    """Share a router's index with processors, never with the next watch batch."""
    previous = context.get(_LOOKUP_BATCH_KEY)
    if reuse and isinstance(previous, _ResourceLookupBatch):
        yield previous
        return
    existed = _LOOKUP_BATCH_KEY in context
    batch = _ResourceLookupBatch()
    context[_LOOKUP_BATCH_KEY] = batch
    try:
        yield batch
    finally:
        batch.close()
        if existed:
            context[_LOOKUP_BATCH_KEY] = previous
        else:
            del context[_LOOKUP_BATCH_KEY]


@dataclass(frozen=True)
class _ResourceNoteState:
    """Snapshot a linked note, or a collision-free path reserved for a new one."""

    path: str
    created: bool
    before_bytes: bytes | None


def _compute_note_stem(filename: str) -> str:
    """Return the daily note stem for a resource filename."""
    return PurePosixPath(filename).stem


def _parse_resource_path(file_path: str, resource_dir: str) -> tuple[str, str]:
    """Extract (date, filename) from a resource path like 'resource/2026-06-06/report.pdf'.

    Returns (date_str, filename) where filename may contain subdirectories.
    """
    parts = PurePosixPath(file_path).parts
    # Strip leading resource_dir prefix
    prefix_parts = PurePosixPath(resource_dir).parts
    if parts[: len(prefix_parts)] != prefix_parts:
        return "", ""
    parts = parts[len(prefix_parts) :]
    # First segment is date, rest is filename
    date_str = parts[0] if parts else ""
    if not _DATE_RE.match(date_str):
        return "", ""
    filename = str(PurePosixPath(*parts[1:])) if len(parts) > 1 else ""
    return date_str, filename


def _loose_resource_filename(file_path: str, resource_dir: str) -> str:
    """Return filename for a root-level resource path like 'resource/report.txt'."""
    parts = PurePosixPath(file_path).parts
    prefix_parts = PurePosixPath(resource_dir).parts
    if parts[: len(prefix_parts)] != prefix_parts:
        return ""
    rest = parts[len(prefix_parts) :]
    if len(rest) != 1:
        return ""
    filename = rest[0]
    return "" if filename in ("", ".", "..") else filename


def _results_answer(results: list[dict], processed_answer: str) -> str:
    """Return the actual per-change answer while preserving a batch fallback."""
    answers = [str(item.get("answer") or "").strip() for item in results]
    answers = [item for item in answers if item]
    if len(answers) == 1:
        return answers[0]
    if len(answers) > 1:
        return "\n\n".join(f"{index}. {answer}" for index, answer in enumerate(answers, start=1))
    return processed_answer


def _source_suffix(file_path: str) -> str:
    """Return a short stable suffix for source-path collision handling."""
    return hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]


def _sanitize_note_name(raw: str, fallback: str) -> str:
    """Return a safe single filename component from an LLM-suggested name."""
    name = str(raw or "").strip()
    name = _UNSAFE_FILENAME_CHARS.sub("-", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = str(fallback or "").strip()
    name = _UNSAFE_FILENAME_CHARS.sub("-", name).strip(" .")
    if not name or validate_filename_component(name, kind="name"):
        name = f"resource-{_source_suffix(fallback or raw or 'note')}"
    if validate_filename_component(name, kind="name"):
        name = f"resource-{_source_suffix(name)}"
    return name


class BaseAutoResourceStep(BaseStep):
    """Shared source-linked daily-note lifecycle for resource processors."""

    resource_fallback = False
    resource_suffixes: frozenset[str] = frozenset()
    router_inherit_keys = frozenset({"file_store", "language"})

    @classmethod
    def matches_change(cls, change: Mapping[str, Any]) -> bool:
        """Return whether this processor accepts a change before fallback.

        The predicate must stay synchronous and file-system independent because
        deleted resources no longer exist when the router evaluates them.
        """
        file_path = change.get("path") or change.get("file_path", "")
        return Path(str(file_path)).suffix.lower() in cls.resource_suffixes

    def _normalize_change(self, raw) -> Change | None:
        if isinstance(raw, Change):
            return raw
        if isinstance(raw, str):
            return Change.__members__.get(raw)
        return None

    def _today(self) -> str:
        tz = self.app_context.app_config.timezone if self.app_context is not None else None
        return now(tz).strftime("%Y-%m-%d")

    def _daily_note_path(self, day: str, name: str) -> str:
        return f"{self.config_value('daily_dir')}/{day}/{name}.md"

    def _resource_directory(self) -> tuple[str, Path]:
        """Return the workspace-relative identity and resolved resource root."""
        workspace = self.workspace_path.resolve()
        configured = str(self.config_value("resource_dir"))
        resolved, error = resolve_path(workspace, configured)
        if error or resolved is None:
            raise ValueError(f"invalid resource_dir {configured!r}: {error or 'cannot resolve path'}")

        logical = Path(configured)
        if logical.is_absolute():
            for workspace_variant in (self.workspace_path.absolute(), workspace):
                try:
                    logical = logical.relative_to(workspace_variant)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("resource_dir must stay inside the workspace")
        return logical.as_posix(), resolved

    def _resolve_resource_source(self, raw_path: str) -> tuple[str, Path, str]:
        """Return a logical resource path, safe read path, and logical resource root.

        The logical path is kept for ``source_resource`` provenance. The
        resolved path is used for stat/read so a symlink cannot escape the
        configured resource directory.
        """
        value = str(raw_path or "").strip()
        if not value:
            raise ValueError("resource path is required")

        supplied = Path(value)
        if any(part in {".", ".."} for part in supplied.parts):
            raise ValueError(f"resource path cannot contain '.' or '..': {value!r}")

        workspace = self.workspace_path.resolve()
        resource_dir, resource_root = self._resource_directory()

        resolved, path_error = resolve_path(workspace, value)
        if path_error or resolved is None:
            raise ValueError(f"invalid resource path {value!r}: {path_error or 'cannot resolve path'}")
        if not is_relative_to(resolved, resource_root):
            raise ValueError("resource path must stay inside the configured resource directory")

        if supplied.is_absolute():
            try:
                logical = supplied.relative_to(self.workspace_path.absolute())
            except ValueError:
                try:
                    logical = supplied.relative_to(workspace)
                except ValueError as exc:
                    raise ValueError("resource path must stay inside the workspace") from exc
        else:
            logical = supplied

        resource_logical = Path(resource_dir)
        try:
            logical.relative_to(resource_logical)
        except ValueError as exc:
            raise ValueError("resource path must stay inside the configured resource directory") from exc
        return logical.as_posix(), resolved, resource_dir

    @staticmethod
    def _source_resource_link(file_path: str) -> str:
        return f"[[{file_path}]]"

    def _frontmatter(self, path: str) -> dict:
        post = frontmatter.loads((self.file_store.workspace_path / path).read_text(encoding="utf-8"))
        return dict(post.metadata or {})

    def _note_bytes(self, path: str) -> bytes | None:
        note_path = self.file_store.workspace_path / path
        if not note_path.is_file():
            return None
        return note_path.read_bytes()

    def _note_modified(self, before_path: str, before_bytes: bytes | None, after_path: str) -> bool:
        if not after_path:
            return False
        after_bytes = self._note_bytes(after_path)
        if after_bytes is None:
            return before_bytes is not None
        return after_path != before_path or before_bytes != after_bytes

    async def _refresh_day_index(self, day: str) -> dict:
        """Refresh and return the derived daily index for a resource-note change."""
        daily_dir = self.config_value("daily_dir")
        self.logger.info(f"[{self.name}] refresh index start date={day} daily_dir={daily_dir}")
        index_payload = await refresh_day_index(self.file_store, day, daily_dir)
        self.logger.info(f"[{self.name}] refresh index done date={day}")
        return index_payload

    def _find_resource_note(self, notes: list[dict], file_path: str) -> dict | None:
        """Return only a note explicitly owned by ``file_path``."""
        source = self._source_resource_link(file_path)
        for note in notes:
            if str(note.get(_SOURCE_RESOURCE_KEY, "")).strip() == source:
                return note
        return None

    async def _list_resource_note(self, day: str, file_path: str) -> dict | None:
        notes = await self._list_daily_notes(day)
        return self._find_resource_note(notes, file_path)

    async def _list_daily_notes(self, day: str) -> list[dict]:
        """Use the configured daily_list job for both history and targeted checks."""
        list_response = await self.run_job("daily_list", date=day)
        if not list_response.success:
            raise RuntimeError(f"daily_list failed: {list_response.answer}")
        return list_response.metadata.get("notes") or []

    def _resource_lookup_cache(self) -> tuple[_ResourceLookupBatch | None, tuple]:
        """Keep overridden stores/configurations from sharing another lookup domain."""
        batch = self.context.get(_LOOKUP_BATCH_KEY) if self.context is not None else None
        if not isinstance(batch, _ResourceLookupBatch):
            return None, ()
        key = (
            self.workspace_path.resolve(),
            str(self.config_value("daily_dir")),
            id(self.file_store),
            id(self.app_context),
        )
        return batch, key

    def _resource_note_snapshot(self) -> dict[str, _ResourceDaySnapshot]:
        """Fingerprint daily notes, including unowned files, using metadata only."""
        workspace = self.workspace_path.resolve()
        daily_dir = str(self.config_value("daily_dir"))
        daily_root, error = resolve_path(workspace, daily_dir)
        if error or daily_root is None:
            raise ValueError(f"invalid daily_dir {daily_dir!r}: {error or 'cannot resolve path'}")
        snapshots = {}
        try:
            with os.scandir(daily_root) as entries:
                for entry in entries:
                    if not _DATE_RE.fullmatch(entry.name):
                        continue
                    directory = Path(entry.path)
                    if entry.is_symlink():
                        try:
                            directory, path_error = resolve_path(workspace, entry.path)
                        except (OSError, RuntimeError):
                            continue
                        if path_error or directory is None:
                            continue
                    value = _snapshot_note_day(workspace, directory)
                    if value is not None:
                        snapshots[entry.name] = value
        except (FileNotFoundError, NotADirectoryError):
            return {}
        return snapshots

    async def _find_loose_resource_day(self, file_path: str) -> str | None:
        """Resolve ownership through the common batch index, for any resource modality."""
        batch, key = self._resource_lookup_cache()
        if batch is None:
            assert self.context is not None
            with _resource_lookup_scope(self.context):
                return await self._find_loose_resource_day(file_path)
        lookup = await batch.get_lookup(key, self._resource_note_snapshot, self._list_daily_notes)
        matches = sorted(lookup.owners.get(self._source_resource_link(file_path), {}).items())
        if len(matches) > 1:
            paths = ", ".join(path for _, path in matches)
            raise RuntimeError(f"Multiple daily resource notes claim {file_path}: {paths}")
        return matches[0][0] if matches else None

    async def _prepare_resource_note(self, day: str, file_path: str, note_stem: str) -> _ResourceNoteState:
        """Find the owned note or allocate a safe path before the first write."""
        note = await self._list_resource_note(day, file_path)
        if note is not None:
            note_path = str(note["path"])
            return _ResourceNoteState(path=note_path, created=False, before_bytes=self._note_bytes(note_path))

        _, note_path = self._unique_daily_note_path(day, note_stem, file_path, current_path="")
        return _ResourceNoteState(path=note_path, created=True, before_bytes=None)

    async def _resolve_written_note(
        self,
        state: _ResourceNoteState,
        day: str,
        file_path: str,
    ) -> str | None:
        """Resolve a processor write without claiming a pre-existing same-stem note."""
        if not state.created:
            if self._note_bytes(state.path) is None:
                raise RuntimeError(f"linked resource note disappeared: {state.path}")
            return state.path

        note = await self._list_resource_note(day, file_path)
        if note is not None:
            return str(note["path"])
        if self._note_bytes(state.path) is None:
            return None

        # The path was absent when this invocation allocated it, so a note
        # created there without provenance can be repaired conservatively. A
        # different explicit owner is always a conflict and is never claimed.
        source = str(self._frontmatter(state.path).get(_SOURCE_RESOURCE_KEY, "")).strip()
        expected = self._source_resource_link(file_path)
        if source and source != expected:
            raise RuntimeError(f"resource note path is owned by another source: {state.path}")
        return state.path

    async def _ensure_resource_frontmatter(self, path: str, file_path: str) -> None:
        metadata = {_SOURCE_RESOURCE_KEY: self._source_resource_link(file_path)}
        current = self._frontmatter(path)
        if all(current.get(key) == value for key, value in metadata.items()):
            return
        response = await self.run_job(
            "frontmatter_update",
            path=path,
            metadata=metadata,
        )
        if not response.success:
            raise RuntimeError(f"frontmatter_update failed: {response.answer}")

    async def _set_frontmatter_name(self, path: str, name: str) -> None:
        if self._frontmatter(path).get("name") == name:
            return
        response = await self.run_job("frontmatter_update", path=path, metadata={"name": name})
        if not response.success:
            raise RuntimeError(f"frontmatter_update failed: {response.answer}")

    def _unique_daily_note_path(self, day: str, name: str, file_path: str, current_path: str) -> tuple[str, str]:
        """Return a collision-free (name, path), preserving current_path when possible."""
        target_path = self._daily_note_path(day, name)
        target_abs = self.file_store.workspace_path / target_path
        if target_path == current_path or not target_abs.exists():
            return name, target_path

        suffixed = f"{name}--{_source_suffix(file_path)}"
        target_path = self._daily_note_path(day, suffixed)
        target_abs = self.file_store.workspace_path / target_path
        if target_path == current_path or not target_abs.exists():
            return suffixed, target_path

        for index in range(2, 100):
            candidate = f"{suffixed}-{index}"
            target_path = self._daily_note_path(day, candidate)
            target_abs = self.file_store.workspace_path / target_path
            if target_path == current_path or not target_abs.exists():
                return candidate, target_path
        raise RuntimeError(f"cannot allocate unique note name for: {name!r}")

    async def _rename_from_frontmatter_name(
        self,
        path: str,
        day: str,
        file_path: str,
        fallback_name: str,
        *,
        allow_rename: bool,
    ) -> str:
        meta = self._frontmatter(path)
        current_name = PurePosixPath(path).stem
        suggested_name = str(meta.get("name", "")).strip()

        if not allow_rename:
            name = _sanitize_note_name(current_name, fallback_name)
            if suggested_name != name:
                await self._set_frontmatter_name(path, name)
            return path

        name = _sanitize_note_name(suggested_name, fallback_name)
        name, target_path = self._unique_daily_note_path(day, name, file_path, path)
        if suggested_name != name:
            await self._set_frontmatter_name(path, name)

        if target_path == path:
            return path

        move_response = await self.run_job(
            "move",
            src_path=path,
            dst_path=target_path,
            overwrite=False,
            retarget=True,
        )
        if not move_response.success:
            raise RuntimeError(f"move failed: {move_response.answer}")
        return target_path

    async def _finalize_resource_note(
        self,
        state: _ResourceNoteState,
        day: str,
        file_path: str,
        note_stem: str,
        added: bool,
    ) -> str | None:
        """Resolve, source-link, rename, index, and report one processor write."""
        staged_bytes = self._note_bytes(state.path)
        self.context.response.metadata.update(
            {
                "path": state.path if staged_bytes is not None else None,
                "created": state.created and staged_bytes is not None,
                "modified": self._note_modified(state.path, state.before_bytes, state.path),
            },
        )
        note_path = await self._resolve_written_note(state, day, file_path)
        if note_path is None:
            self.context.response.metadata.update({"path": None, "created": False, "modified": False})
            return None

        modified = self._note_modified(state.path, state.before_bytes, note_path)
        self.context.response.metadata.update({"path": note_path, "created": state.created, "modified": modified})
        await self._ensure_resource_frontmatter(note_path, file_path)
        note_path = await self._rename_from_frontmatter_name(
            note_path,
            day,
            file_path,
            note_stem,
            allow_rename=state.created,
        )
        modified = self._note_modified(state.path, state.before_bytes, note_path)
        self.context.response.metadata.update({"path": note_path, "created": state.created, "modified": modified})
        index_payload = await self._refresh_day_index(day)
        self.context.response.metadata.update(
            {
                "path": note_path,
                "created": state.created,
                "modified": modified,
                "session_id": note_stem,
                "source_resource": self._source_resource_link(file_path),
                "action": "added" if added else "modified",
                "index": index_payload,
            },
        )
        return note_path

    async def _handle_delete(self, file_path: str, date_str: str, note_stem: str) -> None:
        note = await self._list_resource_note(date_str, file_path)
        if note is None:
            self.context.response.success = True
            self.context.response.answer = f"No linked resource note to delete: {file_path}"
            self.context.response.metadata.update(
                {
                    "path": None,
                    "session_id": note_stem,
                    "source_resource": self._source_resource_link(file_path),
                    "action": "skipped",
                    "reason": "resource_note_not_found",
                    "modified": False,
                },
            )
            self.logger.info(f"[{self.name}] delete skipped; no owned note file_path={file_path}")
            return

        note_rel = str(note["path"])
        note_abs = self.workspace_path / note_rel
        note_existed = note_abs.is_file()
        self.logger.info(f"[{self.name}] delete start note={note_rel}")

        if note_existed:
            note_abs.unlink()
            self.logger.info(f"[{self.name}] Deleted file: {note_rel}")

        self.context.response.metadata.update(
            {
                "path": note_rel,
                "session_id": note_stem,
                "source_resource": self._source_resource_link(file_path),
                "action": "deleted",
                "modified": note_existed,
            },
        )
        await self.file_store.delete([note_rel])
        self.logger.info(f"[{self.name}] catalog delete done note={note_rel}")
        index_payload = await self._refresh_day_index(date_str)

        self.context.response.success = True
        self.context.response.answer = f"Deleted resource note: {note_rel}"
        self.context.response.metadata["index"] = index_payload

    @abstractmethod
    async def _handle_upsert(
        self,
        file_path: str,
        date_str: str,
        note_stem: str,
        added: bool,
        source_path: Path,
    ) -> None:
        """Interpret one added or modified resource into its daily note."""

    async def _handle_change(self, file_path: str, raw_change) -> dict:
        assert self.context is not None
        # Handlers write item-scoped fields into the shared response. Start each
        # change with a fresh mapping so one result cannot inherit another's metadata.
        self.context.response.metadata = {}
        if not file_path:
            self.context.response.success = False
            self.context.response.answer = "Missing file_path"
            self.logger.warning(f"[{self.name}] missing file_path change={raw_change!r}")
            return {"success": False, "path": file_path, "change": raw_change, "answer": self.context.response.answer}

        change = self._normalize_change(raw_change)
        if change is None:
            self.context.response.success = False
            self.context.response.answer = f"Invalid change type: {raw_change}"
            self.logger.warning(f"[{self.name}] invalid change file_path={file_path} change={raw_change!r}")
            return {"success": False, "path": file_path, "change": raw_change, "answer": self.context.response.answer}

        try:
            file_path, source_path, resource_dir = self._resolve_resource_source(file_path)
        except ValueError as exc:
            self.context.response.success = False
            self.context.response.answer = str(exc)
            self.context.response.metadata.update(
                {"path": str(file_path), "action": "failed", "error": str(exc), "modified": False},
            )
            self.logger.warning(f"[{self.name}] invalid resource path file_path={file_path!r} error={exc}")
            return {
                "success": False,
                "path": str(file_path),
                "change": change.name,
                "answer": self.context.response.answer,
                "metadata": dict(self.context.response.metadata),
            }

        loose_filename = _loose_resource_filename(file_path, resource_dir)
        if loose_filename:
            existing_day = await self._find_loose_resource_day(file_path)
            date_str, filename = existing_day or self._today(), loose_filename
            self.logger.info(
                f"[{self.name}] loose resource file_path={file_path} date={date_str} existing={bool(existing_day)}",
            )
        else:
            date_str, filename = _parse_resource_path(file_path, resource_dir)

        if not date_str or not filename:
            self.context.response.success = False
            self.context.response.answer = f"Cannot parse date/filename from: {file_path}"
            self.logger.warning(f"[{self.name}] parse path failed file_path={file_path} resource_dir={resource_dir}")
            return {"success": False, "path": file_path, "change": change.name, "answer": self.context.response.answer}

        note_stem = _compute_note_stem(filename)
        self.logger.info(f"[{self.name}] {change.name} file_path={file_path} note_stem={note_stem}")

        if change == Change.deleted:
            await self._handle_delete(file_path, date_str, note_stem)
        else:
            await self._handle_upsert(
                file_path,
                date_str,
                note_stem,
                change == Change.added,
                source_path,
            )
        return {
            "success": self.context.response.success,
            "path": file_path,
            "change": change.name,
            "answer": self.context.response.answer,
            "metadata": dict(self.context.response.metadata),
        }

    def _failed_change_result(self, file_path: str, raw_change, exc: Exception) -> dict:
        """Convert one unexpected processor error into an item-scoped result."""
        assert self.context is not None
        file_path = str(file_path or "")
        if Path(file_path).is_absolute():
            file_path = self.to_workspace_relative(file_path)
        change = self._normalize_change(raw_change)
        change_name = change.name if change is not None else str(raw_change)
        answer = f"Failed to process resource: {file_path}: {exc}"
        metadata = dict(self.context.response.metadata)
        metadata.setdefault("path", file_path)
        metadata.setdefault("modified", False)
        metadata.update({"action": "failed", "error": str(exc)})
        self.context.response.success = False
        self.context.response.answer = answer
        self.context.response.metadata = metadata
        self.logger.exception(f"[{self.name}] resource failed file_path={file_path} error={exc}")
        return {
            "success": False,
            "path": file_path,
            "change": change_name,
            "answer": answer,
            "metadata": dict(metadata),
        }

    async def execute(self):
        assert self.context is not None
        with _resource_lookup_scope(self.context, reuse=True):
            return await self._execute_changes()

    async def _execute_changes(self):
        """Process a sub-batch within the router's or a standalone lookup scope."""
        assert self.context is not None
        changes = self.context.get("changes")
        if not isinstance(changes, list):
            self.context.response.success = False
            self.context.response.answer = "AutoResourceStep requires changes: list[dict]"
            self.logger.warning(f"[{self.name}] invalid changes payload type={type(changes).__name__}")
            return self.context.response

        self.logger.info(f"[{self.name}] start changes={len(changes)}")
        results = []
        for index, item in enumerate(changes, start=1):
            if not isinstance(item, dict):
                self.logger.warning(f"[{self.name}] skip invalid change item index={index} type={type(item).__name__}")
                continue
            self.logger.info(f"[{self.name}] process change {index}/{len(changes)}")
            file_path = item.get("path") or item.get("file_path", "")
            raw_change = item.get("change", "")
            self.context.response.metadata = {}
            try:
                result = await self._handle_change(file_path, raw_change)
            except Exception as exc:  # pylint: disable=broad-except
                result = self._failed_change_result(file_path, raw_change, exc)
            results.append(result)
        success_count = sum(1 for item in results if item.get("success"))
        self.context.response.success = success_count == len(changes)
        processed_answer = f"Processed {success_count}/{len(changes)} resource change(s)"
        self.context.response.answer = _results_answer(results, processed_answer)
        self.context.response.metadata["processed"] = len(results)
        self.context.response.metadata["results"] = results
        self.context.response.metadata["modified"] = any(
            bool((item.get("metadata") or {}).get("modified")) for item in results
        )
        self.logger.info(
            f"[{self.name}] done success={success_count}/{len(changes)} "
            f"processed={len(results)} modified={self.context.response.metadata['modified']}",
        )
        return self.context.response
