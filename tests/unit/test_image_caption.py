"""Image validation and caption provider boundaries, without network calls."""

import asyncio
import base64
import io
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentscope.exception import StructuredOutputError
from agentscope.message import DataBlock, TextBlock
from agentscope.model import ChatResponse
from PIL import Image, ImageOps
from pydantic import ValidationError

from reme.steps.evolve import _image_caption as caption_module
from reme.steps.evolve._image_caption import ImageCaption, caption_image, normalize_image

CAPTION = {"name": "Red mug", "description": "A red mug on a desk.", "caption": "A red mug marked 204 sits on a desk."}
_UNSET = object()


def image_bytes(image_format="PNG", size=(12, 8), **kwargs):
    """Build a small, valid raster fixture entirely in memory."""
    output = io.BytesIO()
    Image.new("RGB", size, "red").save(output, format=image_format, **kwargs)
    return output.getvalue()


class CaptionModel:
    """Mock both structured and plain model interfaces."""

    def __init__(self, structured=_UNSET, error=None, plain=None):
        if structured is _UNSET:
            structured = CAPTION
        self.generate_structured_output = AsyncMock(return_value=SimpleNamespace(content=structured), side_effect=error)
        self.plain = AsyncMock(
            return_value=plain or ChatResponse(content=[TextBlock(text=json.dumps(CAPTION))], is_last=True),
        )

    async def __call__(self, **kwargs):
        return await self.plain(**kwargs)


@pytest.mark.parametrize(
    ("source_format", "source_mime"),
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("WEBP", "image/webp"),
        ("GIF", "image/gif"),
        ("BMP", "image/bmp"),
        ("TIFF", "image/tiff"),
    ],
)
def test_normalization_sniffs_supported_formats_without_changing_original(source_format, source_mime):
    """A provider copy has a truthful MIME type and source bytes remain intact."""
    source = image_bytes(source_format)
    original = bytes(source)

    prepared, provider_mime, detected_mime = normalize_image(source)

    assert source == original
    assert detected_mime == source_mime
    with Image.open(io.BytesIO(prepared)) as result:
        assert Image.MIME[result.format] == provider_mime
        assert result.size == (12, 8)


def test_normalization_applies_exif_orientation_before_resizing():
    """OCR and spatial facts see the displayed orientation, without stale EXIF."""
    exif = Image.Exif()
    exif[274] = 6
    source = image_bytes("JPEG", size=(3000, 1000), exif=exif)

    prepared, _, _ = normalize_image(source)

    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == (683, 2048)
        assert 274 not in result.getexif()
    with Image.open(io.BytesIO(source)) as original:
        assert original.size == (3000, 1000)
        assert original.getexif()[274] == 6


def test_normalization_uses_only_first_frame():
    """Animated GIFs deterministically expose the first frame to the captioner."""
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        output,
        format="GIF",
        save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")],
    )

    prepared, provider_mime, source_mime = normalize_image(output.getvalue())

    assert provider_mime == "image/png"
    assert source_mime == "image/gif"
    with Image.open(io.BytesIO(prepared)) as result:
        assert result.getpixel((0, 0)) == (255, 0, 0)
        assert not getattr(result, "is_animated", False)


def test_large_lossless_payload_falls_back_to_bounded_jpeg():
    """High-entropy PNG input fits the provider byte limit after normalization."""
    output = io.BytesIO()
    Image.frombytes("RGB", (2048, 2048), os.urandom(2048 * 2048 * 3)).save(output, format="PNG")
    assert len(output.getvalue()) > caption_module.MAX_IMAGE_PROVIDER_BYTES

    prepared, provider_mime, source_mime = normalize_image(output.getvalue())

    assert source_mime == "image/png"
    assert provider_mime == "image/jpeg"
    assert len(prepared) <= caption_module.MAX_IMAGE_PROVIDER_BYTES


def test_input_byte_limit_precedes_pillow_open(monkeypatch):
    """Oversized inputs cannot reach the decoder."""
    monkeypatch.setattr(caption_module, "MAX_IMAGE_INPUT_BYTES", 4)
    monkeypatch.setattr(Image, "open", lambda *_args, **_kwargs: pytest.fail("Decoder must not be reached"))

    with pytest.raises(ValueError, match="input limit"):
        normalize_image(b"12345")


