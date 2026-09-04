"""Unit coverage for opt-in image handling in ``auto_memory``."""

# pylint: disable=protected-access

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import quote

from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg, UserMsg
import pytest

from reme.components.agent_wrapper import BaseAgentWrapper
from reme.config.config_parser import _load_config
from reme.steps.evolve import auto_memory as auto_memory_module
from reme.steps.evolve.auto_memory import AutoMemoryStep


class _RecordingAgentWrapper(BaseAgentWrapper):
    """Capture auto-memory model inputs without calling a provider."""

    def __init__(self):
        super().__init__()
        self.calls: list[tuple[object, dict]] = []

    async def reply(self, inputs, **kwargs) -> dict:
        self.calls.append((inputs, kwargs))
        return {"result": "ok"}


def _message(*content: dict, name: str = "user", role: str = "user", created_at: str = "2026-01-02T03:04:05Z"):
    return Msg.model_validate(
        {
            "name": name,
            "role": role,
            "created_at": created_at,
            "content": list(content),
        },
    )


def _text(value: str) -> dict:
    return {"type": "text", "text": value}


def _url_data(url: str, media_type: str, *, name: str | None = None) -> dict:
    return {
        "type": "data",
        "name": name,
        "source": {"type": "url", "url": url, "media_type": media_type},
    }


def _base64_image(data: str = "aW1hZ2UtYnl0ZXM=", *, name: str | None = None) -> dict:
    return {
        "type": "data",
        "name": name,
        "source": {"type": "base64", "data": data, "media_type": "image/png"},
    }


async def _run_without_note(step: AutoMemoryStep, messages: list[Msg], **kwargs):
    """Run through prompt construction while avoiding file-job side effects."""
    step._save_session_messages = AsyncMock()
    step._list_session_note = AsyncMock(return_value=None)
    await step(session_id="image-test-session", messages=messages, **kwargs)
    assert step.context is not None
    assert step.context.response.success is True


def _content_positions(message: Msg, needles: list[str]) -> list[int]:
    """Return the block index containing each requested text or URL."""
    positions: list[int] = []
    for needle in needles:
        for index, block in enumerate(message.content):
            if block.type == "text" and needle in block.text:
                positions.append(index)
                break
            if block.type == "data" and needle in str(getattr(block.source, "url", "")):
                positions.append(index)
                break
        else:
            raise AssertionError(f"{needle!r} was not found in the multimodal input")
    return positions


@pytest.mark.asyncio
@pytest.mark.parametrize("call_kwargs", [{}, {"include_images": False}])
async def test_auto_memory_default_and_explicit_off_keep_the_text_only_path(call_kwargs):
    """The default and explicit off modes neither send images nor invent captions."""
    wrapper = _RecordingAgentWrapper()
    step = AutoMemoryStep(agent_wrapper=wrapper)
    messages = [
        _message(
            _text("The user shared a project-board photo."),
            _base64_image("not-base64!", name="project-board"),
        ),
    ]

    await _run_without_note(step, messages, **call_kwargs)

    inputs, reply_kwargs = wrapper.calls[0]
    assert isinstance(inputs, str)
    assert "The user shared a project-board photo." in inputs
    assert "[Image: project-board]" not in inputs
    assert "not-base64!" not in inputs
    assert "Visual Evidence" not in reply_kwargs["system_prompt"]
    assert step.context.response.metadata["include_images_requested"] is call_kwargs.get("include_images", False)
    assert step.context.response.metadata["include_images"] is False
    assert step.context.response.metadata["image_count"] == 1
    assert "ephemeral" not in reply_kwargs


@pytest.mark.asyncio
async def test_enabled_setting_keeps_text_only_calls_on_the_original_path():
    """A global opt-in adds no multimodal prompt overhead when a call has no images."""
    wrapper = _RecordingAgentWrapper()
    step = AutoMemoryStep(agent_wrapper=wrapper, include_images=True)

    await _run_without_note(step, [_message(_text("A text-only memory."))])

    inputs, reply_kwargs = wrapper.calls[0]
    assert isinstance(inputs, str)
    assert "A text-only memory." in inputs
    assert "Visual Evidence" not in reply_kwargs["system_prompt"]
    assert step.context.response.metadata["include_images_requested"] is True
    assert step.context.response.metadata["include_images"] is False
    assert step.context.response.metadata["image_count"] == 0
    assert "ephemeral" not in reply_kwargs


