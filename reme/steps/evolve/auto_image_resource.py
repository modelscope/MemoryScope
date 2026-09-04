"""Image resource processor for the unified auto-resource router."""

import base64
import io
import json
import re
import warnings
from pathlib import Path, PurePosixPath

import aiofiles
from agentscope.message import Base64Source, DataBlock, TextBlock, UserMsg
from agentscope.model import ChatModelBase
from pydantic import BaseModel, Field

from ..file_io._path import IMAGE_SUFFIXES
from .base_auto_resource import _SOURCE_RESOURCE_KEY, _sanitize_note_name, BaseAutoResourceStep
from ...components import R
from ...enumeration import ComponentEnum

DEFAULT_MAX_IMAGE_INPUT_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_REQUEST_DIMENSION = 2048
_JPEG_QUALITY = 85
# Decoded formats outside this set are re-encoded to provider-friendly
# PNG/JPEG for VLM requests; the stored resource file is never modified.
_PASSTHROUGH_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
_HEIF_BRANDS = frozenset(
    {b"heic", b"heif", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"hevm", b"hevs", b"mif1", b"msf1"},
)
_MAX_FTYP_SCAN_BYTES = 4096
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class _CaptionOutput(BaseModel):
    """Structured caption contract enforced on the vision model."""

    name: str = Field(
        description="short kebab-case topic stem based on visible content; filename is only a weak naming hint",
    )
    description: str = Field(description="one-sentence summary of visible image content that stands on its own")
    caption: str = Field(
        description="complete description / verbatim transcription of meaningful content visible in the image",
    )


def _load_pillow():
    """Load the core image dependency only when image processing runs."""
    try:
        from PIL import Image, ImageOps  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("Image captioning requires Pillow; install reme-ai[core]") from exc
    return Image, ImageOps


def _looks_like_heif(data: bytes) -> bool:
    """Return whether an ISO-BMFF header declares a HEIC/HEIF brand."""
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False
    box_size = int.from_bytes(data[:4], "big")
    if box_size < 12:
        return False
    end = min(box_size, len(data), _MAX_FTYP_SCAN_BYTES)
    if data[8:12] in _HEIF_BRANDS:
        return True
    return any(data[index : index + 4] in _HEIF_BRANDS for index in range(16, end - 3, 4))


def _register_heif_opener() -> None:
    """Load and register HEIC support only for bytes that declare HEIF."""
    try:
        from pillow_heif import register_heif_opener  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("HEIC image captioning requires pillow-heif; install reme-ai[image-heif]") from exc
    try:
        register_heif_opener()
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Failed to initialize HEIC image support: {exc}") from exc


