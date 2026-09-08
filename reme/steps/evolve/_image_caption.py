"""Shared image preprocessing and caption generation, without workspace writes."""

import base64
import io
import json
import re
import warnings

from agentscope.message import Base64Source, DataBlock, TextBlock, UserMsg
from agentscope.model import ChatModelBase
from pydantic import BaseModel, Field

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
        resize_frame = None
        try:
            frame = image
            if needs_resize:
                # Pillow forces NEAREST for palette and bilevel images, even
                # when LANCZOS is requested. Expand these modes within the
                # checked pixel budget so resizing retains fine strokes and
                # palette transparency. Other modes resize before conversion.
                if image.mode in ("P", "1"):
                    resize_frame = image.convert("RGBA" if image.mode == "P" else "L")
                    frame = resize_frame
                # Pillow 10 cannot apply LANCZOS directly to 16-bit integer
                # modes; NEAREST keeps that path bounded without a full-size
                # RGB conversion first.
                resize_filter = image_module.Resampling.LANCZOS
                if frame.mode.startswith("I;16"):
                    resize_filter = image_module.Resampling.NEAREST
                frame.thumbnail((MAX_IMAGE_REQUEST_DIMENSION, MAX_IMAGE_REQUEST_DIMENSION), resize_filter)
            has_alpha = frame.mode in ("RGBA", "LA", "P")
            frame = frame.convert("RGBA" if has_alpha else "RGB")
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
        finally:
            if resize_frame is not None:
                resize_frame.close()


def build_image_request_payload(
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


def resolve_vision_model(step) -> ChatModelBase | None:
    """Resolve explicit ``as_llm`` through Ref, otherwise prefer vision/default."""
    context_model = step.context.get("as_llm") if step.context is not None else None
    if "as_llm" in step.kwargs or isinstance(context_model, ChatModelBase):
        return step.as_llm
    if step.app_context is None:
        return None
    models = step.app_context.components.get(ComponentEnum.AS_LLM, {})
    for name in ("vision", "default"):
        if name in models:
            step.kwargs["as_llm"] = name
            return step.as_llm
    return None


async def generate_image_caption(
    model: ChatModelBase,
    payload: dict,
    prompt: str,
    *,
    logger,
    name: str,
) -> dict:
    """Caption a prepared image, preserving the resource model-call contract.

    Try structured output first, then one lenient plain-call fallback. The
    caller owns model resolution, prompt rendering, and any persistence.
    """
    user_message = UserMsg(
        name="user",
        content=[
            TextBlock(text=prompt),
            DataBlock(
                source=Base64Source(data=payload["data_b64"], media_type=payload["mime"]),
                name="image",
            ),
        ],
    )
    try:
        structured = await model.generate_structured_output(
            messages=[user_message],
            structured_model=_CaptionOutput,
        )
        content = structured.content if isinstance(structured.content, dict) else {}
        normalized = _normalize_caption_fields(dict(content))
        if normalized["caption"] or normalized["description"]:
            logger.info(f"[{name}] structured caption ok name={normalized['name']}")
            return normalized
        logger.warning(f"[{name}] structured caption empty; retrying with a plain call")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(f"[{name}] structured caption failed ({type(exc).__name__}); retrying with a plain call")
    result = await model([user_message])
    parsed = _parse_caption_json(await _response_text(result))
    if not parsed["caption"] and not parsed["description"]:
        raise RuntimeError("Vision model returned no usable caption")
    return parsed
