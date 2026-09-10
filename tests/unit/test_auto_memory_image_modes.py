"""Direct-only image configuration preserves the original transcript contract."""

# pylint: disable=protected-access,missing-function-docstring

import base64
import copy
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.model import ChatModelBase
from PIL import Image
import pytest
import yaml

from reme.components.agent_wrapper import BaseAgentWrapper
from reme.components.agent_wrapper.as_agent_wrapper import AsAgentWrapper
from reme.components.as_llm import BaseAsLLM
from reme.components.file_store import LocalFileStore
from reme.components import R
from reme.components.job import BaseJob
from reme.components.tag_index import LocalTagIndex
from reme.enumeration import ComponentEnum
from reme.schema import ApplicationConfig
from reme.steps.evolve import _auto_memory_image
from reme.steps.evolve.auto_memory import AutoMemoryStep

from .test_auto_tag import _TaggingWrapper, _write_note

_DAY = "2026-09-01"
_SESSION = "image-modes"


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
        # Different images deliberately share an ID; positions identify them.
        content.extend([_image_block(), _image_block(_png((220, 40, 20)))])
    content.extend(
        [
            {"type": "tool_call", "id": "recall-1", "name": "memory_search", "input": "{}"},
            {
                "type": "tool_result",
                "id": "recall-1",
                "name": "memory_search",
                "output": "TOOL_RESULT_MUST_NOT_BE_SAVED",
            },
            {
                "type": "data",
                "source": {"type": "base64", "media_type": "application/pdf", "data": "YWJj"},
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
    """Non-AgentScope backend for disabled-image and configuration checks."""

    def __init__(self):
        super().__init__()
        self.calls = []

    async def reply(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        return {"result": "ok"}


class _DirectModel(ChatModelBase):
    """Local model with no API client."""

    def __init__(self, name="custom-memory-model"):
        self.model = name
        self.context_size = 200000
        self.formatter = OpenAIChatFormatter()


class _DirectWrapper(AsAgentWrapper):
    """Keep a real wrapper type and binding while observing the reply boundary."""

    def __init__(self):
        super().__init__(backend="agentscope")
        self.as_llm = BaseAsLLM()
        self.as_llm.model = _DirectModel()
        self.calls = []
        self.error = None

    async def reply(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        if self.error is not None:
            raise self.error
        return {"result": "ok"}


class _Harness:
    """Real session IO and an explicitly declared vision-supporting test setup."""

    def __init__(self, workspace, monkeypatch):
        self.workspace = workspace
        self.monkeypatch = monkeypatch
        self.store = LocalFileStore(name="image_modes", embedding_store="")
        self.wrapper = _DirectWrapper()
        self.logger = MagicMock()
        self.app_context = SimpleNamespace(
            registry=R,
            metadata={},
            app_config=ApplicationConfig(workspace_dir=str(workspace)),
            jobs={},
            components={ComponentEnum.AS_LLM: {"default": self.wrapper.as_llm}},
        )

    @property
    def session_path(self):
        return self.workspace / "session" / "dialog" / f"{_SESSION}.jsonl"

    async def no_note(self, _day, _session_id):
        return None

    def step(self, **kwargs):
        step = AutoMemoryStep(
            app_context=self.app_context,
            file_store=self.store,
            agent_wrapper=self.wrapper,
            **{"supports_vision": True, **kwargs},
        )
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
    assert "__reme_image_" not in harness.session_path.read_text(encoding="utf-8")


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
        messages, expected = [older, original], _main_saved_line(older) + original_bytes
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
@pytest.mark.parametrize("scenario", ["off", "direct", "fallback"])
async def test_default_memory_chain_passes_changes_to_auto_tag_without_losing_image_metadata(
    harness,
    monkeypatch,
    scenario,
):
    path = f"daily/{_DAY}/image-memory.md"
    target = harness.workspace / path
    harness.store.tag_index = LocalTagIndex(max_tags_per_file=3)
    tagger = _TaggingWrapper(harness.workspace, tags=["OpenAI"])

    async def find_note(_step, _day, _session_id):
        return {"path": path} if target.exists() else None

    async def write_memory(inputs, **kwargs):
        harness.wrapper.calls.append((inputs, kwargs))
        _write_note(target)
        return {"result": "Memory written."}

    monkeypatch.setattr(AutoMemoryStep, "_list_session_note", find_note)
    monkeypatch.setattr(harness.wrapper, "reply", write_memory)
    defaults = Path(__file__).resolve().parents[2] / "reme/config/default.yaml"
    steps = yaml.safe_load(defaults.read_text(encoding="utf-8"))["jobs"]["auto_memory"]["steps"]
    assert [step["backend"] for step in steps] == ["auto_memory_step", "auto_tag_step"]
    for step, wrapper in zip(steps, (harness.wrapper, tagger)):
        step.update(file_store=harness.store, agent_wrapper=wrapper)
    job = BaseJob(app_context=harness.app_context, steps=steps)
    message = _message()
    if scenario == "fallback":
        message.content[1].source.data = "invalid-base64"
    await job.start()
    try:
        response = await job(
            session_id=_SESSION,
            date=_DAY,
            messages=[message],
            include_images=scenario != "off",
            supports_vision=True,
            changes=[{"change": "added", "path": "daily/stale.md"}],
        )
    finally:
        await job.close()

    assert response.success is True
    assert response.answer == "Memory written."
    assert response.metadata["auto_tag"]["processed"] == response.metadata["auto_tag"]["succeeded"] == 1
    assert response.metadata["auto_tag"]["ignored"] == []
    assert response.metadata["auto_tag"]["results"][0]["change"] == "added"
    assert response.metadata["auto_tag"]["results"][0]["path"] == response.metadata["path"] == path
    assert len(tagger.calls) == 1
    inputs, options = harness.wrapper.calls[0]
    assert isinstance(inputs, Msg if scenario == "direct" else str)
    assert "[enable_tags]" not in options["system_prompt"] and "`tags`" not in options["system_prompt"]
    image_metadata = response.metadata.get("auto_memory_images")
    if scenario == "off":
        assert image_metadata is None
    else:
        assert image_metadata["status"] == ("completed" if scenario == "direct" else "fallback")
        assert image_metadata["mode"] == "direct"
        assert image_metadata["image_count"] == 2 and image_metadata["captioned_images"] == 0
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step_options,job_options,call_options,status",
    [
        ({}, {}, {}, None),
        ({"include_images": True, "supports_vision": True}, {}, {}, "completed"),
        ({"include_images": True, "supports_vision": True}, {}, {"supports_vision": False}, "fallback"),
        ({"supports_vision": False}, {"include_images": True, "supports_vision": True}, {}, "completed"),
        ({"include_images": True, "supports_vision": True}, {"include_images": False}, {}, None),
        (
            {"include_images": True, "supports_vision": False, "image_mode": "unsupported"},
            {"include_images": False},
            {"include_images": True, "supports_vision": True, "image_mode": "direct"},
            "completed",
        ),
    ],
)
async def test_real_base_job_merges_call_job_and_step_switches(
    harness,
    monkeypatch,
    step_options,
    job_options,
    call_options,
    status,
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
                **step_options,
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
    assert isinstance(harness.wrapper.calls[0][0], Msg if status == "completed" else str)
    assert response.metadata.get("auto_memory_images", {}).get("status") == status


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["caption-only", "future-mode", None, False])
async def test_enabled_unsupported_mode_is_configuration_error_not_fallback(harness, mode):
    step = harness.step()
    with pytest.raises(ValueError, match="image_mode"):
        await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True, image_mode=mode)
    assert not harness.wrapper.calls
    harness.logger.warning.assert_not_called()
    assert "auto_memory_images" not in step.context.response.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,value",
    [(key, value) for key in ("include_images", "supports_vision") for value in ("true", 1, None)],
)
async def test_non_boolean_switch_is_configuration_error_even_when_images_are_off(harness, key, value):
    step = harness.step()
    with pytest.raises(ValueError, match=key):
        await step(session_id=_SESSION, date=_DAY, messages=[_message()], **{key: value})
    assert not harness.wrapper.calls


@pytest.mark.asyncio
async def test_source_failure_warning_and_metadata_do_not_expose_provider_credentials(harness, monkeypatch):
    secret = "FAKE_PROVIDER_TOKEN_8c219"
    diagnostic = f"https://user:{secret}@images.invalid/x?api_key={secret}"
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", AsyncMock(side_effect=RuntimeError(diagnostic)))

    response = await _invoke(harness, [_message()], enabled=True)

    assert response.success is True
    assert response.metadata["auto_memory_images"]["reason"] == "source: RuntimeError"
    harness.logger.warning.assert_called_once()
    warning = harness.logger.warning.call_args.args[0]
    assert secret not in warning
    assert "images.invalid" not in warning
    assert secret not in str(response.metadata)
    assert secret not in response.answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,supported,images",
    [(False, True, True), (True, False, True), (True, True, False), (True, True, True)],
)
async def test_direct_prompt_guidance_only_applies_when_images_are_sent(harness, enabled, supported, images):
    step = harness.step()
    plain = step.prompt_format("system_prompt", enable_tags=False, include_images=False, direct_images=False)

    await step(
        session_id=_SESSION,
        date=_DAY,
        messages=[_message(images=images)],
        include_images=enabled,
        supports_vision=supported,
    )

    prompt = harness.wrapper.calls[0][1]["system_prompt"]
    assert (prompt != plain) is (enabled and supported and images)
    assert "[direct_images]" not in prompt
    assert "[caption_only]" not in prompt
