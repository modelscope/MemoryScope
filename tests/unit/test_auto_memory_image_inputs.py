"""Bounded and workspace-scoped image input for caption-only auto-memory."""

# pylint: disable=protected-access,missing-function-docstring

import base64
from types import SimpleNamespace

import httpx
import pytest
from agentscope.message import Base64Source, URLSource

from reme.components.runtime_context import RuntimeContext
from reme.steps.evolve import _auto_memory_image
from .auto_resource_test_support import png_bytes


def _source(data):
    return Base64Source(data=base64.b64encode(data).decode("ascii"), media_type="image/png")


def _step(workspace, **context):
    return SimpleNamespace(
        file_store=SimpleNamespace(workspace_path=workspace),
        context=RuntimeContext(**context),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1, 8, 9])
async def test_base64_decoded_byte_limit_is_inclusive(tmp_path, monkeypatch, size):
    monkeypatch.setattr(_auto_memory_image, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)
    source = _source(b"x" * size)
    if size <= 8:
        assert await _auto_memory_image._image_bytes(_step(tmp_path), source) == b"x" * size
    else:
        with pytest.raises(ValueError, match="byte limit"):
            await _auto_memory_image._image_bytes(_step(tmp_path), source)


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ["", "%%BAD%%", "YQ==junk", "Y Q==", "YQ"])
async def test_invalid_or_empty_base64_is_rejected(tmp_path, data):
    with pytest.raises(ValueError):
        await _auto_memory_image._image_bytes(
            _step(tmp_path),
            Base64Source(data=data, media_type="image/png"),
        )


@pytest.mark.asyncio
async def test_base64_over_limit_is_rejected_before_decode(tmp_path, monkeypatch):
    monkeypatch.setattr(_auto_memory_image, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Oversized Base64 must be rejected before allocation")

    monkeypatch.setattr(_auto_memory_image.base64, "b64decode", forbidden)
    with pytest.raises(ValueError, match="byte limit"):
        await _auto_memory_image._image_bytes(
            _step(tmp_path),
            Base64Source(data="A" * 16, media_type="image/png"),
        )


@pytest.mark.asyncio
async def test_workspace_file_url_preserves_encoded_name_and_bytes(tmp_path):
    target = tmp_path / "user image #1.png"
    data = png_bytes()
    target.write_bytes(data)
    source = URLSource(url=target.as_uri(), media_type="image/png")

    assert await _auto_memory_image._image_bytes(_step(tmp_path), source) == data
    assert target.read_bytes() == data


@pytest.mark.asyncio
@pytest.mark.parametrize("escape", ["outside", "symlink", "scope", "remote-host", "query"])
async def test_file_urls_cannot_escape_workspace_or_permissions(tmp_path, escape):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(png_bytes())
    inside = workspace / "inside.png"
    inside.write_bytes(png_bytes())
    context = {}
    if escape == "outside":
        url = outside.as_uri()
    elif escape == "symlink":
        link = workspace / "link.png"
        link.symlink_to(outside)
        url = link.as_uri()
    elif escape == "scope":
        context["_allowed_paths"] = ["other"]
        url = inside.as_uri()
    elif escape == "remote-host":
        url = "file://other-host" + inside.as_posix()
    else:
        url = inside.as_uri() + "?password=secret"
    with pytest.raises((ValueError, PermissionError)):
        await _auto_memory_image._image_bytes(_step(workspace, **context), URLSource(url=url, media_type="image/png"))
    assert outside.read_bytes() == png_bytes()
    assert inside.read_bytes() == png_bytes()


class _Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("oversized", [False, True])
async def test_http_read_is_bounded_and_closes_stream(tmp_path, monkeypatch, oversized):
    monkeypatch.setattr(_auto_memory_image, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)
    stream = _Chunks([b"1234", b"5678", b"9", b"MUST_NOT_READ"] if oversized else [b"1234", b"5678"])
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/image"})
        return httpx.Response(200, stream=stream)

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        _auto_memory_image.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    source = URLSource(url="https://images.invalid/redirect", media_type="image/png")
    if oversized:
        with pytest.raises(ValueError, match="byte limit"):
            await _auto_memory_image._image_bytes(_step(tmp_path), source)
        assert stream.read_count == 3
    else:
        assert await _auto_memory_image._image_bytes(_step(tmp_path), source) == b"12345678"
        assert stream.read_count == 2
    assert calls == ["/redirect", "/image"]
    assert stream.closed


@pytest.mark.asyncio
async def test_http_redirect_count_is_bounded(tmp_path, monkeypatch):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(302, headers={"location": "/next"})

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        _auto_memory_image.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    with pytest.raises(httpx.TooManyRedirects):
        await _auto_memory_image._image_bytes(
            _step(tmp_path),
            URLSource(url="https://images.invalid/redirect", media_type="image/png"),
        )
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_file_source_read_checks_byte_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(_auto_memory_image, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)
    path = tmp_path / "oversized.png"
    path.write_bytes(b"x" * 9)

    with pytest.raises(ValueError, match="byte limit"):
        await _auto_memory_image._image_bytes(
            _step(tmp_path),
            URLSource(url=path.as_uri(), media_type="image/png"),
        )
    assert path.read_bytes() == b"x" * 9


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 404, 500])
async def test_http_errors_are_not_interpreted_as_image_bytes(tmp_path, monkeypatch, status):
    def respond(_request):
        return httpx.Response(status, content=b"not image data")

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        _auto_memory_image.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await _auto_memory_image._image_bytes(
            _step(tmp_path),
            URLSource(url="https://images.invalid/failed", media_type="image/png"),
        )
