"""Session-owned image sources and caption notes, independent of resource jobs."""

import asyncio
import base64
import binascii
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import aiofiles
import frontmatter
import httpx
from agentscope.message import Msg, TextBlock, URLSource

from ._image_caption import MAX_IMAGE_INPUT_BYTES, caption_image, normalize_image
from ..file_io import refresh_day_index
from ..file_io._file_io import get_path_lock, write_file_safe
from ..file_io._path import _check_path_permission, resolve_path
from ..index import normalize_posix_path

_SOURCE_METADATA = "reme_image_sources"
_PREPROCESSING_VERSION = 2
_MAX_NOTE_BYTES = 1024 * 1024
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
                # Only apply it to the exact content-addressed attachment name.
                expected_digest = None
                if saved_source and Path(raw_path).name == Path(saved_source.get("source_path", "")).name:
                    expected_digest = str(saved_source.get("source_sha256", ""))
                    extension = Path(raw_path).suffix.lstrip(".")
                    canonical = f"{self.session_dir}/images/{expected_digest}.{extension}"
                    if (
                        len(expected_digest) != 64
                        or any(char not in "0123456789abcdef" for char in expected_digest)
                        or extension not in _EXTENSIONS.values()
                        or saved_source.get("source_path") != canonical
                        or not raw_path.endswith("/" + canonical)
                    ):
                        raise ValueError("Invalid saved session image provenance")
                    raw_path = canonical
                target = self.path(raw_path)
                data = await self._read_local(target)
                if expected_digest and hashlib.sha256(data).hexdigest() != expected_digest:
                    raise ValueError("Stored session image no longer matches its saved provenance")
            elif parsed.scheme in ("http", "https"):
                if parsed.username or parsed.password:
                    raise ValueError("Session image URLs cannot contain credentials")
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
            previous = (message.metadata or {}).get(_SOURCE_METADATA, [])
            previous_by_id = (
                {item.get("block_id"): item for item in previous if isinstance(item, dict)}
                if isinstance(previous, list)
                else {}
            )
            for index, block in enumerate(message.content):
                if not is_image(block):
                    content.append(block)
                    continue
                record = {"message_id": message.id, "block_id": block.id, "block_index": index, "status": "pending"}
                self.records.append(record)
                try:
                    data = await self._read_source(block, previous_by_id.get(block.id))
                    _, _, source_mime = await asyncio.to_thread(normalize_image, data)
                    digest = hashlib.sha256(data).hexdigest()
                    relative = f"{self.session_dir}/images/{digest}.{_EXTENSIONS[source_mime]}"
                    target = self.path(relative)
                    lock = await get_path_lock(target)
                    async with lock:
                        if target.exists():
                            if hashlib.sha256(await self._read_local(target)).hexdigest() != digest:
                                raise ValueError("Stored session image has changed; refusing to overwrite it")
                        else:
                            await write_file_safe(target, data)
                    record.update(source_path=relative, source_sha256=digest, media_type=source_mime, status="stored")
                    sources.append(
                        {
                            "block_id": block.id,
                            "block_index": index,
                            "source_path": relative,
                            "source_sha256": digest,
                        },
                    )
                    content.append(
                        block.model_copy(update={"source": URLSource(url=target.as_uri(), media_type=source_mime)}),
                    )
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

    async def _find_note(self, fingerprint: str) -> tuple[str, frontmatter.Post] | None:
        daily = self.path(self.daily_dir)
        # A note's filename is stable; its user-editable body is the caption
        # source of truth. No additional durable caption store is required.
        for path in sorted(daily.glob(f"*/session-image-{fingerprint}.md")):
            relative = path.relative_to(self.workspace).as_posix()
            path = self.path(relative)
            lock = await get_path_lock(path)
            async with lock:
                post = frontmatter.loads((await self._read_local(path, _MAX_NOTE_BYTES)).decode("utf-8"))
            if post.get("kind") != "session_image" or post.get("image_fingerprint") != fingerprint:
                raise ValueError("Session image note path is occupied by another document")
            if not post.content.strip():
                raise ValueError("Stored image note is empty; restore its caption before reusing it")
            return relative, post
        return None

    async def _image_note(self, record: dict, day: str, identity: dict) -> tuple[str, str]:
        fingerprint = hashlib.sha256(
            json.dumps(
                {**identity, "source_sha256": record["source_sha256"]},
                sort_keys=True,
                ensure_ascii=False,
            ).encode(),
        ).hexdigest()
        lock_path = self.path(f"{self.session_dir}/images/caption-{fingerprint}.lock")
        lock = await get_path_lock(lock_path)
        async with lock:
            found = await self._find_note(fingerprint)
            if found:
                relative, post = found
                record.update(note_path=relative, cache_hit=True, status="ready")
                return relative, post.content
            target_rel = f"{self.daily_dir}/{day}/session-image-{fingerprint}.md"
            target = self.path(target_rel)
            source_path = self.path(record["source_path"])
            data = await self._read_local(source_path)
            if hashlib.sha256(data).hexdigest() != record["source_sha256"]:
                raise ValueError("Session image changed before captioning")
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
            # user document is never overwritten. Use the shared file writer.
            target_lock = await get_path_lock(target)
            async with target_lock:
                if target.exists():
                    raise ValueError("Image note target already exists")
                post = frontmatter.Post(body, name=caption.name, description=caption.description, **metadata)
                await write_file_safe(target, frontmatter.dumps(post) + "\n")
            record.update(note_path=target_rel, cache_hit=False, status="ready")
            return target_rel, body

    async def enrich(self, messages: list[Msg], day: str) -> list[Msg]:
        """Inject descriptions only into the memory agent's text-message copy."""
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
                    except Exception as exc:
                        record.update(status="failed", error_type=type(exc).__name__)
                        raise
                    if relative not in self.note_paths:
                        self.note_paths.append(relative)
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
        finally:
            # This also updates day pages for successful cards when another image fails
            # or the later session-memory agent decides there is nothing to write.
            for note_day in sorted({Path(path).parent.name for path in self.note_paths}):
                index_path = self.path(f"{self.daily_dir}/{note_day}.md")
                index_lock = await get_path_lock(index_path)
                async with index_lock:
                    index = await refresh_day_index(self.step.file_store, note_day, self.daily_dir)
                    if index.get("error"):
                        raise RuntimeError(index["error"])
        return enriched
