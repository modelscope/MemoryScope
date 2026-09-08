"""Image validation and caption provider boundaries, without network calls."""

import asyncio
import base64
import io
import inspect
import json
import os
import struct
import zlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentscope.exception import StructuredOutputError
from agentscope.message import DataBlock, TextBlock
from agentscope.model import ChatResponse
from PIL import Image, ImageOps, JpegImagePlugin
from pydantic import ValidationError

from reme.steps.evolve import _image_caption as caption_module
from reme.steps.evolve._image_caption import ImageCaption, caption_image, normalize_image, validate_image

CAPTION = {"name": "Red mug", "description": "A red mug on a desk.", "caption": "A red mug marked 204 sits on a desk."}
_UNSET = object()


def image_bytes(image_format="PNG", size=(12, 8), **kwargs):
    """Build a small, valid raster fixture entirely in memory."""
    output = io.BytesIO()
    Image.new("RGB", size, "red").save(output, format=image_format, **kwargs)
    return output.getvalue()


def transparent_16_bit_png():
    """Encode an exact tRNS sample, including with Pillow 10's limited writer."""
    with Image.frombytes("I;16", (2, 1), struct.pack("<2H", 16384, 16385)) as image, io.BytesIO() as output:
        image.save(output, format="PNG")
        source = output.getvalue()
    chunk = b"tRNS" + struct.pack(">H", 16384)
    # Insert the valid two-byte transparency chunk after PNG's mandatory IHDR.
    return source[:33] + struct.pack(">I", 2) + chunk + struct.pack(">I", zlib.crc32(chunk)) + source[33:]


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


@pytest.mark.parametrize("source_format", ["PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"])
def test_validation_decodes_without_provider_preparation(source_format, monkeypatch):
    """Ingestion validation does not resize, encode or transpose source pixels."""
    source = image_bytes(source_format)
    original = bytes(source)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Validation must not prepare a provider image")

    monkeypatch.setattr(Image.Image, "thumbnail", unexpected)
    monkeypatch.setattr(Image.Image, "save", unexpected)
    # Pillow's TIFF decoder applies orientation itself as part of load().
    if source_format != "TIFF":
        monkeypatch.setattr(ImageOps, "exif_transpose", unexpected)
    assert validate_image(source) == Image.MIME[source_format]
    assert source == original


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
def test_validation_rejects_truncated_jpeg_after_header_verification(prepare):
    """JPEG verify alone cannot establish that the first frame is decodable."""
    source = image_bytes("JPEG", size=(80, 80))[:-30]
    with Image.open(io.BytesIO(source)) as image:
        image.verify()
    with pytest.raises(ValueError, match="Invalid or unsupported"):
        prepare(source)


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
def test_validation_rejects_corrupt_png_checksum(prepare):
    """Both paths retain structural validation in addition to pixel decoding."""
    source = bytearray(image_bytes())
    source[-17] ^= 1
    with pytest.raises(ValueError, match="Invalid or unsupported"):
        prepare(bytes(source))


@pytest.mark.parametrize(("mode", "transparent"), [("P", False), ("1", False), ("P", True)])
def test_normalization_retains_thin_strokes_and_palette_alpha(mode, transparent):
    """Filtered downscaling retains fine chart/OCR strokes and palette opacity."""
    source_image = Image.new(mode, (4096, 256), 1 if mode == "1" else 0)
    if mode == "P":
        source_image.putpalette([255, 255, 255, 0, 0, 0] + [0] * 762)
        if transparent:
            source_image.info["transparency"] = 0
    source_image.paste(0 if mode == "1" else 1, (0, 0, 1, 256))
    with io.BytesIO() as buffer:
        source_image.save(buffer, format="PNG")
        original = buffer.getvalue()
    source_image.close()

    prepared, mime, source_mime = normalize_image(original)

    assert mime == source_mime == "image/png"
    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == (2048, 128)
        if transparent:
            assert result.mode == "RGBA"
            minimum, maximum = result.getextrema()[3]
            assert minimum == 0
            assert 0 < maximum < 255
        else:
            assert result.getextrema()[0][0] < 240
            assert result.getpixel((2047, 0))[:3] == (255, 255, 255)


