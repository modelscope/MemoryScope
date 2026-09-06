"""Bounded image preparation and one-shot captions for session memory."""

import asyncio
import base64
import io
import json
import warnings

from agentscope.exception import StructuredOutputError
from agentscope.message import Base64Source, DataBlock, TextBlock, UserMsg
from agentscope.model import ChatModelBase
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_IMAGE_INPUT_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_PROVIDER_BYTES = 5 * 1024 * 1024
MAX_IMAGE_SIDE = 2048
MAX_CAPTION_RESPONSE_CHARS = 65_536

_SOURCE_MEDIA_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
}
_PROVIDER_MEDIA_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class ImageCaption(BaseModel):
    """A validated description of visible image content, without source identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200, description="A short descriptive image title.")
    description: str = Field(min_length=1, max_length=2000, description="A concise summary for image discovery.")
    caption: str = Field(
        min_length=1,
        max_length=24_000,
        description="Detailed, grounded visible facts and readable text.",
    )


def _encode_image(image, image_format: str, **kwargs) -> bytes:
    """Encode an already bounded Pillow image without inherited metadata."""
    output = io.BytesIO()
    image.save(output, format=image_format, **kwargs)
    return output.getvalue()


def _provider_image(image, source_format: str) -> tuple[bytes, str]:
    """Keep lossless pixels when practical; use bounded JPEG for large payloads."""
    from PIL import Image

    has_alpha = "A" in image.getbands() or "transparency" in image.info
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.info.clear()
    output_format = "JPEG" if source_format == "JPEG" and not has_alpha else "PNG"
    encoded = _encode_image(image, output_format, **({"quality": 95} if output_format == "JPEG" else {}))
    if len(encoded) <= MAX_IMAGE_PROVIDER_BYTES:
        return encoded, _SOURCE_MEDIA_TYPES[output_format]

    if has_alpha:
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background
    for quality in (90, 80, 65):
        encoded = _encode_image(image, "JPEG", quality=quality)
        if len(encoded) <= MAX_IMAGE_PROVIDER_BYTES:
            return encoded, "image/jpeg"
    raise ValueError("Image cannot be encoded within the provider payload limit")


def normalize_image(data: bytes) -> tuple[bytes, str, str]:
    """Validate source bytes and return (provider bytes, provider MIME, source MIME).

    Source bytes are never modified. Animated or multi-page inputs contribute
    their first frame only. A provider copy has EXIF orientation applied, a
    maximum side of 2048 pixels, and no inherited metadata.
    """
    if not isinstance(data, bytes) or not data:
        raise ValueError("Image must contain non-empty bytes")
    if len(data) > MAX_IMAGE_INPUT_BYTES:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_INPUT_BYTES}-byte input limit")
    if data[4:8] == b"ftyp" and any(brand in data[8:40] for brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1")):
        raise ValueError("HEIC/HEIF images are not supported; convert them to PNG or JPEG")

    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Image memory requires Pillow; install ReMe with its core dependencies") from exc

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=list(_SOURCE_MEDIA_TYPES)) as source:
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError(f"Image exceeds the {MAX_IMAGE_PIXELS}-pixel limit")
                source_format = source.format
                source.verify()
            with Image.open(io.BytesIO(data), formats=list(_SOURCE_MEDIA_TYPES)) as source:
                source.seek(0)
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
                encoded, media_type = _provider_image(image, source_format)
                return encoded, media_type, _SOURCE_MEDIA_TYPES[source_format]
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError(f"Image exceeds the {MAX_IMAGE_PIXELS}-pixel limit") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError(
            "Invalid or unsupported image; supported formats are PNG, JPEG, WebP, GIF, BMP, and TIFF",
        ) from exc


def _structured_fallback_allowed(error: Exception) -> bool:
    """Restrict fallback to output/schema incompatibility, never transport errors."""
    if isinstance(error, (StructuredOutputError, NotImplementedError, ValidationError)):
        return True
    message = str(error).lower()
    schema_error = any(word in message for word in ("schema", "structured", "response_format", "tool_choice", "tools"))
    if getattr(error, "status_code", None) in (400, 422):
        return schema_error
    return (
        isinstance(error, (TypeError, ValueError))
        and schema_error
        and any(
            word in message
            for word in ("unsupported", "not supported", "not implemented", "unexpected keyword", "invalid")
        )
    )


def _response_text(response) -> str:
    """Read text only and reject interrupted or oversized provider responses."""
    if getattr(response, "finished_reason", None) == "interrupted":
        raise asyncio.CancelledError("Image caption generation was interrupted")
    content = getattr(response, "content", [])
    if isinstance(content, str):
        text = content
    else:
        text = "".join(block.text for block in content if isinstance(block, TextBlock))
    if len(text) > MAX_CAPTION_RESPONSE_CHARS:
        raise ValueError("Image caption response exceeds the output limit")
    return text


async def _plain_caption(model: ChatModelBase, message: UserMsg) -> ImageCaption:
    """Make one JSON-only fallback call and consume AgentScope's final response."""
    schema = json.dumps(ImageCaption.model_json_schema(), ensure_ascii=False)
    fallback = message.model_copy(deep=True)
    fallback.content.append(
        TextBlock(
            text=f"Return only one JSON object matching this schema, without markdown fences or commentary: {schema}",
        ),
    )
    response = await model(messages=[fallback])
    if hasattr(response, "__aiter__"):
        final_response = None
        delta_chars = 0
        try:
            async for chunk in response:
                text = _response_text(chunk)
                if chunk.is_last:
                    final_response = chunk
                else:
                    delta_chars += len(text)
                    if delta_chars > MAX_CAPTION_RESPONSE_CHARS:
                        raise ValueError("Image caption response exceeds the output limit")
        finally:
            if hasattr(response, "aclose"):
                await response.aclose()
        if final_response is None:
            raise ValueError("Image caption stream ended without a complete response")
        response = final_response
    text = _response_text(response).strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[8:-4].strip()
    try:
        return ImageCaption.model_validate_json(text)
    except ValidationError as exc:
        raise ValueError("Image caption model did not return a valid name, description, and caption") from exc


async def caption_image(model: ChatModelBase, data: bytes, media_type: str, prompt: str) -> ImageCaption:
    """Caption a normalized image, with at most one additional JSON fallback call."""
    if not data or len(data) > MAX_IMAGE_PROVIDER_BYTES:
        raise ValueError("Image caption input must fit the provider payload limit")
    if media_type not in _PROVIDER_MEDIA_TYPES:
        raise ValueError("Image caption input must be PNG, JPEG, WebP, or GIF")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Image caption prompt must not be empty")
    message = UserMsg(
        name="user",
        content=[
            TextBlock(text=prompt),
            DataBlock(source=Base64Source(data=base64.b64encode(data).decode("ascii"), media_type=media_type)),
        ],
    )
    try:
        result = await model.generate_structured_output(messages=[message], structured_model=ImageCaption)
    except Exception as exc:
        if not _structured_fallback_allowed(exc):
            raise
    else:
        if getattr(result, "finished_reason", None) == "interrupted":
            raise asyncio.CancelledError("Image caption generation was interrupted")
        try:
            return ImageCaption.model_validate(getattr(result, "content", None))
        except ValidationError:
            pass
    return await _plain_caption(model, message)
