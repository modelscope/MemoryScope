"""Independent input-boundary and real-resource-job checks for session images."""

# pylint: disable=protected-access,missing-function-docstring

import base64
import copy
import hashlib
from types import SimpleNamespace

import httpx
import pytest
from agentscope.message import Base64Source, DataBlock, Msg, TextBlock, URLSource

from reme.components import R
from reme.components.job import BaseJob
from reme.components.runtime_context import RuntimeContext
from reme.steps.evolve import _session_images
from reme.steps.evolve.auto_memory import AutoMemoryStep
from .auto_resource_test_support import StructuredVisionModel, png_bytes

pytest_plugins = ("unit.auto_resource_test_plugin",)

_DAY = "2026-09-03"


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
    monkeypatch.setattr(_session_images, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)
    source = _source(b"x" * size)
    if size <= 8:
        assert await _session_images._image_bytes(_step(tmp_path), source) == b"x" * size
    else:
        with pytest.raises(ValueError, match="byte limit"):
            await _session_images._image_bytes(_step(tmp_path), source)


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ["", "%%BAD%%", "YQ==junk", "Y Q==", "YQ"])
async def test_invalid_or_empty_base64_is_rejected(tmp_path, data):
    with pytest.raises(ValueError):
        await _session_images._image_bytes(
            _step(tmp_path),
            Base64Source(data=data, media_type="image/png"),
        )


@pytest.mark.asyncio
async def test_base64_over_limit_is_rejected_before_decode(tmp_path, monkeypatch):
    monkeypatch.setattr(_session_images, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Oversized Base64 must be rejected before allocation")

    monkeypatch.setattr(_session_images.base64, "b64decode", forbidden)
    with pytest.raises(ValueError, match="byte limit"):
        await _session_images._image_bytes(
            _step(tmp_path),
            Base64Source(data="A" * 16, media_type="image/png"),
        )


@pytest.mark.asyncio
async def test_workspace_file_url_preserves_encoded_name_and_bytes(tmp_path):
    target = tmp_path / "user image #1.png"
    data = png_bytes()
    target.write_bytes(data)
    source = URLSource(url=target.as_uri(), media_type="image/png")

    assert await _session_images._image_bytes(_step(tmp_path), source) == data
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
        await _session_images._image_bytes(_step(workspace, **context), URLSource(url=url, media_type="image/png"))
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
    monkeypatch.setattr(_session_images, "DEFAULT_MAX_IMAGE_INPUT_BYTES", 8)
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
        _session_images.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    source = URLSource(url="https://images.invalid/redirect", media_type="image/png")
    if oversized:
        with pytest.raises(ValueError, match="byte limit"):
            await _session_images._image_bytes(_step(tmp_path), source)
        assert stream.read_count == 3
    else:
        assert await _session_images._image_bytes(_step(tmp_path), source) == b"12345678"
        assert stream.read_count == 2
    assert calls == ["/redirect", "/image"]
    assert stream.closed


@pytest.mark.asyncio
async def test_resource_registration_accepts_narrow_target_scope(tmp_path):
    step = _step(tmp_path, _allowed_paths=[f"resource/{_DAY}"])
    step.config_value = lambda _key: "resource"
    data = png_bytes()
    digest = hashlib.sha256(data).hexdigest()

    path = await _session_images._register_resource(step, _DAY, digest, data, "image/png")

    assert path == f"resource/{_DAY}/_session_images/{digest}.png"
    assert (tmp_path / path).read_bytes() == data


@pytest.mark.asyncio
async def test_resource_registration_rejects_hash_collision_without_overwrite(tmp_path):
    step = _step(tmp_path)
    step.config_value = lambda _key: "resource"
    data = png_bytes()
    digest = hashlib.sha256(data).hexdigest()
    target = tmp_path / "resource" / _DAY / "_session_images" / f"{digest}.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user-owned-file")

    with pytest.raises(ValueError, match="content hash"):
        await _session_images._register_resource(step, _DAY, digest, data, "image/png")

    assert target.read_bytes() == b"user-owned-file"