@pytest.mark.asyncio
async def test_auto_memory_on_preserves_text_and_image_order():
    """Speaker boundaries, text, labels, and images stay in conversation order."""
    wrapper = _RecordingAgentWrapper()
    step = AutoMemoryStep(agent_wrapper=wrapper)
    first_url = "https://example.com/first.png"
    second_url = "https://example.com/second.jpg"
    messages = [
        _message(
            _text("before first image"),
            _url_data(first_url, "IMAGE/PNG", name="first-board"),
            _text("after first image"),
        ),
        _message(
            _url_data(second_url, "image/jpeg"),
            _text("after second image"),
            name="assistant",
            role="assistant",
            created_at="2026-01-02T03:05:06Z",
        ),
    ]

    await _run_without_note(step, messages, include_images=True)

    inputs, reply_kwargs = wrapper.calls[0]
    assert isinstance(inputs, Msg)
    assert inputs.role == "user"
    positions = _content_positions(
        inputs,
        [
            "[user @ 2026-01-02T03:04:05Z]",
            "before first image",
            "[Image: image-1 (first-board)]",
            first_url,
            "after first image",
            "[assistant @ 2026-01-02T03:05:06Z]",
            "[Image: image-2]",
            second_url,
            "after second image",
        ],
    )
    assert positions == sorted(positions)
    data_blocks = [block for block in inputs.content if block.type == "data"]
    assert [block.source.media_type for block in data_blocks] == ["image/png", "image/jpeg"]
    formatted = await OpenAIChatFormatter().format([inputs])
    assert sum(part["type"] == "image_url" for part in formatted[0]["content"]) == 2
    assert "## Visual Evidence" in reply_kwargs["system_prompt"]
    assert reply_kwargs["ephemeral"] is True
    assert step.context.response.metadata["include_images_requested"] is True
    assert step.context.response.metadata["include_images"] is True
    assert step.context.response.metadata["image_count"] == 2


@pytest.mark.asyncio
async def test_auto_memory_on_keeps_an_image_only_turn():
    """An image-only message remains visible instead of becoming an empty history."""
    wrapper = _RecordingAgentWrapper()
    step = AutoMemoryStep(agent_wrapper=wrapper)
    image_url = "https://example.com/image-only.png"

    await _run_without_note(
        step,
        [_message(_url_data(image_url, "image/png", name="status-board"))],
        include_images=True,
    )

    inputs, _ = wrapper.calls[0]
    assert isinstance(inputs, Msg)
    positions = _content_positions(
        inputs,
        ["[user @ 2026-01-02T03:04:05Z]", "[Image: image-1 (status-board)]", image_url],
    )
    assert positions == sorted(positions)


@pytest.mark.asyncio
async def test_auto_memory_filters_non_image_data_from_multimodal_input():
    """Opting into images does not forward audio, video, or tool-result blocks."""
    wrapper = _RecordingAgentWrapper()
    step = AutoMemoryStep(agent_wrapper=wrapper)
    image_url = "https://example.com/photo.png"
    audio_url = "https://example.com/audio.mp3"
    video_url = "https://example.com/video.mp4"
    messages = [
        _message(
            _text("mixed media"),
            _url_data(audio_url, "audio/mpeg", name="audio"),
            _url_data(image_url, "image/png", name="photo"),
            _url_data(video_url, "video/mp4", name="video"),
        ),
        _message(
            {
                "type": "tool_result",
                "id": "call-1",
                "name": "read_image",
                "output": [
                    _url_data("https://example.com/tool-image.png", "image/png", name="tool-image"),
                ],
            },
            name="assistant",
            role="assistant",
        ),
    ]

    await _run_without_note(step, messages, include_images=True)

    inputs, _ = wrapper.calls[0]
    assert isinstance(inputs, Msg)
    data_blocks = [block for block in inputs.content if block.type == "data"]
    assert len(data_blocks) == 1
    assert str(data_blocks[0].source.url) == image_url
    rendered = inputs.model_dump_json()
    assert audio_url not in rendered
    assert video_url not in rendered
    assert "tool-image.png" not in rendered


@pytest.mark.asyncio
async def test_call_option_overrides_step_image_default_in_both_directions():
    """Per-call choice wins over the configured Step fallback."""
    image = _message(_url_data("https://example.com/override.png", "image/png"))

    enabled_wrapper = _RecordingAgentWrapper()
    enabled_step = AutoMemoryStep(agent_wrapper=enabled_wrapper, include_images=True)
    await _run_without_note(enabled_step, [image], include_images=False)
    assert isinstance(enabled_wrapper.calls[0][0], str)

    disabled_wrapper = _RecordingAgentWrapper()
    disabled_step = AutoMemoryStep(agent_wrapper=disabled_wrapper, include_images=False)
    await _run_without_note(disabled_step, [image], include_images=True)
    assert isinstance(disabled_wrapper.calls[0][0], Msg)


