"""Session-owned image sources and caption notes, independent of resource jobs."""

import asyncio
import base64
import binascii
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import aiofiles
import frontmatter
import httpx
from agentscope.message import Msg, TextBlock, URLSource

from ._image_caption import MAX_IMAGE_INPUT_BYTES, caption_image, normalize_image, validate_image
from ._image_note_lookup import ImageNoteLookup
from ._session_io import atomic_write
from ..file_io import refresh_day_index
from ..file_io._file_io import get_path_lock
from ..file_io._path import _check_path_permission, resolve_path
from ..index import normalize_posix_path

_SOURCE_METADATA = "reme_image_sources"
_PREPROCESSING_VERSION = 4
_MAX_NOTE_BYTES = 1024 * 1024
_MAX_SOURCE_CACHE = 256
_MAX_INDEX_CACHE_DAYS = 8
_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
}


def is_image(block) -> bool:
    """Only top-level image DataBlocks are session image evidence."""
    return block.type == "data" and str(getattr(block.source, "media_type", "")).lower().startswith("image/")


class SessionImages:
    """Invocation-scoped orchestration; workspace files own all durable state.

    Caption notes themselves are the reusable description, not a separate hidden
    caption cache. Per-path locks serialize one caption fingerprint across calls.
    """

    def __init__(self, step):
        self.step = step
        self.workspace = step.file_store.workspace_path.resolve()
        self.session_dir = normalize_posix_path(str(step.config_value("session_dir")))
        self.daily_dir = step.config_value("daily_dir")
        self.records: list[dict] = []
        self.note_paths: list[str] = []
        self.dirty_days: set[str] = set()
        self.index_results: list[dict] = []
        self.stage = "source"
        # Invocation-local bounded mappings contain locators, never image bytes
        # or remote URLs (which can carry signatures).
        self._remote_sources: OrderedDict[str, dict] = OrderedDict()
        self._validated_sources: OrderedDict[str, str] = OrderedDict()
        self._index_snapshots: OrderedDict[str, tuple[tuple, str]] = OrderedDict()
        self._notes = ImageNoteLookup(
            self.workspace,
            self.daily_dir,
            resolve=self.path,
            max_note_bytes=_MAX_NOTE_BYTES,
        )

    @property
    def source_modified(self) -> bool:
        """Whether this invocation published an original attachment."""
        return any(record.get("source_modified") for record in self.records)

    @property
    def notes_modified(self) -> bool:
        """Whether this invocation published a caption card."""
        return any(record.get("note_modified") for record in self.records)

    @staticmethod
    def _remember(cache: OrderedDict, key, value, limit: int = _MAX_SOURCE_CACHE) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)

    def path(self, relative: str) -> Path:
        """Apply the same containment and request scope as normal file steps."""
        target, error = resolve_path(self.workspace, relative)
        if error or target is None:
            raise ValueError(error or "Invalid image path")
        if not _check_path_permission(self.workspace, target, self.step.context.get("_allowed_paths")):
            raise ValueError("No permission to access auto-memory image path")
        return target

    @staticmethod
    def _check_size(size: int) -> None:
        if not 0 < size <= MAX_IMAGE_INPUT_BYTES:
            raise ValueError(f"Session image must contain 1..{MAX_IMAGE_INPUT_BYTES} bytes")

    @staticmethod
    async def _read_local(path: Path, limit: int = MAX_IMAGE_INPUT_BYTES) -> bytes:
        """Bound every local read, including previously materialized files."""
        if not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise ValueError("Session image file is missing, empty, or exceeds the input limit")
        async with aiofiles.open(path, "rb") as image_file:
            data = await image_file.read(limit + 1)
        if not 0 < len(data) <= limit:
            raise ValueError("Session image file is empty or exceeds the input limit")
        return data

    async def _published(self, path: Path, content: bytes | str) -> bool:
        """Resolve a cancellation racing with the atomic writer's publication."""
        payload = content.encode("utf-8") if isinstance(content, str) else content
        try:
            return await self._read_local(path, len(payload)) == payload
        except (OSError, ValueError, asyncio.CancelledError):
            return False

    async def _read_source(self, block, saved_source: dict | None = None) -> bytes:
        source = block.source
        if source.type == "base64":
            if len(source.data) > 4 * ((MAX_IMAGE_INPUT_BYTES + 2) // 3):
                raise ValueError("Session image base64 exceeds the input limit")
            try:
                data = base64.b64decode(source.data, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("Invalid session image base64") from exc
        else:
            parsed = urlparse(str(source.url))
            if parsed.scheme == "file":
                if parsed.netloc not in ("", "localhost") or parsed.query or parsed.fragment:
                    raise ValueError("Session image file URL must identify a local workspace file")
                raw_path = url2pathname(parsed.path)
                # Saved relative provenance also works after moving a workspace.
                # A saved block must retain its exact content-addressed identity.
                expected_digest = None
                if saved_source:
                    expected_digest = str(saved_source.get("source_sha256", ""))
                    extension = Path(str(saved_source.get("source_path", ""))).suffix.lstrip(".")
                    canonical = f"{self.session_dir}/images/{expected_digest}.{extension}"
                    if (
                        len(expected_digest) != 64
                        or any(char not in "0123456789abcdef" for char in expected_digest)
                        or extension not in _EXTENSIONS.values()
                        or saved_source.get("source_path") != canonical
                    ):
                        raise ValueError("Invalid saved session image provenance")
                    if not raw_path.endswith("/" + canonical):
                        # Older saved messages used a resolved file URL. Accept
                        # those only when the current safe logical path resolves
                        # to the very same local file; never trust a remote root.
                        if self.path(raw_path) != self.path(canonical):
                            raise ValueError("Invalid saved session image provenance")
                    raw_path = canonical
                target = self.path(raw_path)
                data = await self._read_local(target)
                if expected_digest and hashlib.sha256(data).hexdigest() != expected_digest:
                    raise ValueError("Stored session image no longer matches its saved provenance")
            elif parsed.scheme in ("http", "https"):
                if parsed.username or parsed.password:
                    raise ValueError("Session image URLs cannot contain credentials")
                key = hashlib.sha256(str(source.url).encode()).hexdigest()
                cached = self._remote_sources.get(key)
                if cached:
                    data = await self._read_local(self.path(cached["source_path"]))
                    if hashlib.sha256(data).hexdigest() != cached["source_sha256"]:
                        raise ValueError("Stored session image no longer matches its saved provenance")
                    self._remote_sources.move_to_end(key)
                    return data
                async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=3) as client:
                    async with client.stream("GET", str(source.url)) as response:
                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length:
                            self._check_size(int(content_length))
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > MAX_IMAGE_INPUT_BYTES:
                                raise ValueError("Session image download exceeds the input limit")
                        data = bytes(chunks)
            else:
                raise ValueError("Session image source must use base64, file, HTTP, or HTTPS")
        self._check_size(len(data))
        return data

    async def materialize(self, messages: list[Msg]) -> list[Msg]:
        """Copy images to immutable attachments and retain their message positions."""
        result = []
        for message in messages:
            content = []
            sources = []
            previous_sources = self._saved_sources(message)
            for index, block in enumerate(message.content):
                if not is_image(block):
                    content.append(block)
                    continue
                record = {
                    "message_id": message.id,
                    "block_id": block.id,
                    "block_index": index,
                    "status": "pending",
                    "source_modified": False,
                    "note_modified": False,
                }
                self.records.append(record)
                try:
                    data = await self._read_source(block, previous_sources.get((block.id, index)))
                    digest = hashlib.sha256(data).hexdigest()
                    source_mime = self._validated_sources.get(digest)
                    if source_mime is None:
                        source_mime = await asyncio.to_thread(validate_image, data)
                        self._remember(self._validated_sources, digest, source_mime)
                    else:
                        self._validated_sources.move_to_end(digest)
                    relative = f"{self.session_dir}/images/{digest}.{_EXTENSIONS[source_mime]}"
                    record.update(source_path=relative, source_sha256=digest, media_type=source_mime)
                    target = self.path(relative)
                    lock = await get_path_lock(target)
                    async with lock:
                        if target.exists():
                            if hashlib.sha256(await self._read_local(target)).hexdigest() != digest:
                                raise ValueError("Stored session image has changed; refusing to overwrite it")
                        else:
                            try:
                                await atomic_write(target, data)
                            except BaseException:
                                record["source_modified"] = await self._published(target, data)
                                raise
                            record["source_modified"] = True
                    record.update(source_path=relative, source_sha256=digest, media_type=source_mime, status="stored")
                    if block.source.type == "url" and urlparse(str(block.source.url)).scheme in ("http", "https"):
                        self._remember(
                            self._remote_sources,
                            hashlib.sha256(str(block.source.url).encode()).hexdigest(),
                            {"source_path": relative, "source_sha256": digest},
                        )
                    sources.append(
                        {
                            "block_id": block.id,
                            "block_index": index,
                            "source_path": relative,
                            "source_sha256": digest,
                        },
                    )
                    content.append(
                        block.model_copy(
                            update={
                                "source": URLSource(url=(self.workspace / relative).as_uri(), media_type=source_mime),
                            },
                        ),
                    )
                except asyncio.CancelledError:
                    record.update(status="cancelled", error_type="CancelledError")
                    raise
                except Exception as exc:
                    record.update(status="failed", error_type=type(exc).__name__)
                    raise
            if sources:
                result.append(
                    message.model_copy(
                        update={
                            "content": content,
                            "metadata": {**(message.metadata or {}), _SOURCE_METADATA: sources},
                        },
                    ),
                )
            else:
                result.append(message)
        return result

    @staticmethod
    def _saved_sources(message: Msg) -> dict[tuple[str, int], dict]:
        """Match saved provenance by position as well as ID; IDs need not be unique.

        Older transcripts could remove non-image blocks without adjusting the
        saved index. A unique image ID can recover that position, but only its
        original source path/digest is trusted by ``_read_source``. Multiple
        possible positions or duplicate provenance never silently discard an
        immutable source identity.
        """
        previous = (message.metadata or {}).get(_SOURCE_METADATA, [])
        if not isinstance(previous, list):
            raise ValueError("Invalid saved session image provenance list")
        images_by_id: dict[str, list[int]] = {}
        for index, block in enumerate(message.content):
            if is_image(block):
                images_by_id.setdefault(block.id, []).append(index)
        entries: dict[tuple[str, int], dict] = {}
        counts: dict[str, int] = {}
        for item in previous:
            if not isinstance(item, dict):
                raise ValueError("Invalid saved session image provenance entry")
            block_id, index = item.get("block_id"), item.get("block_index")
            if not isinstance(block_id, str) or type(index) is not int or index < 0:
                raise ValueError("Invalid saved session image provenance position")
            key = block_id, index
            if key in entries:
                raise ValueError("Duplicate saved session image provenance position")
            entries[key] = item
            counts[block_id] = counts.get(block_id, 0) + 1
        matched = {}
        for (block_id, index), item in entries.items():
            positions = images_by_id.get(block_id, [])
            if index not in positions:
                if len(positions) != 1 or counts[block_id] != 1:
                    raise ValueError("Saved session image provenance position is ambiguous or missing")
                index = positions[0]
            matched[block_id, index] = item
        return matched

    def _generation_identity(self) -> dict:
        model = self.step.as_llm
        parameters = getattr(model, "parameters", None)
        return {
            "preprocessing_version": _PREPROCESSING_VERSION,
            "model_type": f"{type(model).__module__}.{type(model).__name__}",
            "model": str(getattr(model, "model", "")),
            "endpoint": str(getattr(getattr(model, "credential", None), "base_url", "")),
            "parameters": parameters.model_dump(mode="json") if hasattr(parameters, "model_dump") else parameters,
            "extra_body": getattr(model, "extra_body", None),
            "prompt": self.step.get_prompt("image_caption_prompt"),
        }

    async def _find_note(self, fingerprint: str, record: dict) -> tuple[str, frontmatter.Post] | None:
        return await self._notes.find(fingerprint, record)

    async def _remember_note(self, relative: str, *, created: bool) -> None:
        """Record a committed card before any later index/agent operation fails."""
        if relative not in self.note_paths:
            self.note_paths.append(relative)
        day = Path(relative).parent.name
        if created:
            self.dirty_days.add(day)
            return
        if day in self.dirty_days:
            return
        index = self.path(f"{self.daily_dir}/{day}.md")
        if not index.is_file():
            self.dirty_days.add(day)
            return
        stat = index.stat()
        signature = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_size)
        cached = self._index_snapshots.get(day)
        if cached is None or cached[0] != signature:
            try:
                body = (await self._read_local(index, _MAX_NOTE_BYTES)).decode("utf-8")
            except (OSError, ValueError, UnicodeError):
                self.dirty_days.add(day)
                return
            cached = signature, body
            self._remember(self._index_snapshots, day, cached, _MAX_INDEX_CACHE_DAYS)
        if stat.st_mtime_ns < self.path(relative).stat().st_mtime_ns or f"[[{relative}]]" not in cached[1]:
            self.dirty_days.add(day)

    async def _image_note(self, record: dict, day: str, identity: dict) -> tuple[str, str]:
        fingerprint = hashlib.sha256(
            json.dumps(
                {**identity, "source_sha256": record["source_sha256"]},
                sort_keys=True,
                ensure_ascii=False,
            ).encode(),
        ).hexdigest()
        record["image_fingerprint"] = fingerprint
        lock_path = self.path(f"{self.session_dir}/images/caption-{fingerprint}.lock")
        lock = await get_path_lock(lock_path)
        async with lock:
            # Recheck the immutable source even on a caption cache hit. Reading
            # another image/model can have yielded since materialization.
            source_path = self.path(record["source_path"])
            data = await self._read_local(source_path)
            if hashlib.sha256(data).hexdigest() != record["source_sha256"]:
                raise ValueError("Session image changed before captioning")
            found = await self._find_note(fingerprint, record)
            if found:
                relative, post = found
                record.update(note_path=relative, cache_hit=True, status="ready")
                await self._remember_note(relative, created=False)
                return relative, post.content
            target_rel = f"{self.daily_dir}/{day}/session-image-{fingerprint}.md"
            target = self.path(target_rel)
            payload, mime, _ = await asyncio.to_thread(normalize_image, data)
            caption = await caption_image(self.step.as_llm, payload, mime, identity["prompt"])
            body = f"![[{record['source_path']}]]\n\n## Caption\n\n{caption.caption}\n"
            metadata = {
                "kind": "session_image",
                "source_resource": f"[[{record['source_path']}]]",
                "source_sha256": record["source_sha256"],
                "media_type": record["media_type"],
                "image_fingerprint": fingerprint,
                "caption_model": identity["model"],
                "caption_prompt_sha256": hashlib.sha256(identity["prompt"].encode()).hexdigest(),
                "image_preprocessing_version": _PREPROCESSING_VERSION,
            }
            # Hold the target's normal write lock through create, so an existing
            # user document is never overwritten. The short catalog lock keeps
            # concurrent image writers out of metadata scans, never out of LLM calls.
            async with await self._notes.get_catalog_lock():
                # A normal file write or restore can have supplied a user-owned
                # caption while the model was running. Recheck under the catalog
                # lock without recursively acquiring it or publishing a second
                # owner. The selected card's current body takes precedence.
                found = await self._notes.find_locked(fingerprint, record)
                if found:
                    relative, post = found
                    record.update(note_path=relative, cache_hit=True, status="ready")
                    await self._remember_note(relative, created=False)
                    return relative, post.content
                target = self.path(target_rel)
                target_lock = await get_path_lock(target)
                async with target_lock:
                    if target.exists():
                        raise ValueError("Image note target already exists")
                    post = frontmatter.Post(body, name=caption.name, description=caption.description, **metadata)
                    rendered = frontmatter.dumps(post) + "\n"
                    try:
                        await atomic_write(target, rendered)
                    except BaseException:
                        self._notes.invalidate_day(day)
                        if await self._published(target, rendered):
                            record.update(note_path=target_rel, cache_hit=False, status="ready", note_modified=True)
                            await self._remember_note(target_rel, created=True)
                        raise
                record.update(note_path=target_rel, cache_hit=False, status="ready", note_modified=True)
                await self._remember_note(target_rel, created=True)
                try:
                    await self._notes.record_committed(target_rel, post)
                except BaseException:
                    self._notes.invalidate_day(day)
                    raise
            return target_rel, body

    async def _refresh_indexes(self, *, suppress_errors: bool = False) -> None:
        """Refresh dirty days, preserving the original failure on partial work."""
        self.step.context.response.metadata["auto_memory_images"]["indexes"] = self.index_results
        failed = False
        for day in sorted(self.dirty_days):
            result = {"date": day, "path": f"{self.daily_dir}/{day}.md"}
            try:
                async with await self._notes.get_catalog_lock():
                    index_path = self.path(result["path"])
                    index_lock = await get_path_lock(index_path)
                    async with index_lock:
                        index = await refresh_day_index(self.step.file_store, day, self.daily_dir)
                        if index.get("error"):
                            raise RuntimeError("Session image day index refresh failed")
                result["changed"] = bool(index.get("changed"))
            except Exception as exc:
                result["error_type"] = type(exc).__name__
                self.index_results.append(result)
                failed = True
            else:
                self.index_results.append(result)
        if failed and not suppress_errors:
            self.stage = "index"
            raise RuntimeError("Session image day index refresh failed")

    async def enrich(self, messages: list[Msg], day: str) -> list[Msg]:
        """Inject descriptions only into the memory agent's text-message copy."""
        self.stage = "caption"
        identity = self._generation_identity()
        self.step.context.response.metadata["auto_memory_images"].update(
            caption_model=identity["model"],
            caption_prompt_sha256=hashlib.sha256(identity["prompt"].encode()).hexdigest(),
        )
        records = iter(self.records)
        enriched = []
        try:
            for message in messages:
                content = []
                for block in message.content:
                    if not is_image(block):
                        content.append(block)
                        continue
                    record = next(records)
                    try:
                        relative, body = await self._image_note(record, day, identity)
                    except asyncio.CancelledError:
                        if record["status"] != "ready":
                            record.update(status="cancelled", error_type="CancelledError")
                        raise
                    except Exception as exc:
                        if record["status"] != "ready":
                            record.update(status="failed", error_type=type(exc).__name__)
                        raise
                    # JSON encoding keeps labels on one line and explicitly
                    # marks them as user-supplied locators, not visual facts.
                    label = json.dumps(block.name or block.id, ensure_ascii=False)
                    content.append(
                        TextBlock(
                            text=(
                                f"[Image description; supplied label: {label}]\n" f"Image note: [[{relative}]]\n{body}"
                            ),
                        ),
                    )
                enriched.append(message.model_copy(update={"content": content}))
        except BaseException:
            await self._refresh_indexes(suppress_errors=True)
            raise
        await self._refresh_indexes()
        return enriched
