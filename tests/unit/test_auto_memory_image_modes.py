"""Opt-in image preprocessing must leave the upstream session transcript intact."""

# pylint: disable=protected-access,missing-function-docstring

import asyncio
import base64
import copy
import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from agentscope.message import Msg
from agentscope.model import ChatModelBase
from PIL import Image
import pytest

from reme.components.agent_wrapper import BaseAgentWrapper
from reme.components.file_store import LocalFileStore
from reme.components import R
from reme.components.job import BaseJob
from reme.components.prompt_handler import PromptHandler
from reme.components.runtime_context import RuntimeContext
from reme.schema import ApplicationConfig
from reme.steps.evolve import _auto_memory_image, _image_caption
from reme.steps.evolve.auto_image_resource import AutoImageResourceStep
from reme.steps.evolve.auto_memory import AutoMemoryStep

_DAY = "2026-09-01"
_SESSION = "image-modes"
_CAPTION = "A blue circle beside the visible label RIVER482."


def _png(color=(20, 40, 220)):
    with Image.new("RGB", (8, 8), color) as image:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def _image_block(data=None, block_id="shared-image-id"):
    return {
        "type": "data",
        "id": block_id,
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.b64encode(_png() if data is None else data).decode("ascii"),
        },
    }


def _message(message_id="message-1", created_at=f"{_DAY}T10:00:00", *, images=True):
    content = [{"type": "text", "text": "Remember this observation."}]
    if images:
        # Two different images deliberately use the same block ID. Image
        # preprocessing must operate on positions without rewriting the source.
        content.extend([_image_block(), _image_block(_png((220, 40, 20)))])
    content.extend(
        [
            {
                "type": "tool_call",
                "id": "recall-1",
                "name": "memory_search",
                "input": "{}",
            },
            {
                "type": "tool_result",
                "id": "recall-1",
                "name": "memory_search",
                "output": "TOOL_RESULT_MUST_NOT_BE_SAVED",
            },
            {
                "type": "data",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": "YWJj",
                },
            },
            {
                "type": "data",
                "source": {
                    "type": "url",
                    "media_type": "application/pdf",
                    "url": "https://example.invalid/user-document.pdf",
                },
            },
        ],
    )
    return Msg.model_validate(
        {
            "id": message_id,
            "name": "assistant",
            "role": "assistant",
            "created_at": created_at,
            "content": content,
            "metadata": {"user_owned": {"nested": ["keep", 7]}},
        },
    )


def _main_saved_line(message):
    """Independent oracle for main's unchanged source serialization contract."""
    blocks = [
        block
        for block in message.content
        if block.type != "tool_result"
        and not (block.type == "data" and getattr(block.source, "type", None) == "base64")
    ]
    return (message.model_copy(update={"content": blocks}).model_dump_json() + "\n").encode("utf-8")