@pytest.mark.parametrize("orientation", [1, 6, 8])
def test_large_jpeg_decoder_scales_before_loading_and_keeps_orientation(orientation, monkeypatch):
    """Provider preparation uses decoder scaling before in-place EXIF rotation."""
    exif = Image.Exif()
    exif[274] = orientation
    source = image_bytes("JPEG", size=(4096, 1024), exif=exif)
    decoded_sizes = []
    original_load = JpegImagePlugin.JpegImageFile.load

    def record_load(frame, *args, **kwargs):
        decoded_sizes.append(frame.size)
        return original_load(frame, *args, **kwargs)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "load", record_load)
    prepared, mime, source_mime = normalize_image(source)

    assert decoded_sizes[0] == (2048, 512)
    assert mime == source_mime == "image/jpeg"
    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == ((2048, 512) if orientation == 1 else (512, 2048))
        assert 274 not in result.getexif()
    with Image.open(io.BytesIO(source)) as original:
        assert original.size == (4096, 1024)
        assert original.getexif()[274] == orientation


def test_validation_decodes_jpeg_at_original_size(monkeypatch):
    """Validation is not an image transformation and never uses JPEG draft."""
    source = image_bytes("JPEG", size=(4096, 1024))
    decoded_sizes = []
    original_load = JpegImagePlugin.JpegImageFile.load

    def record_load(frame, *args, **kwargs):
        decoded_sizes.append(frame.size)
        return original_load(frame, *args, **kwargs)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "load", record_load)
    assert validate_image(source) == "image/jpeg"
    assert decoded_sizes == [(4096, 1024)]


@pytest.mark.parametrize("source_format", ["JPEG", "PNG", "TIFF"])
def test_normalization_strips_source_metadata(source_format):
    """EXIF artist/description metadata never enters the provider copy."""
    exif = Image.Exif()
    exif[270] = "PRIVATE_DESCRIPTION_MARKER"
    exif[315] = "PRIVATE_ARTIST_MARKER"
    source = image_bytes(source_format, exif=exif)

    assert validate_image(source) == Image.MIME[source_format]
    prepared, _, _ = normalize_image(source)

    assert b"PRIVATE_" not in prepared
    with Image.open(io.BytesIO(prepared)) as result:
        assert not result.getexif()
    with Image.open(io.BytesIO(source)) as original:
        assert original.getexif()[315] == "PRIVATE_ARTIST_MARKER"


@pytest.mark.parametrize("failure", [None, "thumbnail", "convert", "save"])
def test_normalization_closes_owned_images_even_on_failure(failure, monkeypatch):
    """Source, palette-expanded and provider frames are explicitly released."""
    source_image = Image.new("P", (2049, 2))
    with io.BytesIO() as buffer:
        source_image.save(buffer, format="PNG")
        source = buffer.getvalue()
    source_image.close()
    frames = []
    original_open, original_convert = Image.open, Image.Image.convert

    def record_open(*args, **kwargs):
        frame = original_open(*args, **kwargs)
        frames.append(frame)
        return frame

    def record_convert(frame, *args, **kwargs):
        # Fail the second conversion, after the large palette expansion exists.
        if failure == "convert" and frame.mode == "RGBA":
            raise OSError("Synthetic conversion failure")
        converted = original_convert(frame, *args, **kwargs)
        # Pillow's resize creates additional internal premultiplication frames;
        # this assertion concerns the images created/owned by our helper.
        if inspect.currentframe().f_back.f_code.co_filename == caption_module.__file__:
            frames.append(converted)
        return converted

    monkeypatch.setattr(Image, "open", record_open)
    monkeypatch.setattr(Image.Image, "convert", record_convert)
    if failure in {"thumbnail", "save"}:
        monkeypatch.setattr(Image.Image, failure, lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("Synthetic")))

    if failure:
        with pytest.raises(ValueError, match="Invalid or unsupported"):
            normalize_image(source)
    else:
        normalize_image(source)

    assert len(frames) >= 3
    for frame in frames:
        with pytest.raises(ValueError, match="closed image"):
            frame.getpixel((0, 0))


