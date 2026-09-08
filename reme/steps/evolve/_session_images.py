"""Temporary image-to-text input for auto-memory; never rewrites source messages."""

import base64
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

import aiofiles
import frontmatter
import httpx
from agentscope.message import Msg, TextBlock

from ._image_caption import (
    DEFAULT_MAX_IMAGE_INPUT_BYTES,
    build_image_request_payload,
    generate_image_caption,
    resolve_vision_model,
)
from ..file_io._file_io import _decode_known_file
from ..file_io._path import _check_path_permission, resolve_path
from ...components.prompt_handler import PromptHandler

_IMAGE_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


def _workspace_path(step, path: str, *, check_permission: bool = True) -> Path:
    workspace = step.file_store.workspace_path.resolve()
    target, error = resolve_path(workspace, path)
    if error or target is None:
        raise ValueError("Image path must stay inside the workspace")
    if check_permission and not _check_path_permission(workspace, target, step.context.get("_allowed_paths")):
        raise PermissionError("Image path is outside the allowed paths")
    return target


async def _read_bytes(path: Path, limit: int) -> bytes:
    async with aiofiles.open(path, "rb") as stream:
        data = await stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Image or caption note exceeds the byte limit")
    return data


async def _image_bytes(step, source) -> bytes:
    limit = DEFAULT_MAX_IMAGE_INPUT_BYTES
    if source.type == "base64":
        if len(source.data) > 4 * ((limit + 2) // 3):
            raise ValueError("Image exceeds the byte limit")
        data = base64.b64decode(source.data, validate=True)
    else:
        url = urlsplit(str(source.url))
        if url.scheme == "file" and url.netloc in ("", "localhost") and not url.query and not url.fragment:
            data = await _read_bytes(_workspace_path(step, unquote(url.path)), limit)
        elif url.scheme in ("http", "https"):
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, max_redirects=3) as client:
                async with client.stream("GET", str(source.url)) as response:
                    response.raise_for_status()
                    buffer = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(buffer) + len(chunk) > limit:
                            raise ValueError("Image exceeds the byte limit")
                        buffer.extend(chunk)
                    data = bytes(buffer)
        else:
            raise ValueError("Image source must be Base64, HTTP(S), or a workspace file URI")
    if not data or len(data) > limit:
        raise ValueError("Image is empty or exceeds the byte limit")
    return data


