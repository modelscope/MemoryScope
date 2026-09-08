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
    stamps: dict[str, tuple]


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
    Publication checks enumerate file stamps, including otherwise unchanged
    dates, so an external in-place restore during the model call is visible.
    Changed dates reuse unchanged identities: a batch reads each stable old
    note once and each new note once, though file enumeration/stats still scale
    with the number of publications times the number of historical notes.
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

    def _scan_day(self, day: str, signature: tuple, previous: _Day | None = None) -> _Day:
        relative = f"{self.daily_dir}/{day}"
        notes, stamps = {}, {}
        for path in sorted(self._path(relative).iterdir()):
            if path.suffix != ".md":
                continue
            # Keep the logical path through an authorized internal directory
            # symlink, not its canonical target's potentially different name.
            note_path = f"{relative}/{path.name}"
            stamp = self._signature(self._path(note_path))
            if previous is not None and previous.stamps.get(note_path) == stamp:
                notes[note_path] = previous.notes[note_path]
            else:
                notes[note_path] = self._read_identity(note_path)
                if self._signature(self._path(note_path)) != stamp:
                    raise _SnapshotChangedError("Image-note metadata changed during lookup")
            stamps[note_path] = stamp
        if self._directory_signature(relative) != signature:
            raise _SnapshotChangedError("Image-note directory changed during lookup")
        return _Day(signature, notes, stamps)

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
                days[day] = self._scan_day(day, signature, previous)
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

    async def _update_snapshot(self, *, recheck_files: bool = False) -> _Snapshot:
        """Publish one complete differential snapshot while the catalog is held."""
        dirty = dict(self._dirty)
        inspect_days = set(dirty)
        if recheck_files and self._snapshot is not None:
            inspect_days.update(self._snapshot.days)
        snapshot = await self._stable_snapshot(inspect_days)
        self._snapshot = snapshot
        for day, generation in dirty.items():
            if self._dirty.get(day) == generation:
                del self._dirty[day]
        return snapshot

    @staticmethod
    def _candidate(snapshot: _Snapshot, fingerprint: str) -> str | None:
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            raise ValueError("Image fingerprint must be a lowercase SHA-256 hex digest")
        candidates = set(snapshot.owners.get(fingerprint, ())) | set(snapshot.occupied.get(fingerprint, ()))
        if len(candidates) > 1:
            raise ValueError("Multiple daily notes claim the same session image fingerprint")
        return next(iter(candidates), None)

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

    async def _read_candidate(
        self,
        relative: str | None,
        fingerprint: str,
        record: dict,
    ) -> tuple[str, frontmatter.Post] | None:
        if relative is None:
            return None
        target = await asyncio.to_thread(self._path, relative)
        lock = await get_path_lock(target)
        async with lock:
            post = await asyncio.to_thread(self._read_post, relative, target)
            self._validate(post, fingerprint, record)
        return relative, post

    async def find(self, fingerprint: str, record: dict) -> tuple[str, frontmatter.Post] | None:
        """Return one current note; release the catalog before reading its body."""
        async with await self.get_catalog_lock():
            snapshot = await self._update_snapshot()
            relative = self._candidate(snapshot, fingerprint)
        return await self._read_candidate(relative, fingerprint, record)

    async def find_locked(self, fingerprint: str, record: dict) -> tuple[str, frontmatter.Post] | None:
        """Recheck ownership before publication; caller holds fingerprint/catalog.

        Unlike ordinary hits, check every file stamp, including unselected notes
        edited in place while awaiting the model. Identity bytes are read only
        for added or changed files. Only filesystem work holds the catalog.
        """
        snapshot = await self._update_snapshot(recheck_files=True)
        relative = self._candidate(snapshot, fingerprint)
        return await self._read_candidate(relative, fingerprint, record)

    async def record_committed(self, relative: str, post: frontmatter.Post) -> None:
        """Incorporate a real publication, without trusting a guessed directory stamp.

        Caller holds the catalog, after successful atomic publication. Compare
        actual file stamps and reread changed identities instead of absorbing
        concurrent external writes into an optimistic self-write signature.
        Never retain the provided caption body in the rebuildable snapshot.
        """
        parts = Path(relative).relative_to(self.daily_dir).parts
        if len(parts) != 2 or not self._valid_day(parts[0]) or Path(parts[1]).suffix != ".md":
            raise ValueError("Published image note must use a legal daily note path")
        day = parts[0]
        self.invalidate_day(day)
        try:
            snapshot = await self._update_snapshot(recheck_files=True)
            selected = self._candidate(snapshot, post.get("image_fingerprint"))
            state = snapshot.days.get(day)
            metadata = state.notes.get(relative) if state is not None else None
            if selected != relative or metadata != {key: post.get(key) for key in _IDENTITY_KEYS}:
                raise ValueError("Published image note identity changed before its snapshot update")
        except BaseException:
            self.invalidate_day(day)
            raise