class _MemoryWrapper(BaseAgentWrapper):
    """Capture the real memory prompt without invoking an external model."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.error: Exception | None = None

    async def reply(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        if isinstance(self.error, Exception):
            raise self.error  # pylint: disable=raising-bad-type
        return {"result": "ok"}


class _VisionModel(ChatModelBase):
    """Fail after a chosen number of successful unique-image descriptions."""

    def __init__(self):
        self.calls = []
        self.error: BaseException | None = None
        self.succeed_before_failure = 0

    async def generate_structured_output(self, messages, structured_model, **kwargs):
        del structured_model, kwargs
        self.calls.append(messages)
        if self.error and len(self.calls) > self.succeed_before_failure:
            raise self.error  # pylint: disable=raising-bad-type
        return SimpleNamespace(content={"name": "blue-circle", "description": "A circle.", "caption": _CAPTION})

    async def __call__(self, messages, **kwargs):
        del kwargs
        self.calls.append(messages)
        if self.error:
            raise self.error  # pylint: disable=raising-bad-type
        return SimpleNamespace(content=[{"type": "text", "text": _CAPTION}])


class _Harness:
    """Real main session IO, mocked models, and no resource job configuration."""

    def __init__(self, workspace, monkeypatch):
        self.workspace = workspace
        self.monkeypatch = monkeypatch
        self.store = LocalFileStore(name="image_modes", embedding_store="")
        self.wrapper = _MemoryWrapper()
        self.vision = _VisionModel()
        self.logger = MagicMock()
        self.app_context = SimpleNamespace(
            registry=R,
            metadata={},
            app_config=ApplicationConfig(workspace_dir=str(workspace)),
            jobs={},
        )

    @property
    def session_path(self):
        return self.workspace / "session" / "dialog" / f"{_SESSION}.jsonl"

    async def no_note(self, _day, _session_id):
        return None

    def step(self, **kwargs):
        options = {
            "app_context": self.app_context,
            "file_store": self.store,
            "agent_wrapper": self.wrapper,
            "as_llm": self.vision,
            **kwargs,
        }
        step = AutoMemoryStep(**options)
        step.logger = self.logger
        self.monkeypatch.setattr(step, "_list_session_note", self.no_note)
        return step


@pytest.fixture(name="harness")
def image_modes_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return _Harness(tmp_path, monkeypatch)


async def _invoke(harness, messages, *, enabled=False, **kwargs):
    step = harness.step()
    await step(session_id=_SESSION, date=_DAY, messages=messages, include_images=enabled, **kwargs)
    return step.context.response


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_on_off_preserve_main_jsonl_bytes_and_caller_messages(harness, enabled):
    message = _message()
    before = copy.deepcopy(message.model_dump())

    response = await _invoke(harness, [message], enabled=enabled)

    assert response.success is True
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    assert message.model_dump() == before
    saved = Msg.model_validate_json(harness.session_path.read_text(encoding="utf-8"))
    assert [block.type for block in saved.content] == ["text", "tool_call", "data"]
    assert saved.metadata == message.metadata
    assert _CAPTION not in harness.session_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("history", ["append", "backfill", "same-id", "replace-and-backfill"])
async def test_history_merge_keeps_main_append_and_rewrite_contract(harness, enabled, history):
    original = _message()
    await _invoke(harness, [original], enabled=enabled)
    original_bytes = harness.session_path.read_bytes()
    replacement = original.model_copy(deep=True)
    replacement.content[0].text = "Updated same-ID observation."
    older = _message("older", f"{_DAY}T09:00:00", images=False)
    later = _message("later", f"{_DAY}T11:00:00", images=False)
    if history == "append":
        messages, expected = [original, later], original_bytes + _main_saved_line(later)
    elif history == "backfill":
        messages, expected = [older, original], _main_saved_line(older) + _main_saved_line(original)
    elif history == "same-id":
        messages, expected = [replacement], original_bytes
    else:
        messages, expected = [older, replacement], _main_saved_line(older) + _main_saved_line(replacement)
    before = [copy.deepcopy(message.model_dump()) for message in messages]

    response = await _invoke(harness, messages, enabled=enabled)

    assert response.success is True
    assert harness.session_path.read_bytes() == expected
    assert [message.model_dump() for message in messages] == before


@pytest.mark.asyncio
async def test_caption_only_replaces_image_positions_without_writing_resources(harness):
    message = _message()
    before = message.model_dump()
    step = harness.step()
    step.context = RuntimeContext()
    messages = [message]

    prepared, applied = await _auto_memory_image.prepare_image_messages(step, messages, _DAY)

    assert applied is True
    assert prepared is not messages
    assert prepared[0] is not message
    assert message.model_dump() == before
    for index, block in enumerate(message.content):
        if index in (1, 2):
            assert prepared[0].content[index].type == "text"
            assert _CAPTION in prepared[0].content[index].text
            assert "Caption (model-generated):" in prepared[0].content[index].text
            assert "Image note:" not in prepared[0].content[index].text
            assert "Image resource:" not in prepared[0].content[index].text
            assert "[[" not in prepared[0].content[index].text
        else:
            assert prepared[0].content[index] == block
    assert prepared[0].metadata == message.metadata
    assert prepared[0].id == message.id
    assert prepared[0].created_at == message.created_at
    assert len(harness.vision.calls) == 2
    assert not (harness.workspace / "resource").exists()
    assert not (harness.workspace / "daily").exists()
    assert not (harness.workspace / "session").exists()


@pytest.mark.asyncio
async def test_user_file_image_keeps_original_url_and_only_replaces_prompt(harness):
    source = harness.workspace / "user-owned-secret-name.png"
    source.write_bytes(_png())
    message = _message()
    message.content[1].source = (
        Msg.model_validate(
            {
                "name": "user",
                "role": "user",
                "content": [
                    {
                        "type": "data",
                        "source": {
                            "type": "url",
                            "url": source.as_uri(),
                            "media_type": "image/png",
                        },
                    },
                ],
            },
        )
        .content[0]
        .source
    )
    before = copy.deepcopy(message.model_dump())

    response = await _invoke(harness, [message], enabled=True)

    assert response.success is True
    assert _CAPTION in harness.wrapper.calls[0][0]
    assert message.model_dump() == before
    assert source.read_bytes() == _png()
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    assert "user-owned-secret-name" not in harness.vision.calls[0][0].get_text_content()
    assert "file://" not in harness.vision.calls[0][0].get_text_content()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_zero_image_messages_do_not_decode_or_resolve_vision(harness, monkeypatch, enabled):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Image dependencies must stay unused for a text-only session")

    monkeypatch.setattr(_image_caption, "_load_pillow", forbidden)
    monkeypatch.setattr(_auto_memory_image, "resolve_vision_model", forbidden)
    message = _message(images=False)

    response = await _invoke(harness, [message], enabled=enabled)

    assert response.success is True
    assert harness.wrapper.calls
    assert not harness.vision.calls
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
async def test_default_off_ignores_even_invalid_image_bytes_and_unused_mode(harness, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Disabled image processing must not touch image dependencies")

    monkeypatch.setattr(_image_caption, "_load_pillow", forbidden)
    monkeypatch.setattr(_auto_memory_image, "resolve_vision_model", forbidden)
    message = _message()
    message.content[1].source.data = "not-base64"
    step = harness.step()

    await step(session_id=_SESSION, date=_DAY, messages=[message], image_mode="resource")

    assert step.context.response.success is True
    assert len(harness.wrapper.calls) == 1
    assert not harness.vision.calls
    assert "auto_memory_images" not in step.context.response.metadata
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("enable_tags", [False, True])
async def test_image_switch_preserves_upstream_tag_prompt(harness, enabled, enable_tags):
    step = harness.step(enable_tags=enable_tags)
    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=enabled)

    assert step.context.response.success is True
    prompt, kwargs = harness.wrapper.calls[0]
    assert ("`tags`" in kwargs["system_prompt"]) is enable_tags
    assert ('metadata={"tags"' in prompt) is enable_tags
    assert kwargs["job_tools"] == ["daily_write"]
    assert "injected_job_kwargs" not in kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_options", "call_options", "enabled"),
    [
        ({}, {}, False),
        ({}, {"include_images": True}, True),
        ({"include_images": True}, {}, True),
        ({"include_images": True}, {"include_images": False}, False),
        ({"include_images": False}, {"include_images": True}, True),
        (
            {"include_images": True, "image_mode": "resource"},
            {"image_mode": "caption-only"},
            True,
        ),
    ],
)
async def test_call_options_override_step_image_configuration(harness, step_options, call_options, enabled):
    step = harness.step(**step_options)
    await step(session_id=_SESSION, date=_DAY, messages=[_message()], **call_options)

    assert step.context.response.success is True
    assert (_CAPTION in harness.wrapper.calls[0][0]) is enabled
    assert bool(harness.vision.calls) is enabled


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_enabled", "job_options", "call_options", "enabled"),
    [
        (False, {}, {}, False),
        (True, {}, {}, True),
        (False, {"include_images": True}, {}, True),
        (True, {"include_images": False}, {}, False),
        (False, {"include_images": True}, {"include_images": False}, False),
        (True, {"include_images": False}, {"include_images": True}, True),
    ],
)
async def test_real_base_job_merges_call_job_and_step_switches(
    harness,
    monkeypatch,
    step_enabled,
    job_options,
    call_options,
    enabled,
):
    async def no_note(_step, _day, _session_id):
        return None

    monkeypatch.setattr(AutoMemoryStep, "_list_session_note", no_note)
    job = BaseJob(
        app_context=harness.app_context,
        steps=[
            {
                "backend": "auto_memory_step",
                "file_store": harness.store,
                "agent_wrapper": harness.wrapper,
                "as_llm": harness.vision,
                "include_images": step_enabled,
            },
        ],
        **job_options,
    )
    await job.start()
    try:
        response = await job(session_id=_SESSION, date=_DAY, messages=[_message()], **call_options)
    finally:
        await job.close()

    assert response.success is True
    assert (_CAPTION in harness.wrapper.calls[0][0]) is enabled
    assert bool(harness.vision.calls) is enabled


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["resource", "caption_only", "", None, False])
async def test_enabled_unsupported_mode_is_configuration_error_not_fallback(harness, mode):
    step = harness.step()
    with pytest.raises(ValueError, match="image_mode"):
        await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True, image_mode=mode)
    assert not harness.vision.calls
    assert not harness.wrapper.calls
    assert "auto_memory_images" not in step.context.response.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["true", 1, None])
async def test_non_boolean_switch_is_configuration_error(harness, value):
    with pytest.raises(ValueError, match="include_images"):
        await _invoke(harness, [_message()], enabled=value)
    assert not harness.wrapper.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["source", "decode", "model", "caption"])
async def test_image_failure_warns_and_runs_unchanged_text_memory(harness, monkeypatch, failure):
    message = _message()
    if failure == "source":
        message.content[1].source.data = "bad-base64"
    elif failure == "decode":
        message.content[1].source.data = base64.b64encode(b"not an image").decode()
    elif failure == "model":
        monkeypatch.setattr(_auto_memory_image, "resolve_vision_model", lambda _step: None)
    else:
        harness.vision.error = RuntimeError("provider unavailable")
    before = copy.deepcopy(message.model_dump())

    response = await _invoke(harness, [message], enabled=True)

    assert response.success is True
    assert len(harness.wrapper.calls) == 1
    assert _CAPTION not in harness.wrapper.calls[0][0]
    assert "Remember this observation." in harness.wrapper.calls[0][0]
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    metadata = response.metadata["auto_memory_images"]
    assert metadata["mode"] == "caption-only"
    assert metadata["status"] == "fallback"
    assert metadata["image_count"] == 2
    assert metadata["captioned_images"] == 0
    assert ":" in metadata["reason"]
    assert harness.logger.warning.called


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["source", "caption"])
async def test_later_failure_discards_all_partial_caption_enrichment(harness, failure):
    message = _message()
    if failure == "source":
        message.content[2].source.data = "invalid-second-image"
    else:
        harness.vision.error = RuntimeError("second caption failed")
        harness.vision.succeed_before_failure = 1
    step = harness.step()
    step.context = RuntimeContext()
    messages = [message]
    before = copy.deepcopy(message.model_dump())

    prepared, applied = await _auto_memory_image.prepare_image_messages(step, messages, _DAY)

    assert prepared is messages
    assert applied is False
    assert message.model_dump() == before
    assert _CAPTION not in prepared[0].get_text_content()
    metadata = step.context.response.metadata["auto_memory_images"]
    assert metadata["status"] == "fallback"
    assert metadata["captioned_images"] == 1
    assert metadata["image_count"] == 2


@pytest.mark.asyncio
async def test_warning_and_metadata_never_include_provider_error_secrets(harness):
    secret = "FAKE_PROVIDER_TOKEN_8c219"
    harness.vision.error = RuntimeError(f"https://user:{secret}@images.invalid/x?api_key={secret}")

    response = await _invoke(harness, [_message()], enabled=True)

    assert response.success is True
    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    warnings = "\n".join(str(call) for call in harness.logger.warning.call_args_list)
    assert warnings
    assert secret not in warnings
    assert secret not in str(response.metadata)
    assert secret not in response.answer
    assert "images.invalid" not in warnings


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["source", "caption"])
async def test_cancellation_is_not_converted_into_successful_text_fallback(harness, monkeypatch, stage):
    if stage == "caption":
        harness.vision.error = asyncio.CancelledError()
    else:

        async def cancelled(*_args, **_kwargs):
            raise asyncio.CancelledError()

        monkeypatch.setattr(_auto_memory_image, "_image_bytes", cancelled)

    with pytest.raises(asyncio.CancelledError):
        await _invoke(harness, [_message()], enabled=True)

    assert not harness.wrapper.calls
    assert not harness.logger.warning.called


@pytest.mark.asyncio
@pytest.mark.parametrize("image_fails", [False, True])
async def test_memory_agent_errors_are_not_swallowed_by_image_fallback(harness, image_fails):
    harness.wrapper.error = RuntimeError("original-memory-error")
    if image_fails:
        harness.vision.error = RuntimeError("vision-error")

    with pytest.raises(RuntimeError, match="original-memory-error"):
        await _invoke(harness, [_message()], enabled=True)

    assert len(harness.wrapper.calls) == 1


@pytest.mark.asyncio
async def test_identical_bytes_caption_once_but_preserve_repeated_ids_and_positions(harness):
    message = _message()
    message.content[2].source.data = message.content[1].source.data
    response = await _invoke(harness, [message], enabled=True)

    assert response.success is True
    assert harness.wrapper.calls[0][0].count(_CAPTION) == 2
    assert response.metadata["auto_memory_images"] == {
        "mode": "caption-only",
        "status": "completed",
        "image_count": 2,
        "captioned_images": 1,
    }
    assert len(harness.vision.calls) == 1
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    # A new call has no durable caption cache and captions again.
    await _invoke(harness, [message], enabled=True)
    assert len(harness.vision.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "zh"])
async def test_caption_uses_shared_resource_prompt_without_source_name_inference(harness, language):
    step = harness.step(language=language)
    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True)

    prompt = harness.vision.calls[0][0].get_text_content()
    expected = (
        PromptHandler(language=language)
        .load_prompt_by_class(AutoImageResourceStep)
        .prompt_format(
            "user_message",
            file_path="(inline session image; not saved)",
            filename="session-image-1",
            stem="session-image",
            date=_DAY,
        )
    )
    assert prompt == expected
    if language == "en":
        assert "Describe the attached image" in prompt
        assert "transcribe meaningful visible text verbatim" in prompt
        assert "Filename: session-image-1" in prompt
    else:
        assert "为记忆知识库描述用户资源库中的这张图像" in prompt
        assert "逐字转录有意义的可见文字" in prompt
    assert "(inline session image; not saved)" in prompt
    assert _DAY in prompt
    assert "[[resource/" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "zh"])
@pytest.mark.parametrize("scenario", ["off", "no-images", "completed", "fallback"])
async def test_caption_prompt_rules_only_apply_when_captions_were_injected(harness, language, scenario):
    step = harness.step(language=language)
    plain = step.prompt_format(
        "system_prompt",
        enable_tags=False,
        include_images=False,
    )
    if scenario == "fallback":
        harness.vision.error = RuntimeError("caption unavailable")
    await step(
        session_id=_SESSION,
        date=_DAY,
        messages=[_message(images=scenario != "no-images")],
        include_images=scenario != "off",
    )

    prompt = harness.wrapper.calls[0][1]["system_prompt"]
    if scenario == "completed":
        assert "Image note" not in harness.wrapper.calls[0][0]
        assert "model-generated" in harness.wrapper.calls[0][0]
        assert prompt != plain
        marker = (
            "No image-note or image-resource files have been created."
            if language == "en"
            else "没有创建图像笔记或原图资源文件"
        )
        assert marker in prompt
    else:
        assert prompt == plain
    for flag in ("[include_images]", "[image_resources]", "[image_captions]"):
        assert flag not in prompt