def _normalize_image_bytes(
    data: bytes,
    suffix: str,
    *,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> tuple[bytes | None, str, str]:
    """Validate and optionally normalize image bytes for a VLM request.

    The returned tuple is ``(normalized_bytes, request_mime, source_mime)``.
    ``normalized_bytes`` is ``None`` only when the original bytes can be sent
    unchanged. MIME values come from the decoded image rather than its suffix.
    Missing dependencies, unsafe pixel counts, and decode/convert failures are
    explicit. The stored resource file is never modified.
    """
    try:
        pixel_limit = int(max_image_pixels)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"max_image_pixels must be a positive integer: {max_image_pixels!r}") from exc
    if pixel_limit <= 0:
        raise ValueError(f"max_image_pixels must be a positive integer: {max_image_pixels!r}")

    image_module, image_ops = _load_pillow()
    if _looks_like_heif(data):
        _register_heif_opener()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", image_module.DecompressionBombWarning)
            image = image_module.open(io.BytesIO(data))
    except (image_module.DecompressionBombWarning, image_module.DecompressionBombError) as exc:
        raise RuntimeError(
            f"Image rejected by Pillow decompression-bomb protection ({suffix or 'unknown suffix'})",
        ) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Failed to decode image ({suffix or 'unknown suffix'}): {exc}") from exc

    with image:
        width, height = image.size
        pixel_count = width * height
        if pixel_count > pixel_limit:
            raise RuntimeError(
                f"Image exceeds max_image_pixels before decode: " f"{width}x{height}={pixel_count} > {pixel_limit}",
            )

        source_mime = str(image.get_format_mimetype() or "").strip().lower()
        if not source_mime.startswith("image/"):
            raise RuntimeError(
                f"Cannot determine decoded image MIME type ({suffix or 'unknown suffix'}, format={image.format!r})",
            )

        needs_resize = width > MAX_IMAGE_REQUEST_DIMENSION or height > MAX_IMAGE_REQUEST_DIMENSION
        if source_mime == "image/jpeg" and needs_resize:
            max_dimension = max(width, height)
            decoder_size = (
                max(1, (width * MAX_IMAGE_REQUEST_DIMENSION + max_dimension - 1) // max_dimension),
                max(1, (height * MAX_IMAGE_REQUEST_DIMENSION + max_dimension - 1) // max_dimension),
            )
            try:
                # JPEG supports power-of-two decoder scaling. ``draft`` picks
                # the smallest decoded frame that still covers decoder_size,
                # reducing peak memory before the final LANCZOS thumbnail.
                image.draft(None, decoder_size)
            except Exception as exc:  # pylint: disable=broad-except
                raise RuntimeError(f"Failed to prepare JPEG decoder downsampling ({width}x{height}): {exc}") from exc

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", image_module.DecompressionBombWarning)
                image.load()
            orientation = int(image.getexif().get(274, 1) or 1)
            image_ops.exif_transpose(image, in_place=True)
        except (image_module.DecompressionBombWarning, image_module.DecompressionBombError) as exc:
            raise RuntimeError(
                f"Image rejected by Pillow decompression-bomb protection ({suffix or 'unknown suffix'})",
            ) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to decode image ({suffix or 'unknown suffix'}): {exc}") from exc

        needs_convert = source_mime not in _PASSTHROUGH_IMAGE_MIMES
        needs_orientation = orientation in range(2, 9)
        if not needs_resize and not needs_convert and not needs_orientation:
            return None, source_mime, source_mime
        try:
            if needs_resize:
                # Resize the decoded source before color conversion so large
                # non-JPEG images do not require a second full-size frame.
                # Pillow 10 cannot apply LANCZOS directly to 16-bit integer
                # modes; NEAREST keeps that path bounded without a full-size
                # RGB conversion first.
                resize_filter = image_module.Resampling.LANCZOS
                if image.mode.startswith("I;16"):
                    resize_filter = image_module.Resampling.NEAREST
                image.thumbnail((MAX_IMAGE_REQUEST_DIMENSION, MAX_IMAGE_REQUEST_DIMENSION), resize_filter)
            has_alpha = image.mode in ("RGBA", "LA", "P")
            frame = image.convert("RGBA" if has_alpha else "RGB")
            try:
                buffer = io.BytesIO()
                if frame.mode == "RGBA":
                    frame.save(buffer, format="PNG")
                    return buffer.getvalue(), "image/png", source_mime
                frame.save(buffer, format="JPEG", quality=_JPEG_QUALITY)
                return buffer.getvalue(), "image/jpeg", source_mime
            finally:
                frame.close()
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to convert/resize image ({suffix or 'unknown suffix'}): {exc}") from exc


def _build_image_request_payload(
    data: bytes,
    suffix: str,
    *,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> dict:
    """Return ``{"data_b64", "mime", "source_mime", "converted"}`` for a VLM request.

    ``mime`` is the format actually sent (after in-memory downscale/re-encode);
    ``source_mime`` is the decoded format of the stored resource file and is
    what notes record. Both are based on actual bytes, not the filename suffix.
    """
    normalized_bytes, mime, source_mime = _normalize_image_bytes(
        data,
        suffix,
        max_image_pixels=max_image_pixels,
    )
    request_bytes = data if normalized_bytes is None else normalized_bytes
    return {
        "data_b64": base64.b64encode(request_bytes).decode("ascii"),
        "mime": mime,
        "source_mime": source_mime,
        "converted": normalized_bytes is not None,
    }


async def _response_text(result) -> str:
    """Extract text blocks from a streaming or non-streaming ChatResponse."""
    if hasattr(type(result), "__aiter__"):
        last = None
        async for chunk in result:
            last = chunk
        result = last
    if result is None:
        return ""
    parts: list[str] = []
    for block in result.content or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        elif getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "") or ""))
    return "".join(parts).strip()


def _normalize_caption_fields(parsed: dict) -> dict:
    """Normalize parsed caption fields, cross-filling a missing ``caption``
    from a present ``description`` so raw JSON never reaches the note body."""
    caption = str(parsed.get("caption") or "").strip()
    description = str(parsed.get("description") or "").strip()
    if not caption and description:
        caption = description
    return {
        "name": str(parsed.get("name") or "").strip(),
        "description": description,
        "caption": caption,
    }