def test_pixel_limit_precedes_image_decode(monkeypatch):
    """Header dimensions reject decompression-heavy inputs before loading pixels."""
    source = image_bytes(size=(100, 100))
    monkeypatch.setattr(caption_module, "MAX_IMAGE_PIXELS", 99)
    monkeypatch.setattr(ImageOps, "exif_transpose", lambda *_args: pytest.fail("Pixel decode must not be reached"))

    with pytest.raises(ValueError, match="pixel limit"):
        normalize_image(source)


@pytest.mark.parametrize("data", [b"", b"not an image", b"<svg></svg>"])
def test_empty_or_unsupported_image_is_rejected(data):
    """Non-raster content is never forwarded as a claimed image."""
    with pytest.raises(ValueError):
        normalize_image(data)


def test_truncated_image_is_rejected():
    """A valid header alone is not sufficient to accept image bytes."""
    with pytest.raises(ValueError, match="Invalid or unsupported"):
        normalize_image(image_bytes()[:-20])


def test_heic_reports_explicit_unsupported_format():
    """No optional codec is silently required or imported for HEIC."""
    with pytest.raises(ValueError, match="HEIC/HEIF images are not supported"):
        normalize_image(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16)


@pytest.mark.parametrize("field", ["name", "description", "caption"])
def test_empty_caption_field_is_never_success(field):
    """Whitespace-only visual facts cannot become persisted memory."""
    with pytest.raises(ValidationError):
        ImageCaption.model_validate({**CAPTION, field: "  \n "})


@pytest.mark.asyncio
async def test_structured_caption_sends_one_image_and_preserves_prompt():
    """The VLM call receives original prompt and the normalized image bytes."""
    model = CaptionModel()
    source = image_bytes()

    result = await caption_image(model, source, "image/png", "Describe visible text and objects.")

    assert result.model_dump() == CAPTION
    call = model.generate_structured_output.call_args.kwargs
    assert call["structured_model"] is ImageCaption
    blocks = call["messages"][0].content
    assert blocks[0].text == "Describe visible text and objects."
    assert isinstance(blocks[1], DataBlock)
    assert blocks[1].source.media_type == "image/png"
    assert base64.b64decode(blocks[1].source.data) == source
    model.plain.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [NotImplementedError(), StructuredOutputError("invalid tool output")])
async def test_unsupported_structured_output_has_one_plain_fallback(error):
    """Schema incompatibility changes output mode without losing the image."""
    model = CaptionModel(error=error)

    result = await caption_image(model, image_bytes(), "image/png", "Caption the image.")

    assert result.model_dump() == CAPTION
    model.generate_structured_output.assert_awaited_once()
    model.plain.assert_awaited_once()
    fallback = model.plain.call_args.kwargs
    assert "stream" not in fallback
    assert fallback["messages"][0].content[0].text == "Caption the image."
    assert isinstance(fallback["messages"][0].content[1], DataBlock)
    assert "JSON object" in fallback["messages"][0].content[2].text


@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [None, {}, {**CAPTION, "caption": " "}])
async def test_invalid_structured_content_gets_one_validated_fallback(structured):
    """A successful HTTP response is not enough to establish caption success."""
    model = CaptionModel(structured=structured)

    result = await caption_image(model, image_bytes(), "image/png", "Caption.")

    assert result.model_dump() == CAPTION
    model.plain.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError("timeout"), ValueError("invalid API key"), RuntimeError("rate limit")])
async def test_provider_failures_do_not_trigger_another_caption_call(error):
    """Transport/auth problems retain their failure and do not multiply requests."""
    model = CaptionModel(error=error)

    with pytest.raises(type(error), match=str(error)):
        await caption_image(model, image_bytes(), "image/png", "Caption.")

    model.plain.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "expected_fallback"), [(400, True), (401, False), (429, False)])