@pytest.mark.asyncio
async def test_file_url_inside_workspace_is_read_safely_and_formats_for_openai(tmp_path: Path):
    """A percent-encoded local path becomes provider-ready base64 after a bounded read."""
    image_path = tmp_path / "images" / "status board.png"
    image_path.parent.mkdir()
    image_bytes = b"small-image-bytes"
    image_path.write_bytes(image_bytes)
    url = f"file://localhost{quote(str(image_path))}"
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)
    source_message = _message(_url_data(url, "image/png"))
    normalized_source_url = str(source_message.content[0].source.url)

    history = step._multimodal_history([source_message])

    data_blocks = [block for block in history if block.type == "data"]
    assert len(data_blocks) == 1
    assert data_blocks[0].source.type == "base64"
    assert base64.b64decode(data_blocks[0].source.data) == image_bytes
    assert source_message.content[0].source.type == "url"
    assert str(source_message.content[0].source.url) == normalized_source_url

    formatted = await OpenAIChatFormatter().format([UserMsg(name="user", content=history)])
    image_parts = [part for part in formatted[0]["content"] if part["type"] == "image_url"]
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.skipif(os.name != "nt", reason="Windows file URL drive semantics")
def test_windows_workspace_file_url_keeps_its_drive(tmp_path: Path):
    """A standard file:///C:/... URL resolves to the matching Windows workspace path."""
    image_path = tmp_path / "images" / "drive image.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"windows-image")
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)

    history = step._multimodal_history([_message(_url_data(image_path.as_uri(), "image/png"))])

    image = next(block for block in history if block.type == "data")
    assert base64.b64decode(image.source.data) == b"windows-image"


