"""Invocation-scoped image-note locators; editable Markdown remains authoritative."""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import stat

import frontmatter

from ..file_io._file_io import get_path_lock

_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_RESERVED_NAME = re.compile(r"session-image-([0-9a-f]{64})\.md")
_IDENTITY_KEYS = ("kind", "image_fingerprint", "source_sha256", "source_resource")


class _SnapshotChangedError(ValueError):
    """A scan observed concurrent source changes, not invalid source metadata."""


@dataclass(frozen=True)
class _Day:
    signature: tuple
    notes: dict[str, dict]


@dataclass(frozen=True)
class _Snapshot:
    root_signature: tuple | None
    days: dict[str, _Day]
    owners: dict[str, tuple[str, ...]]
    occupied: dict[str, tuple[str, ...]]


class ImageNoteLookup:
    """Cache paths/identity metadata, never caption bodies or durable hidden state.

    Call ``find`` while holding the caption fingerprint's normal lock. Every
    call stats the root and known dates, rescanning only changed/invalidated
    dates. Thus ordinary cross-invocation creation and rename invalidate a
    stale negative, without a directory traversal for every image occurrence.

    This is a call-local metadata snapshot, not a filesystem watcher. An external
    in-place change to an *unselected* note's fingerprint may be discovered only
    in the next invocation if its directory signature does not change. Selected
    notes always have their current body and identity reread under their lock.
    Same-process publishers share the daily-root catalog lock during their
    filesystem publication only, never while awaiting a caption model.
    A changing scan is rebuilt at most twice (three attempts total); unrelated
    IO, metadata, and selected-note validation errors are never retried.
    """

    def __init__(
        self,
        workspace: Path,
        daily_dir: str,
        *,
        resolve: Callable[[str], Path],
        max_note_bytes: int = 1024 * 1024,
    ):
        self.workspace = Path(workspace).resolve()
        self.daily_dir = str(daily_dir)
        self.resolve = resolve
        if max_note_bytes <= 0:
            raise ValueError("Image-note read limit must be positive")
        self.max_note_bytes = max_note_bytes
        self._snapshot: _Snapshot | None = None
        self._dirty: dict[str, int] = {}
        self._generation = 0
        self._lock = asyncio.Lock()

    def invalidate_day(self, day: str) -> None:
        """Invalidate after a possible write, including a partially failed write."""
        self._generation += 1
        self._dirty[day] = self._generation

    async def get_catalog_lock(self) -> asyncio.Lock:
        """Share a resolved daily-root lock for metadata scans and card writes.

        The order is fingerprint, catalog, then individual note path. Release
        the catalog before awaiting models or reading a selected note body.
        Resolving a lock key does not create any lock file or directory.
        """
        target = await asyncio.to_thread(self._path, self.daily_dir)
        return await get_path_lock(target)

    def _path(self, relative: str) -> Path:
        # The caller's resolver applies its current allowed-path permissions.
        # Independently retain containment even with a custom resolver in tests.
        target = Path(self.resolve(relative)).resolve()
        if not target.is_relative_to(self.workspace):
            raise ValueError("Image-note lookup path must stay inside the workspace")
        return target

    @staticmethod
    def _signature(path: Path) -> tuple:
        value = path.stat()
        return (
            str(path),
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    def _directory_signature(self, relative: str) -> tuple:
        path = self._path(relative)
        signature = self._signature(path)
        if not stat.S_ISDIR(signature[3]):
            raise ValueError("Image-note lookup date path must be a directory")
        return signature

    def _read_post(self, relative: str, expected_target: Path | None = None) -> frontmatter.Post:
        path = self._path(relative)
        if expected_target is not None and path != expected_target:
            raise ValueError("Image-note path changed while waiting for its read lock")
        before = self._signature(path)
        if not stat.S_ISREG(before[3]) or not 0 < before[4] <= self.max_note_bytes:
            raise ValueError("Image note is missing, empty, non-regular, or exceeds its byte limit")
        with path.open("rb") as handle:
            content = handle.read(self.max_note_bytes + 1)
        if (
            not 0 < len(content) <= self.max_note_bytes
            or self._signature(path) != before
            or self._path(relative) != path
        ):
            raise ValueError("Image note changed during its bounded read")
        return frontmatter.loads(content.decode("utf-8"))

    def _read_identity(self, relative: str) -> dict:
        """Read only bounded frontmatter; ordinary empty/long bodies are irrelevant."""
        path = self._path(relative)
        before = self._signature(path)
        if not stat.S_ISREG(before[3]):
            raise ValueError("Image-note metadata path must be a regular file")
        lines = []
        consumed = 0
        handler = None
        with path.open("rb") as handle:
            while True:
                line = handle.readline(self.max_note_bytes - consumed + 1)
                consumed += len(line)
                if handler is None:
                    if not line:
                        metadata = {}
                        break
                    if line.strip():
                        # Ordinary note bodies are not interpreted. A bounded
                        # probe may end halfway through a multibyte character.
                        text = line.decode("utf-8", errors="replace").strip()
                        handler = frontmatter.detect_format(text, frontmatter.handlers)
                        if handler is None:
                            metadata = {}
                            break
                        lines.append(text + "\n")
                else:
                    text = line.decode("utf-8")
                    lines.append(text)
                    if handler.FM_BOUNDARY.fullmatch(text.rstrip("\r\n")):
                        metadata = frontmatter.loads("".join(lines)).metadata
                        break
                    if not line:
                        raise ValueError("Image-note frontmatter is missing its closing delimiter")
                if consumed > self.max_note_bytes:
                    raise ValueError("Image-note frontmatter exceeds its byte limit")
        if consumed > self.max_note_bytes and handler is not None:
            raise ValueError("Image-note frontmatter exceeds its byte limit")
        if self._signature(path) != before or self._path(relative) != path:
            raise _SnapshotChangedError("Image-note metadata changed during lookup")
        return {key: metadata.get(key) for key in _IDENTITY_KEYS}

    @staticmethod
    def _valid_day(name: str) -> bool:
        try:
            return len(name) == 10 and date.fromisoformat(name).isoformat() == name
        except ValueError:
            return False

    def _scan_day(self, day: str, signature: tuple) -> _Day:
        relative = f"{self.daily_dir}/{day}"
        notes = {}
        for path in sorted(self._path(relative).iterdir()):
            if path.suffix != ".md":
                continue
            # Keep the logical path through an authorized internal directory
            # symlink, not its canonical target's potentially different name.
            note_path = f"{relative}/{path.name}"
            notes[note_path] = self._read_identity(note_path)
        if self._directory_signature(relative) != signature:
            raise _SnapshotChangedError("Image-note directory changed during lookup")
        return _Day(signature, notes)

    def _refresh(self, dirty: set[str], *, rebuild: bool = False) -> _Snapshot:
        old = None if rebuild else self._snapshot
        try:
            root_signature = self._directory_signature(self.daily_dir)
        except FileNotFoundError:
            # A genuinely absent daily tree is an empty source, not an IO
            # failure in the middle of a populated tree.
            if (self.workspace / self.daily_dir).is_symlink():
                raise
            return _Snapshot(None, {}, {}, {})
        if old is None or old.root_signature != root_signature:
            names = sorted(path.name for path in self._path(self.daily_dir).iterdir() if self._valid_day(path.name))
        else:
            names = list(old.days)
        days = {}
        changed = old is None or old.root_signature != root_signature
        for day in names:
            signature = self._directory_signature(f"{self.daily_dir}/{day}")
            previous = old.days.get(day) if old is not None else None
            if previous is None or previous.signature != signature or day in dirty:
                days[day] = self._scan_day(day, signature)
                changed = True
            else:
                days[day] = previous
        if self._directory_signature(self.daily_dir) != root_signature:
            raise _SnapshotChangedError("Daily tree changed during image-note lookup")
        if not changed:
            return old
        owners, occupied = defaultdict(list), defaultdict(list)
        for state in days.values():
            for path, metadata in state.notes.items():
                fingerprint = metadata.get("image_fingerprint")
                if isinstance(fingerprint, str) and _FINGERPRINT.fullmatch(fingerprint):
                    owners[fingerprint].append(path)
                if match := _RESERVED_NAME.fullmatch(Path(path).name):
                    occupied[match.group(1)].append(path)
        return _Snapshot(
            root_signature,
            days,
            {key: tuple(paths) for key, paths in owners.items()},
            {key: tuple(paths) for key, paths in occupied.items()},
        )

    async def _stable_snapshot(self, dirty: set[str]) -> _Snapshot:
        attempts = 0
        while True:
            try:
                return await asyncio.to_thread(self._refresh, dirty, rebuild=attempts > 0)
            except _SnapshotChangedError:
                attempts += 1
                if attempts == 3:
                    raise

    @staticmethod
    def _validate(post: frontmatter.Post, fingerprint: str, record: dict) -> None:
        if post.get("kind") != "session_image" or post.get("image_fingerprint") != fingerprint:
            raise ValueError("Session image note identity is occupied or has changed")
        if (
            post.get("source_sha256") != record["source_sha256"]
            or post.get("source_resource") != f"[[{record['source_path']}]]"
        ):
            raise ValueError("Session image note source does not match the original image")
        if not post.content.strip():
            raise ValueError("Stored image note is empty; restore its caption before reusing it")

    async def find(self, fingerprint: str, record: dict) -> tuple[str, frontmatter.Post] | None:
        """Return one current, source-validated note, or a refreshed negative."""
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            raise ValueError("Image fingerprint must be a lowercase SHA-256 hex digest")
        async with self._lock:
            async with await self.get_catalog_lock():
                dirty = dict(self._dirty)
                # No partial directory scan or dirty-day update is ever published.
                snapshot = await self._stable_snapshot(set(dirty))
                self._snapshot = snapshot
                for day, generation in dirty.items():
                    if self._dirty.get(day) == generation:
                        del self._dirty[day]
            candidates = set(snapshot.owners.get(fingerprint, ())) | set(snapshot.occupied.get(fingerprint, ()))
            if not candidates:
                return None
            if len(candidates) != 1:
                raise ValueError("Multiple daily notes claim the same session image fingerprint")
            relative = next(iter(candidates))
            target = await asyncio.to_thread(self._path, relative)
            lock = await get_path_lock(target)
            async with lock:
                post = await asyncio.to_thread(self._read_post, relative, target)
                self._validate(post, fingerprint, record)
            return relative, post