@pytest.mark.asyncio
async def test_http_redirect_count_is_bounded(tmp_path, monkeypatch):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(302, headers={"location": "/next"})

    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        _session_images.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=transport, **kwargs),
    )
    with pytest.raises(httpx.TooManyRedirects):
        await _session_images._image_bytes(
            _step(tmp_path),
            URLSource(url="https://images.invalid/redirect", media_type="image/png"),
        )
    assert len(calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("resource_layout", ["default", "nested", "absolute", "symlink", "scoped", "index-denied"])
async def test_resource_mode_batches_real_job_and_reuses_user_edited_card(auto_resource_env, resource_layout):
    env = auto_resource_env
    env.app_context.registry = R
    if resource_layout == "nested":
        env.app_context.app_config.resource_dir = "owned/images"
    elif resource_layout == "absolute":
        env.app_context.app_config.resource_dir = str(env.workspace / "assets")
    elif resource_layout == "symlink":
        (env.workspace / "storage").mkdir()
        (env.workspace / "resource").symlink_to(env.workspace / "storage", target_is_directory=True)
    model = StructuredVisionModel(content={"name": "visible-card", "description": "A square", "caption": "Caption 482"})
    job = BaseJob(
        name="auto_resource",
        app_context=env.app_context,
        steps=[
            {
                "backend": "auto_resource_step",
                "dispatch_steps": [{"backend": "auto_image_resource_step", "file_store": env.file_store}],
            },
        ],
    )
    await job.start()
    calls = []

    async def run_resources(**kwargs):
        calls.append(kwargs)
        return await job(**kwargs)

    env.app_context.jobs["auto_resource"] = run_resources
    data = [png_bytes(color=(250, 10, 10)), png_bytes(color=(10, 250, 10))]
    message = Msg(
        name="user",
        role="user",
        metadata={"user_owned": [1, "keep"]},
        content=[
            TextBlock(text="Before"),
            DataBlock(id="duplicate", source=_source(data[0])),
            DataBlock(id="duplicate", source=_source(data[1])),
            DataBlock(id="duplicate", source=_source(data[0])),
            TextBlock(text="After"),
        ],
    )
    before = copy.deepcopy(message.model_dump())

    def memory_step():
        step = AutoMemoryStep(app_context=env.app_context, file_store=env.file_store, as_llm=model, language="en")
        step.context = RuntimeContext()
        if resource_layout in ("scoped", "index-denied"):
            step.context.data["_allowed_paths"] = [f"resource/{_DAY}", f"daily/{_DAY}"]
            if resource_layout == "scoped":
                step.context.data["_allowed_paths"].append(f"daily/{_DAY}.md")
        return step

    try:
        first = memory_step()
        if resource_layout == "index-denied":
            with pytest.raises(RuntimeError, match="PermissionError"):
                await _session_images.prepare_image_messages(first, [message], _DAY, "resource")
            assert not calls
            assert not model.structured_calls
            assert not (env.workspace / "daily" / f"{_DAY}.md").exists()
            assert message.model_dump() == before
            return
        prepared = await _session_images.prepare_image_messages(first, [message], _DAY, "resource")
        assert len(calls) == 1
        assert len(calls[0]["changes"]) == 2
        assert len(model.structured_calls) == 2
        assert len(first.context.response.metadata["auto_memory_images"]["notes"]) == 2
        assert [block.type for block in prepared[0].content] == ["text"] * 5
        assert prepared[0].content[1].text == prepared[0].content[3].text
        assert "Image note: [[daily/" in prepared[0].content[1].text
        assert message.model_dump() == before
        resources = [
            env.workspace / path for path in first.context.response.metadata["auto_memory_images"]["resources"]
        ]
        assert {path.read_bytes() for path in resources} == set(data)
        assert all(path.stem == hashlib.sha256(path.read_bytes()).hexdigest() for path in resources)

        note = env.workspace / first.context.response.metadata["auto_memory_images"]["notes"][0]
        note.write_text(note.read_text(encoding="utf-8") + "\nUser correction: 483\n", encoding="utf-8")
        second = await _session_images.prepare_image_messages(memory_step(), [message], _DAY, "resource")
        assert "User correction: 483" in second[0].content[1].text
        assert len(calls) == 1
        assert len(model.structured_calls) == 2
        assert message.model_dump() == before
    finally:
        await job.close()