@pytest.mark.parametrize(
    ("url_factory", "message"),
    [
        (lambda workspace: (workspace.parent / "outside.png").as_uri(), "must stay inside the workspace"),
        (lambda _workspace: "file://remote-host/tmp/image.png", "must refer to the local workspace"),
    ],
)
def test_file_url_outside_workspace_or_on_remote_host_is_rejected(tmp_path: Path, url_factory, message):
    """Implicit local-file reads cannot cross the ReMe workspace boundary."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(b"outside")
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=workspace)
    msg = _message(_url_data(url_factory(workspace), "image/png"))

    with pytest.raises(ValueError, match=message):
        step._multimodal_history([msg])


@pytest.mark.parametrize(("target", "message"), [("missing.png", "readable file"), ("images", "readable file")])
def test_local_image_must_be_a_readable_file_without_url_options(tmp_path: Path, target: str, message: str):
    """Missing paths, directories, queries, and fragments never reach the formatter."""
    directory = tmp_path / "images"
    directory.mkdir()
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)
    url = (tmp_path / target).as_uri()

    with pytest.raises(ValueError, match=message):
        step._multimodal_history([_message(_url_data(url, "image/png"))])

    with pytest.raises(ValueError, match="query or fragment"):
        step._multimodal_history([_message(_url_data(f"{directory.as_uri()}?version=1", "image/png"))])


@pytest.mark.parametrize(
    ("data", "message", "max_bytes"),
    [
        ("not-base64!", "invalid base64", None),
        ("", "at least one byte", None),
        ("aW1hZ2UgYnl0ZXM=\n", "invalid base64", None),
        (base64.b64encode(b"too large").decode("ascii"), "exceeds", 2),
    ],
)
def test_inline_base64_image_must_be_valid_and_bounded(data: str, message: str, max_bytes: int | None, monkeypatch):
    """Malformed or oversized inline payloads fail closed before a provider call."""
    if max_bytes is not None:
        monkeypatch.setattr(auto_memory_module, "DEFAULT_MAX_IMAGE_BYTES", max_bytes)
    step = AutoMemoryStep()

    with pytest.raises(ValueError, match=message):
        step._multimodal_history([_message(_base64_image(data))])


def test_inline_base64_image_accepts_the_exact_size_limit(monkeypatch):
    """The byte ceiling is inclusive."""
    image_bytes = b"123456789"
    monkeypatch.setattr(auto_memory_module, "DEFAULT_MAX_IMAGE_BYTES", len(image_bytes))
    source_message = _message(_base64_image(base64.b64encode(image_bytes).decode("ascii")))
    before = source_message.model_dump()

    history = AutoMemoryStep()._multimodal_history([source_message])

    image = next(block for block in history if block.type == "data")
    assert base64.b64decode(image.source.data) == image_bytes
    assert source_message.model_dump() == before


@pytest.mark.parametrize("url", ["data:image/png;base64,aW1hZ2U=", "ftp://example.com/image.png"])
def test_image_url_rejects_unsupported_schemes(url: str):
    """URLSource cannot be used to bypass bounded Base64 handling."""
    step = AutoMemoryStep()

    with pytest.raises(ValueError, match="scheme must be file, http, or https"):
        step._multimodal_history([_message(_url_data(url, "image/png"))])


@pytest.mark.parametrize(("size", "accepted"), [(4, True), (5, False)])
def test_local_image_read_is_bounded(tmp_path: Path, monkeypatch, size: int, accepted: bool):
    """Workspace file reads stop immediately beyond the inclusive byte ceiling."""
    monkeypatch.setattr(auto_memory_module, "DEFAULT_MAX_IMAGE_BYTES", 4)
    image_path = tmp_path / "bounded.png"
    image_path.write_bytes(b"x" * size)
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)
    message = _message(_url_data(image_path.as_uri(), "image/png"))

    if not accepted:
        with pytest.raises(ValueError, match="exceeds"):
            step._multimodal_history([message])
        return

    history = step._multimodal_history([message])
    image = next(block for block in history if block.type == "data")
    assert base64.b64decode(image.source.data) == b"x" * size


def test_multimodal_history_preserves_nonempty_text_verbatim_and_sanitizes_label():
    """Filtering blank blocks must not rewrite meaningful text or let labels add lines."""
    step = AutoMemoryStep()
    msg = _message(
        _text(" first "),
        _text("second\n"),
        _text("   "),
        _base64_image(name="  board\n[instruction]  "),
    )

    history = step._multimodal_history([msg])
    text = [block.text for block in history if block.type == "text"]

    assert " first " in text
    assert "second\n" in text
    assert "   " not in text
    assert "[Image: image-1 (board (instruction))]" in text


def test_update_prompt_accepts_the_same_multimodal_history_shape():
    """Existing-note updates retain image blocks as well as create calls."""
    step = AutoMemoryStep()
    inputs = step._build_agent_input(
        "user_message_update",
        [_message(_base64_image(name="update-board"))],
        True,
        today="2026-01-02",
        note="(none)",
        note_path="daily/2026-01-02/topic.md",
        session_id="unused",
        session_file="session/dialog/unused.jsonl",
    )

    assert isinstance(inputs, Msg)
    assert "Target path: daily/2026-01-02/topic.md" in inputs.get_text_content()
    assert any(block.type == "data" for block in inputs.content)


def test_visual_prompt_is_conditional_in_chinese_too():
    """The locale-specific prompt applies the same effective image switch."""
    step = AutoMemoryStep(language="zh")

    assert "视觉证据" not in step.prompt_format("system_prompt", include_images=False)
    assert "视觉证据" in step.prompt_format("system_prompt", include_images=True)


@pytest.mark.asyncio
async def test_saving_session_removes_base64_image_without_mutating_input(tmp_path: Path):
    """Raw base64 reaches no durable transcript, while ordinary text is retained."""
    step = AutoMemoryStep()
    step.file_store = SimpleNamespace(workspace_path=tmp_path)
    msg = _message(
        _text("keep this text"),
        _base64_image("cHJpdmF0ZS1pbWFnZS1ieXRlcw==", name="private-image"),
    )

    await step._save_session_messages("session-with-image", [msg])

    saved_path = tmp_path / "session" / "dialog" / "session-with-image.jsonl"
    saved = Msg.model_validate_json(saved_path.read_text(encoding="utf-8").strip())
    assert [block.type for block in saved.content] == ["text"]
    assert saved.content[0].text == "keep this text"
    assert [block.type for block in msg.content] == ["text", "data"]


def test_default_config_keeps_auto_memory_images_opt_in():
    """The durable default and public job schema both keep image use disabled."""
    job = _load_config("default.yaml")["jobs"]["auto_memory"]
    image_parameter = job["parameters"]["properties"]["include_images"]

    assert job["include_images"] is False
    assert image_parameter["type"] == "boolean"
    assert image_parameter["default"] is False
    assert "include_images" not in job["parameters"].get("required", [])