def _parse_caption_json(text: str) -> dict:
    """Parse a plain-call caption response leniently.

    Used as the fallback when the schema-forced structured call fails: fenced
    JSON and embedded ``{...}`` slices are tried before degrading the whole
    response text to the caption.
    """
    cleaned = text.strip()
    fence = _JSON_FENCE_RE.match(cleaned)
    if fence:
        cleaned = fence.group(1)
    parsed_json = False
    for candidate in (cleaned, cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        parsed_json = True
        if isinstance(parsed, dict):
            normalized = _normalize_caption_fields(parsed)
            if normalized["caption"] or normalized["description"]:
                return normalized
    if parsed_json:
        return {"name": "", "description": "", "caption": ""}
    return {"name": "", "description": "", "caption": cleaned.strip()}


@R.register("auto_image_resource_step")
class AutoImageResourceStep(BaseAutoResourceStep):
    """Interpret image resource files into daily notes via a direct VLM call.

    Unlike text resources (agent + file tools), the image interpretation is a
    single vision-model call. Images larger than the request budget or in
    provider-unfriendly formats are downscaled/re-encoded in memory for the
    request only; files under ``resource/`` are never modified. Note lookup,
    renaming, deletion linkage, and day-index refresh reuse the shared
    BaseAutoResourceStep lifecycle; only the interpretation differs.
    """

    resource_suffixes = IMAGE_SUFFIXES
    router_inherit_keys = BaseAutoResourceStep.router_inherit_keys | frozenset(
        {"as_llm", "max_image_bytes", "max_image_pixels"},
    )

    def _max_image_bytes(self) -> int:
        """Return the image read limit from Step or Job context."""
        value = self.kwargs.get("max_image_bytes")
        if value is None and self.context is not None:
            value = self.context.get("max_image_bytes")
        return int(value) if value is not None else DEFAULT_MAX_IMAGE_INPUT_BYTES

    def _max_image_pixels(self) -> int:
        """Return the deployment-controlled pre-decode pixel limit."""
        value = self.kwargs.get("max_image_pixels", DEFAULT_MAX_IMAGE_PIXELS)
        try:
            limit = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_image_pixels must be a positive integer: {value!r}") from exc
        if limit <= 0:
            raise ValueError(f"max_image_pixels must be a positive integer: {value!r}")
        return limit

    def _vision_model(self) -> ChatModelBase | None:
        """Resolve explicit ``as_llm`` through Ref, otherwise prefer vision/default."""
        context_model = self.context.get("as_llm") if self.context is not None else None
        if "as_llm" in self.kwargs or isinstance(context_model, ChatModelBase):
            return self.as_llm
        if self.app_context is None:
            return None
        models = self.app_context.components.get(ComponentEnum.AS_LLM, {})
        for name in ("vision", "default"):
            if name in models:
                self.kwargs["as_llm"] = name
                return self.as_llm
        return None

    async def _caption_with_retry(self, model: ChatModelBase, user_message: UserMsg) -> dict:
        """Return the caption fields from the vision model.

        Primary path is the schema-forced structured output (the SDK enforces
        the ``name``/``description``/``caption`` contract and retries transport
        errors). When that fails or yields no usable field, retry once with a
        plain call parsed leniently.
        """
        try:
            structured = await model.generate_structured_output(
                messages=[user_message],
                structured_model=_CaptionOutput,
            )
            content = structured.content if isinstance(structured.content, dict) else {}
            normalized = _normalize_caption_fields(dict(content))
            if normalized["caption"] or normalized["description"]:
                self.logger.info(f"[{self.name}] structured caption ok name={normalized['name']}")
                return normalized
            self.logger.warning(f"[{self.name}] structured caption empty; retrying with a plain call")
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning(f"[{self.name}] structured caption failed ({exc}); retrying with a plain call")
        result = await model([user_message])
        parsed = _parse_caption_json(await _response_text(result))
        if not parsed["caption"] and not parsed["description"]:
            raise RuntimeError("Vision model returned no usable caption")
        return parsed

    async def _read_image(self, file_path: str, source_path: Path) -> dict | None:
        """Read the image file and build the VLM request payload.

        Returns ``None`` when the change must be skipped (stat failure or
        oversized file); the skip outcome is already recorded on the response.
        """
        max_image_bytes = self._max_image_bytes()
        try:
            size_bytes = source_path.stat().st_size
        except OSError as exc:
            self.context.response.success = False
            self.context.response.answer = f"Failed to inspect resource file: {file_path}: {exc}"
            self.context.response.metadata.update(
                {
                    "path": file_path,
                    "action": "failed",
                    "error": str(exc),
                    "modified": False,
                },
            )
            self.logger.warning(f"[{self.name}] resource stat failed file_path={file_path} error={exc}")
            return None
        if size_bytes > max_image_bytes:
            self._record_oversized_image(file_path, size_bytes, max_image_bytes)
            return None

        self.logger.info(f"[{self.name}] read image start file_path={file_path}")
        async with aiofiles.open(source_path, "rb") as f:
            data = await f.read(max_image_bytes + 1)
        if len(data) > max_image_bytes:
            self._record_oversized_image(file_path, len(data), max_image_bytes)
            return None
        payload = _build_image_request_payload(
            data,
            Path(file_path).suffix.lower(),
            max_image_pixels=self._max_image_pixels(),
        )
        self.logger.info(
            f"[{self.name}] read image done file_path={file_path} size_bytes={size_bytes} "
            f"mime={payload['mime']} source_mime={payload['source_mime']} converted={payload['converted']}",
        )
        return payload

    def _record_oversized_image(self, file_path: str, size_bytes: int, max_image_bytes: int) -> None:
        """Record a stable skip response for an image over the compressed-byte limit."""
        assert self.context is not None
        self.context.response.success = True
        self.context.response.answer = (
            f"Skipped oversized image resource file: {file_path} ({size_bytes} > {max_image_bytes} bytes)"
        )
        self.context.response.metadata.update(
            {
                "path": file_path,
                "action": "skipped",
                "reason": "file_too_large",
                "oversized": True,
                "size_bytes": size_bytes,
                "max_image_bytes": max_image_bytes,
                "modified": False,
            },
        )
        self.logger.warning(
            f"[{self.name}] skip oversized image resource file_path={file_path} "
            f"size_bytes={size_bytes} max_image_bytes={max_image_bytes}",
        )

    async def _handle_upsert(
        self,
        file_path: str,
        date_str: str,
        note_stem: str,
        added: bool,
        source_path: Path,
    ) -> None:
        """Caption the image and write/refresh its note (image counterpart of the text upsert)."""
        note_state = await self._prepare_resource_note(date_str, file_path, note_stem)
        note_path = note_state.path
        self.logger.info(
            f"[{self.name}] upsert start file_path={file_path} date={date_str} " f"note_stem={note_stem} added={added}",
        )

        model = self._vision_model()
        if model is None:
            self.context.response.success = True
            self.context.response.answer = f"Skipped image resource without a vision model: {file_path}"
            self.context.response.metadata.update(
                {
                    "path": file_path,
                    "action": "skipped",
                    "reason": "vision_model_not_configured",
                    "modified": False,
                },
            )
            self.logger.warning(f"[{self.name}] no vision model configured file_path={file_path}")
            return

        payload = await self._read_image(file_path, source_path)
        if payload is None:
            return

        user_message = UserMsg(
            name="user",
            content=[
                TextBlock(
                    text=self.prompt_format(
                        "user_message",
                        file_path=file_path,
                        filename=PurePosixPath(file_path).name,
                        stem=note_stem,
                        date=date_str,
                    ),
                ),
                DataBlock(
                    source=Base64Source(data=payload["data_b64"], media_type=payload["mime"]),
                    name="image",
                ),
            ],
        )
        parsed = await self._caption_with_retry(model, user_message)
        name = _sanitize_note_name(str(parsed.get("name") or ""), note_stem)
        caption = str(parsed.get("caption") or "").strip()
        description = str(parsed.get("description") or "").strip() or caption[:120]
        body = f"![[{file_path}]]\n\n## Caption\n\n{caption}\n"

        # The write job's ``name`` parameter is the note name; calling the job
        # directly (instead of run_job) keeps it clear of run_job's
        # positional-only job-selector argument.
        write_job = self.get_job("write")
        if write_job is None:
            raise RuntimeError("Job write not found")
        write_response = await write_job(
            path=note_path,
            name=name,
            description=description,
            content=body,
            metadata={
                _SOURCE_RESOURCE_KEY: self._source_resource_link(file_path),
                "kind": "image",
                "media_type": payload["source_mime"],
            },
        )
        if not write_response.success:
            raise RuntimeError(f"write failed: {write_response.answer}")
        note_path = await self._finalize_resource_note(
            note_state,
            date_str,
            file_path,
            note_stem,
            added,
        )
        if note_path is None:
            raise RuntimeError(f"Image caption note was not written: {file_path}")

        self.context.response.success = True
        self.context.response.answer = f"Captioned image resource {file_path} -> {note_path}"
        self.context.response.metadata.update(
            {
                "media_type": payload["source_mime"],
            },
        )
        self.logger.info(f"[{self.name}] done {note_path} modified={self.context.response.metadata['modified']}")