@pytest.mark.parametrize("fail_paste", [False, True])
def test_alpha_fallback_closes_background_and_mask(fail_paste, monkeypatch):
    """JPEG fallback owns all alpha-compositing resources on success and failure."""
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
    frames = []
    original_new, original_convert, original_channel = Image.new, Image.Image.convert, Image.Image.getchannel

    def record(function):
        def invoke(*args, **kwargs):
            frame = function(*args, **kwargs)
            frames.append(frame)
            return frame

        return invoke

    monkeypatch.setattr(Image, "new", record(original_new))
    monkeypatch.setattr(Image.Image, "convert", record(original_convert))
    monkeypatch.setattr(Image.Image, "getchannel", record(original_channel))
    monkeypatch.setattr(caption_module, "MAX_IMAGE_PROVIDER_BYTES", 5)
    monkeypatch.setattr(
        caption_module,
        "_encode_image",
        lambda _image, fmt, **_kwargs: b"123456" if fmt == "PNG" else b"1",
    )
    if fail_paste:
        monkeypatch.setattr(Image.Image, "paste", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("Synthetic")))
    try:
        if fail_paste:
            with pytest.raises(OSError, match="Synthetic"):
                caption_module._provider_image(image, "PNG")  # pylint: disable=protected-access
        else:
            assert caption_module._provider_image(image, "PNG") == (  # pylint: disable=protected-access
                b"1",
                "image/jpeg",
            )
        assert len(frames) >= 3
        for frame in frames:
            with pytest.raises(ValueError, match="closed image"):
                frame.getpixel((0, 0))
        assert image.getpixel((0, 0)) == (255, 0, 0, 128)  # Caller still owns its input.
    finally:
        image.close()


@pytest.mark.parametrize("mode", ["I;16", "I;16B"])
def test_normalization_resizes_16_bit_tiff_on_pillow_10(mode):
    """Large 16-bit inputs resize without requiring Pillow 11's LANCZOS support."""
    output = io.BytesIO()
    image = Image.new(mode, (3000, 1000), 0)
    image.paste(65535, (1500, 0, 3000, 1000))
    image.save(output, format="TIFF")
    source = output.getvalue()
    original = bytes(source)

    prepared, provider_mime, source_mime = normalize_image(source)

    assert source == original
    assert source_mime == "image/tiff"
    assert provider_mime == "image/png"
    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == (2048, 683)
        assert result.getpixel((0, 0)) == (0, 0, 0)
        assert result.getpixel((2047, 682)) == (255, 255, 255)


@pytest.mark.parametrize(("source_format", "mode"), [("PNG", "I;16"), ("TIFF", "I;16"), ("TIFF", "I;16B")])
def test_normalization_maps_16_bit_midtones_without_clipping_or_contrast_stretch(source_format, mode):
    """Unsigned samples use the full 16-bit range, not this image's extrema."""
    values = (16384, 24576, 32768, 40960, 49152)
    pixels = struct.pack((">" if mode.endswith("B") else "<") + "5H", *values)
    with Image.frombytes(mode, (5, 1), pixels) as image, io.BytesIO() as output:
        image.save(output, format=source_format)
        source = output.getvalue()
    original = bytes(source)

    prepared, provider_mime, source_mime = normalize_image(source)

    assert source == original
    assert source_mime == Image.MIME[source_format]
    assert provider_mime == "image/png"
    with Image.open(io.BytesIO(source)) as image:
        assert [image.getpixel((x, 0)) for x in range(5)] == list(values)
    with Image.open(io.BytesIO(prepared)) as result:
        assert [result.getpixel((x, 0)) for x in range(5)] == [(value,) * 3 for value in (64, 96, 128, 159, 191)]


@pytest.mark.parametrize(("source_format", "mode"), [("PNG", "I;16"), ("TIFF", "I;16"), ("TIFF", "I;16B")])
def test_normalization_filters_16_bit_midgray_thin_strokes(source_format, mode):
    """Downscaling retains thin non-black strokes rather than choosing NEAREST."""
    with Image.new(mode, (4096, 64), 49152) as image, io.BytesIO() as output:
        image.paste(16384, (2000, 0, 2001, 64))
        image.save(output, format=source_format)
        source = output.getvalue()

    prepared, _, _ = normalize_image(source)

    with Image.open(io.BytesIO(prepared)) as result:
        assert result.size == (2048, 32)
        assert result.getpixel((0, 16)) == (191, 191, 191)
        assert 64 < result.getpixel((1000, 16))[0] < 191
        assert result.getextrema()[0][0] < 191