async def test_provider_schema_rejection_falls_back_but_auth_and_limits_do_not(status, expected_fallback):
    """Only a provider's schema rejection warrants changing the request shape."""
    error = RuntimeError("response_format json_schema is not supported")
    error.status_code = status
    model = CaptionModel(error=error)

    if expected_fallback:
        assert (await caption_image(model, image_bytes(), "image/png", "Caption.")).model_dump() == CAPTION
        model.plain.assert_awaited_once()
    else:
        with pytest.raises(RuntimeError, match="not supported"):
            await caption_image(model, image_bytes(), "image/png", "Caption.")
        model.plain.assert_not_awaited()


@pytest.mark.asyncio
async def test_plain_fallback_consumes_final_stream_snapshot_once():
    """AgentScope's complete final response must not be appended to its deltas."""
    closed = []

    async def stream():
        try:
            yield ChatResponse(content=[TextBlock(text='{"name":')], is_last=False)
            yield ChatResponse(content=[TextBlock(text=json.dumps(CAPTION))], is_last=True)
        finally:
            closed.append(True)

    model = CaptionModel(error=NotImplementedError(), plain=stream())

    result = await caption_image(model, image_bytes(), "image/png", "Caption.")

    assert result.model_dump() == CAPTION
    assert closed == [True]


@pytest.mark.asyncio
async def test_incomplete_stream_is_not_accepted():
    """Even parseable partial output cannot be mistaken for completed generation."""

    async def stream():
        yield ChatResponse(content=[TextBlock(text=json.dumps(CAPTION))], is_last=False)

    model = CaptionModel(error=NotImplementedError(), plain=stream())
    with pytest.raises(ValueError, match="complete response"):
        await caption_image(model, image_bytes(), "image/png", "Caption.")


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["", "not json", json.dumps({**CAPTION, "caption": ""})])
async def test_invalid_plain_output_stops_after_one_fallback(output):
    """No fabricated caption or unbounded retry can turn invalid output into success."""
    model = CaptionModel(
        error=NotImplementedError(),
        plain=ChatResponse(content=[TextBlock(text=output)], is_last=True),
    )

    with pytest.raises(ValueError, match="valid name, description, and caption"):
        await caption_image(model, image_bytes(), "image/png", "Caption.")

    model.plain.assert_awaited_once()


@pytest.mark.asyncio
async def test_oversized_plain_output_is_rejected_before_parsing(monkeypatch):
    """Fallback output has a fixed size cap independent of JSON validity."""
    monkeypatch.setattr(caption_module, "MAX_CAPTION_RESPONSE_CHARS", 10)
    model = CaptionModel(error=NotImplementedError())

    with pytest.raises(ValueError, match="output limit"):
        await caption_image(model, image_bytes(), "image/png", "Caption.")


@pytest.mark.asyncio
async def test_cancelled_generation_is_not_retried():
    """Cancellation propagates without starting a second provider operation."""
    model = CaptionModel(error=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await caption_image(model, image_bytes(), "image/png", "Caption.")

    model.plain.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_plain_response_cannot_become_memory():
    """AgentScope represents some cancellations as an interrupted response."""
    model = CaptionModel(
        error=NotImplementedError(),
        plain=ChatResponse(content=[TextBlock(text=json.dumps(CAPTION))], is_last=True, finished_reason="interrupted"),
    )

    with pytest.raises(asyncio.CancelledError):
        await caption_image(model, image_bytes(), "image/png", "Caption.")


@pytest.mark.asyncio
async def test_oversized_stream_is_closed_without_waiting_for_completion(monkeypatch):
    """The output cap stops streaming even before a final snapshot arrives."""
    monkeypatch.setattr(caption_module, "MAX_CAPTION_RESPONSE_CHARS", 10)
    closed = []

    async def stream():
        try:
            yield ChatResponse(content=[TextBlock(text="123456")], is_last=False)
            yield ChatResponse(content=[TextBlock(text="789012")], is_last=False)
            pytest.fail("Oversized stream should already have been closed")
        finally:
            closed.append(True)

    model = CaptionModel(error=NotImplementedError(), plain=stream())

    with pytest.raises(ValueError, match="output limit"):
        await caption_image(model, image_bytes(), "image/png", "Caption.")

    assert closed == [True]