async def _register_resource(step, day: str, digest: str, data: bytes, source_mime: str) -> str:
    """Publish original bytes without overwriting an existing user-owned file."""
    suffix = _IMAGE_SUFFIXES.get(source_mime)
    if suffix is None:
        raise ValueError("Decoded image format is not supported by auto_resource")
    logical_root = Path(str(step.config_value("resource_dir")))
    root = _workspace_path(step, str(logical_root), check_permission=False)
    if logical_root.is_absolute():
        for workspace in (step.file_store.workspace_path.absolute(), step.file_store.workspace_path.resolve()):
            try:
                logical_root = logical_root.relative_to(workspace)
                break
            except ValueError:
                continue
        else:
            raise ValueError("Resource directory must stay inside the workspace")
    logical = logical_root / day / "_session_images" / f"{digest}{suffix}"
    target = _workspace_path(step, str(logical))
    if not target.is_relative_to(root):
        raise ValueError("Session image must stay inside the resource directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiofiles.open(target, "xb") as stream:
            await stream.write(data)
    except FileExistsError:
        if await _read_bytes(target, DEFAULT_MAX_IMAGE_INPUT_BYTES) != data:
            raise ValueError("Existing session image differs from its content hash") from None
    return logical.as_posix()


async def _resource_captions(step, entries: dict, day: str, model) -> None:
    """Reuse existing same-day cards; send all missing cards through one resource job."""
    response = await step.run_job("daily_list", date=day)
    if not response.success:
        raise RuntimeError("Cannot list image resource notes")
    owners: dict[str, list[str]] = {}
    for note in response.metadata.get("notes") or []:
        owners.setdefault(str(note.get("source_resource", "")), []).append(str(note.get("path", "")))
    missing = []
    for entry in entries.values():
        source = f"[[{entry['resource_path']}]]"
        paths = owners.get(source, [])
        if len(paths) > 1:
            raise ValueError("Multiple image notes own the same resource")
        if paths:
            entry["note_path"] = paths[0]
        else:
            missing.append({"path": entry["resource_path"], "change": "added"})
    if missing:
        daily = Path(str(step.config_value("daily_dir")))
        _workspace_path(step, str(daily / day))
        _workspace_path(step, str(daily / f"{day}.md"))
        response = await step.run_job(
            "auto_resource",
            changes=missing,
            as_llm=model,
            _allowed_paths=step.context.get("_allowed_paths"),
        )
        if not response.success:
            raise RuntimeError("auto_resource failed to create image notes")
        results = {item["path"]: item for item in response.metadata.get("results") or []}
        for entry in entries.values():
            if "note_path" in entry:
                continue
            result = results.get(entry["resource_path"], {})
            metadata = result.get("metadata") or {}
            if not result.get("success") or metadata.get("action") not in ("added", "modified"):
                raise RuntimeError("auto_resource did not produce an image note")
            entry["note_path"] = metadata.get("path", "")
    for entry in entries.values():
        path = _workspace_path(step, entry["note_path"])
        text, _ = _decode_known_file(await _read_bytes(path, 1024 * 1024), path.suffix)
        post = frontmatter.loads(text)
        if post.get("kind") != "image" or post.get("source_resource") != f"[[{entry['resource_path']}]]":
            raise ValueError("Image note has an unexpected source or kind")
        if not post.content.strip():
            raise ValueError("Image note has no caption content")
        entry["caption"] = post.content.strip()


def _image_text(entry: dict) -> str:
    lines = ["[Image]"]
    if "note_path" in entry:
        lines.extend(
            [
                f"Image note: [[{entry['note_path']}]]",
                f"Image resource: [[{entry['resource_path']}]]",
            ],
        )
    lines.extend(["Caption (model-generated):", entry["caption"], "[/Image]"])
    return "\n".join(lines)


async def prepare_image_messages(step, messages: list[Msg], day: str, mode: str) -> list[Msg]:
    """Replace top-level image blocks in copies, retaining message and block order.

    Deduplication is invocation-local and content-based, not based on block IDs.
    Resource files/cards may remain if a later operation fails; no rollback or
    source-transcript provenance is introduced here.
    """
    if mode not in ("resource", "caption-only"):
        raise ValueError("image_mode must be 'resource' or 'caption-only'")
    images = [
        (message_index, block_index, block.source)
        for message_index, message in enumerate(messages)
        for block_index, block in enumerate(message.content)
        if block.type == "data" and block.source.media_type.startswith("image/")
    ]
    if not images:
        return messages
    model = resolve_vision_model(step)
    if model is None:
        raise ValueError("Image captioning requires a vision-capable model")
    entries: dict[str, dict] = {}
    positions = {}
    stage = "source"
    try:
        prompt = PromptHandler(language=step.language).load_prompt_by_file(
            Path(__file__).with_name("auto_image_resource.yaml"),
        )
        for message_index, block_index, source in images:
            data = await _image_bytes(step, source)
            digest = hashlib.sha256(data).hexdigest()
            positions[(message_index, block_index)] = digest
            if digest in entries:
                continue
            payload = build_image_request_payload(data, "")
            entry = {}
            if mode == "resource":
                entry["resource_path"] = await _register_resource(step, day, digest, data, payload["source_mime"])
            else:
                stage = "caption"
                filename = f"session-image-{digest}{_IMAGE_SUFFIXES.get(payload['source_mime'], '')}"
                parsed = await generate_image_caption(
                    model,
                    payload,
                    prompt.prompt_format(
                        "user_message",
                        file_path=filename,
                        filename=filename,
                        stem="session-image",
                        date=day,
                    ),
                    logger=step.logger,
                    name=step.name,
                )
                entry["caption"] = parsed["caption"]
                stage = "source"
            entries[digest] = entry
        if mode == "resource":
            stage = "resource"
            await _resource_captions(step, entries, day, model)
    except Exception as exc:  # pylint: disable=broad-except
        # URLs may contain credentials; do not expose decoder/provider exceptions.
        raise RuntimeError(f"Auto-memory image {stage} failed ({type(exc).__name__})") from None
    prepared = []
    for message_index, message in enumerate(messages):
        content = [
            (
                TextBlock(text=_image_text(entries[positions[(message_index, block_index)]]))
                if (message_index, block_index) in positions
                else block
            )
            for block_index, block in enumerate(message.content)
        ]
        prepared.append(message.model_copy(update={"content": content}))
    step.context.response.metadata["auto_memory_images"] = {
        "mode": mode,
        "image_count": len(images),
        "unique_images": len(entries),
        "resources": [entry["resource_path"] for entry in entries.values() if "resource_path" in entry],
        "notes": [entry["note_path"] for entry in entries.values() if "note_path" in entry],
    }
    return prepared