def test_normalization_preserves_16_bit_png_transparency_before_quantizing():
    """Different source samples that map to one gray value retain distinct alpha."""
    source = transparent_16_bit_png()

    prepared, _, _ = normalize_image(source)

    with Image.open(io.BytesIO(prepared)) as result:
        assert result.mode == "RGBA"
        assert result.getpixel((0, 0)) == (64, 64, 64, 0)
        assert result.getpixel((1, 0)) == (64, 64, 64, 255)


@pytest.mark.parametrize("failure", [None, "point", "putalpha", "thumbnail", "save"])
def test_normalization_closes_16_bit_conversion_frames(failure, monkeypatch):
    """The integer, mapped gray and exact-alpha frames close on every exit."""
    source = transparent_16_bit_png()
    frames = []

    def record(method, name):
        def invoke(*args, **kwargs):
            if failure == name:
                raise OSError("Synthetic image conversion failure")
            frame = method(*args, **kwargs)
            if name == "open" or inspect.currentframe().f_back.f_code.co_filename == caption_module.__file__:
                frames.append(frame)
            return frame

        return invoke

    monkeypatch.setattr(Image, "open", record(Image.open, "open"))
    for name in ("point", "convert"):
        monkeypatch.setattr(Image.Image, name, record(getattr(Image.Image, name), name))
    if failure in {"putalpha", "thumbnail", "save"}:
        monkeypatch.setattr(Image.Image, failure, lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("Synthetic")))

    if failure:
        with pytest.raises(ValueError, match="Invalid or unsupported"):
            normalize_image(source)
    else:
        normalize_image(source)

    assert len(frames) >= 2
    for frame in frames:
        with pytest.raises(ValueError, match="closed image"):
            frame.getpixel((0, 0))


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


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
def test_input_byte_limit_precedes_pillow_open(monkeypatch, prepare):
    """Oversized inputs cannot reach the decoder."""
    monkeypatch.setattr(caption_module, "MAX_IMAGE_INPUT_BYTES", 4)
    monkeypatch.setattr(Image, "open", lambda *_args, **_kwargs: pytest.fail("Decoder must not be reached"))

    with pytest.raises(ValueError, match="input limit"):
        prepare(b"12345")


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
def test_pixel_limit_precedes_image_decode(monkeypatch, prepare):
    """Header dimensions reject decompression-heavy inputs before loading pixels."""
    source = image_bytes(size=(100, 100))
    monkeypatch.setattr(caption_module, "MAX_IMAGE_PIXELS", 99)
    monkeypatch.setattr(Image.Image, "load", lambda *_args: pytest.fail("Pixel decode must not be reached"))

    with pytest.raises(ValueError, match="pixel limit"):
        prepare(source)


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
@pytest.mark.parametrize("pillow_limit", [60, 10])
def test_pillow_bomb_warning_and_error_are_rejected(prepare, pillow_limit, monkeypatch):
    """Pillow's warning/error thresholds both fail closed before decoding pixels."""
    source = image_bytes(size=(10, 10))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", pillow_limit)
    with pytest.raises(ValueError, match="pixel limit"):
        prepare(source)


@pytest.mark.parametrize("prepare", [validate_image, normalize_image])
def test_jpeg_container_subtype_does_not_bypass_format_allowlist(prepare):
    """JPEG plugin detection of MPO does not authorize an unsupported source MIME."""
    with io.BytesIO() as buffer:
        Image.new("RGB", (8, 8), "red").save(
            buffer,
            format="MPO",
            save_all=True,
            append_images=[Image.new("RGB", (8, 8), "blue")],
        )
        source = buffer.getvalue()
    with pytest.raises(ValueError, match="[Uu]nsupported"):
        prepare(source)


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
async def test_incomplete_nonstream_response_is_not_accepted():
    """Custom model adapters cannot turn a non-final chunk into caption success."""
    model = CaptionModel(
        error=NotImplementedError(),
        plain=ChatResponse(content=[TextBlock(text=json.dumps(CAPTION))], is_last=False),
    )
    with pytest.raises(ValueError, match="incomplete response"):
        await caption_image(model, image_bytes(), "image/png", "Caption.")
    model.plain.assert_awaited_once()


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
