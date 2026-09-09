"""Direct image inputs use the bound AgentScope model without caption calls."""

# pylint: disable=protected-access,missing-function-docstring

import asyncio
import base64
import copy
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agentscope.agent import Agent, ContextConfig
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Base64Source, Msg, TextBlock, URLSource
from agentscope.model import ChatModelBase
from PIL import Image
import pytest
import yaml

from reme.components.agent_wrapper.as_agent_wrapper import AsAgentWrapper
from reme.components.as_llm import BaseAsLLM
from reme.components.runtime_context import RuntimeContext
from reme.steps.evolve import _auto_memory_image, _image_caption

from .test_auto_memory_image_modes import (
    _DAY,
    _SESSION,
    _Harness,
    _MemoryWrapper,
    _main_saved_line,
    _message,
    _png,
)


class _DirectModel(ChatModelBase):
    """Local model and formatter capability boundary; no API client exists."""

    def __init__(self):
        self.model = "declared-vision-model"
        self.context_size = 200000
        self.formatter = OpenAIChatFormatter()
        self.cards = [SimpleNamespace(name=self.model, input_types=["text/plain", "image/png"])]

    def list_models(self, custom_yaml_dir=None):
        del custom_yaml_dir
        return self.cards


class _DirectWrapper(AsAgentWrapper):
    """Keep a real wrapper type and binding while observing the reply boundary."""

    def __init__(self):
        super().__init__(backend="agentscope")
        self.as_llm = BaseAsLLM(supports_images=None)
        self.as_llm.model = _DirectModel()
        self.calls = []
        self.error = None

    async def reply(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        if self.error is not None:
            raise self.error
        return {"result": "ok"}


class _DirectHarness(_Harness):
    """Use the product default instead of the old caption-only test preset."""

    def step(self, **kwargs):
        step = super().step(**kwargs)
        if "image_mode" not in kwargs:
            step.kwargs.pop("image_mode", None)
        return step


@pytest.fixture(name="harness")
def direct_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    instance = _DirectHarness(tmp_path, monkeypatch)
    instance.wrapper = _DirectWrapper()
    return instance


async def _run(harness, messages, **kwargs):
    step = harness.step()
    await step(session_id=_SESSION, date=_DAY, messages=messages, include_images=True, **kwargs)
    return step.context.response


def test_default_config_keeps_images_disabled_and_selects_direct_mode():
    path = Path(__file__).resolve().parents[2] / "reme" / "config" / "default.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = config["jobs"]["auto_memory"]
    properties = job["parameters"]["properties"]
    assert properties["include_images"]["default"] is False
    assert properties["image_mode"]["default"] == "direct"
    assert properties["image_mode"]["enum"] == ["direct", "caption-only"]
    assert job["steps"][0]["include_images"] is False
    assert job["steps"][0]["image_mode"] == "direct"


@pytest.mark.asyncio
async def test_enabled_default_is_direct_with_a_single_memory_reply(harness, monkeypatch):
    caption = AsyncMock(side_effect=AssertionError("Direct mode must not caption images"))
    monkeypatch.setattr(_auto_memory_image, "generate_image_caption", caption)
    message = _message()
    before = copy.deepcopy(message.model_dump())

    response = await _run(harness, [message])

    assert response.success is True
    assert response.metadata["auto_memory_images"] == {
        "mode": "direct",
        "status": "completed",
        "image_count": 2,
        "captioned_images": 0,
    }
    assert len(harness.wrapper.calls) == 1
    inputs, kwargs = harness.wrapper.calls[0]
    assert isinstance(inputs, Msg)
    assert inputs.role == "user"
    assert [block.type for block in inputs.content] == ["text", "text", "data", "text", "data"]
    assert "Remember this observation." in inputs.content[0].text
    assert "# Your Task" in inputs.content[0].text
    assert "[Image 1]" in inputs.content[0].text
    assert "[Image 2]" in inputs.content[0].text
    assert "TOOL_RESULT_MUST_NOT_BE_SAVED" not in inputs.get_text_content()
    assert "Caption (model-generated)" not in inputs.get_text_content()
    assert "image captions" not in kwargs["system_prompt"].lower()
    assert inputs.content[2].model_dump() == message.content[1].model_dump()
    assert inputs.content[4].model_dump() == message.content[2].model_dump()
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    assert not (harness.workspace / "resource").exists()
    caption.assert_not_called()
    assert not harness.vision.calls

    formatted = await harness.wrapper.as_llm.model.formatter.format([inputs])
    assert len(formatted) == 1
    image_parts = [part for part in formatted[0]["content"] if part["type"] == "image_url"]
    assert [part["image_url"]["url"] for part in image_parts] == [
        f"data:image/png;base64,{message.content[index].source.data}" for index in (1, 2)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("include_images", [None, False])
async def test_disabled_keeps_original_string_and_does_not_prepare(harness, monkeypatch, include_images):
    prepare = AsyncMock(side_effect=AssertionError("Disabled images must not be inspected"))
    monkeypatch.setattr("reme.steps.evolve.auto_memory.prepare_direct_messages", prepare)
    step = harness.step()
    kwargs = {} if include_images is None else {"include_images": include_images}

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], image_mode="future-mode", **kwargs)

    assert step.context.response.success is True
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert "[Image" not in harness.wrapper.calls[0][0]
    assert "auto_memory_images" not in step.context.response.metadata
    prepare.assert_not_called()


@pytest.mark.asyncio
async def test_no_images_skips_capability_and_source_checks(harness, monkeypatch):
    harness.wrapper = _MemoryWrapper()
    loader = AsyncMock(side_effect=AssertionError("No image should be loaded"))
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    response = await _run(harness, [_message(images=False)])

    assert response.success is True
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert response.metadata["auto_memory_images"]["status"] == "skipped"
    assert response.metadata["auto_memory_images"]["image_count"] == 0
    harness.logger.warning.assert_not_called()
    loader.assert_not_called()


@pytest.mark.asyncio
async def test_non_agentscope_wrapper_is_not_trusted_by_backend_name(harness, monkeypatch):
    harness.wrapper = _MemoryWrapper()
    harness.wrapper.backend = "agentscope"
    loader = AsyncMock(side_effect=AssertionError("Backend rejection must precede image IO"))
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    response = await _run(harness, [_message()])

    assert response.success is True
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert response.metadata["auto_memory_images"]["reason"] == "backend: TypeError"
    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    harness.logger.warning.assert_called_once()
    loader.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("supports_images", "card_name", "card_types", "expected"),
    [
        (None, "declared-vision-model", ["text/plain", "image/png"], "completed"),
        (None, "declared-vision-model", ["text/plain", "image/*"], "completed"),
        (None, "different-vision-model", ["text/plain", "image/png"], "fallback"),
        (None, "declared-vision-model-preview", ["text/plain", "image/png"], "fallback"),
        (None, "declared-vision-model", ["text/plain"], "fallback"),
        (None, "declared-vision-model", ["text/plain", "image/jpeg"], "fallback"),
        (False, "declared-vision-model", ["text/plain", "image/png"], "fallback"),
        (True, "different-vision-model", ["text/plain"], "completed"),
    ],
)
async def test_selected_model_capability_requires_exact_card_or_explicit_override(
    harness,
    supports_images,
    card_name,
    card_types,
    expected,
):
    component = harness.wrapper.as_llm
    component.supports_images = supports_images
    component.model.cards = [SimpleNamespace(name=card_name, input_types=card_types)]

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == expected
    assert isinstance(harness.wrapper.calls[0][0], Msg if expected == "completed" else str)
    assert not harness.vision.calls
    if card_types == ["text/plain", "image/jpeg"]:
        assert response.metadata["auto_memory_images"]["reason"] == "formatter-capability: ValueError"


@pytest.mark.asyncio
async def test_explicit_capability_does_not_require_catalog_access(harness, monkeypatch):
    harness.wrapper.as_llm.supports_images = True

    def unavailable_catalog(*_args, **_kwargs):
        raise AssertionError("An explicit deployment declaration replaces catalog discovery")

    monkeypatch.setattr(harness.wrapper.as_llm.model, "list_models", unavailable_catalog)

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("input_types", [["text/plain"], ["text/plain", "image/jpeg"]])
async def test_explicit_vision_cannot_bypass_formatter_mime_support(harness, input_types):
    harness.wrapper.as_llm.supports_images = True
    harness.wrapper.as_llm.model.formatter = OpenAIChatFormatter(input_types=input_types)

    response = await _run(harness, [_message()])

    assert isinstance(harness.wrapper.calls[0][0], str)
    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert response.metadata["auto_memory_images"]["reason"] == "formatter-capability: ValueError"
    harness.logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_missing_bound_memory_model_falls_back_without_using_caption_model(harness):
    harness.wrapper.as_llm.model = None

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert not harness.vision.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("card_types", "formatter_types", "expected", "reason"),
    [
        (["text/plain"], ["text/plain", "image/*"], "fallback", "fallback-model-capability: ValueError"),
        (["text/plain", "image/png"], ["text/plain"], "fallback", "formatter-capability: ValueError"),
        (["text/plain", "image/jpeg"], ["text/plain", "image/*"], "fallback", "formatter-capability: ValueError"),
        (["text/plain", "image/png"], ["text/plain", "image/*"], "completed", None),
    ],
)
async def test_configured_fallback_model_must_accept_every_prepared_image(
    harness,
    card_types,
    formatter_types,
    expected,
    reason,
):
    fallback = _DirectModel()
    fallback.cards[0].input_types = card_types
    fallback.formatter = OpenAIChatFormatter(input_types=formatter_types)
    harness.wrapper.kwargs["model_config"] = {"fallback_model": fallback}

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == expected
    assert isinstance(harness.wrapper.calls[0][0], Msg if expected == "completed" else str)
    assert response.metadata["auto_memory_images"].get("reason") == reason
    assert harness.wrapper.kwargs["model_config"]["fallback_model"] is fallback


@pytest.mark.asyncio
async def test_unknown_fallback_model_cannot_inherit_primary_capability_declaration(harness, monkeypatch):
    harness.wrapper.as_llm.supports_images = True
    fallback = _DirectModel()
    fallback.cards = []
    harness.wrapper.kwargs["model_config"] = {"fallback_model": fallback}
    loader = AsyncMock(side_effect=AssertionError("An unsupported fallback must be rejected before image IO"))
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert response.metadata["auto_memory_images"]["reason"] == "fallback-model-capability: ValueError"
    assert isinstance(harness.wrapper.calls[0][0], str)
    loader.assert_not_called()


@pytest.mark.asyncio
async def test_same_instance_fallback_uses_the_primary_deployment_declaration(harness):
    component = harness.wrapper.as_llm
    component.supports_images = True
    component.model.cards = []
    harness.wrapper.kwargs["model_config"] = {"fallback_model": component.model}

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "completed"
    assert isinstance(harness.wrapper.calls[0][0], Msg)


@pytest.mark.asyncio
@pytest.mark.parametrize("override", ["disable", "replace-config", "supported", "unsupported"])
async def test_reply_hook_model_options_are_checked_once_and_passed_unchanged(harness, monkeypatch, override):
    unsupported = _DirectModel()
    unsupported.cards[0].input_types = ["text/plain"]
    harness.wrapper.kwargs["model_config"] = {"fallback_model": unsupported, "max_retries": 2}
    if override == "disable":
        model_config = {"fallback_model": None}
    elif override == "replace-config":
        # The wrapper shallowly replaces this field, rather than keeping the
        # component-level fallback by deeply merging model_config.
        model_config = {"max_retries": 0}
    elif override == "supported":
        model_config = {"fallback_model": _DirectModel()}
    else:
        harness.wrapper.kwargs["model_config"] = {"max_retries": 0}
        model_config = {"fallback_model": unsupported}
    options = {"model_config": model_config}
    step = harness.step()
    hook = Mock(return_value=options)
    monkeypatch.setattr(step, "_reply_extra_kwargs", hook)

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True)

    expected = "fallback" if override == "unsupported" else "completed"
    assert step.context.response.metadata["auto_memory_images"]["status"] == expected
    assert isinstance(harness.wrapper.calls[0][0], str if override == "unsupported" else Msg)
    assert harness.wrapper.calls[0][1]["model_config"] is model_config
    assert options == {"model_config": model_config}
    hook.assert_called_once_with(_DAY)


def _six_image_message():
    message = _message()
    message.content = [message.content[0], *[message.content[1].model_copy(deep=True) for _ in range(6)]]
    return message


@pytest.mark.asyncio
async def test_default_direct_preserves_six_images_through_real_sdk_context_limiting(harness):
    original_context = {"trigger_ratio": 0.7, "reserve_ratio": 0.2}
    harness.wrapper.kwargs["context_config"] = original_context

    response = await _run(harness, [_six_image_message()])

    assert response.metadata["auto_memory_images"]["status"] == "completed"
    assert response.metadata["auto_memory_images"]["image_count"] == 6
    inputs, options = harness.wrapper.calls[0]
    config = options["context_config"]
    assert config == {"trigger_ratio": 0.7, "reserve_ratio": 0.2, "max_image_num": 6}
    assert config is not original_context
    assert original_context == {"trigger_ratio": 0.7, "reserve_ratio": 0.2}
    assert harness.wrapper.kwargs["context_config"] is original_context
    agent = Agent(
        name="memory-context-check",
        system_prompt="Record useful visual facts.",
        model=harness.wrapper.as_llm.model,
        context_config=ContextConfig(**config),
    )
    await agent.observe(inputs)
    await agent._limit_context_images(agent.context_config)
    assert sum(block.type == "data" for message in agent.state.context for block in message.content) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 5, 6, 10])
async def test_explicit_image_limits_are_respected_without_partial_image_inputs(harness, limit):
    context_config = {"max_image_num": limit, "trigger_ratio": 0.7}
    harness.wrapper.kwargs["context_config"] = context_config

    response = await _run(harness, [_six_image_message()])

    expected = "fallback" if limit < 6 else "completed"
    assert response.metadata["auto_memory_images"]["status"] == expected
    assert isinstance(harness.wrapper.calls[0][0], str if limit < 6 else Msg)
    assert context_config == {"max_image_num": limit, "trigger_ratio": 0.7}
    if limit < 6:
        assert response.metadata["auto_memory_images"]["reason"] == "context-image-limit: ValueError"
        assert "context_config" not in harness.wrapper.calls[0][1]
        harness.logger.warning.assert_called_once()
    else:
        assert harness.wrapper.calls[0][1]["context_config"] == context_config


@pytest.mark.asyncio
@pytest.mark.parametrize("override_limit", [None, 0, 10])
async def test_reply_context_override_has_shallow_precedence_without_mutating_source(
    harness,
    monkeypatch,
    override_limit,
):
    component_config = {"max_image_num": 5, "trigger_ratio": 0.7}
    harness.wrapper.kwargs["context_config"] = component_config
    call_config = {"reserve_ratio": 0.2}
    if override_limit is not None:
        call_config["max_image_num"] = override_limit
    original = dict(call_config)
    step = harness.step()
    hook = Mock(return_value={"context_config": call_config})
    monkeypatch.setattr(step, "_reply_extra_kwargs", hook)

    await step(session_id=_SESSION, date=_DAY, messages=[_six_image_message()], include_images=True)

    expected = "fallback" if override_limit == 0 else "completed"
    assert step.context.response.metadata["auto_memory_images"]["status"] == expected
    assert component_config == {"max_image_num": 5, "trigger_ratio": 0.7}
    assert call_config == original
    effective = harness.wrapper.calls[0][1]["context_config"]
    assert "trigger_ratio" not in effective
    assert effective["max_image_num"] == (6 if override_limit is None else override_limit)
    hook.assert_called_once_with(_DAY)


@pytest.mark.asyncio
async def test_source_failure_does_not_publish_temporary_image_limit_override(harness):
    source_config = {"trigger_ratio": 0.7}
    harness.wrapper.kwargs["context_config"] = source_config
    message = _six_image_message()
    message.content[-1].source.data = "invalid-base64!!!"

    response = await _run(harness, [message])

    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert "context_config" not in harness.wrapper.calls[0][1]
    assert source_config == {"trigger_ratio": 0.7}


@pytest.mark.asyncio
async def test_duplicate_block_ids_use_positions_and_repeated_images_are_not_deduplicated(harness):
    first = _message()
    first.content.insert(2, TextBlock(text="This separates the two observations."))
    second = _message("second", f"{_DAY}T11:00:00", images=False)
    second.content = [first.content[1].model_copy(deep=True)]
    messages = [first, second]
    originals = [message.model_dump() for message in messages]
    step = harness.step()
    step.context = RuntimeContext()

    prepared, attachments = await _auto_memory_image.prepare_direct_messages(step, messages)

    assert [prepared[0].content[index].text for index in (1, 2, 3)] == [
        "[Image 1]",
        "This separates the two observations.",
        "[Image 2]",
    ]
    assert prepared[1].content[0].text == "[Image 3]"
    assert [block.text for block in attachments if block.type == "text"] == ["[Image 1]", "[Image 2]", "[Image 3]"]
    data_blocks = [block for block in attachments if block.type == "data"]
    assert len(data_blocks) == 3
    assert len({block.id for block in data_blocks}) == 1
    assert data_blocks[0].source.data == data_blocks[2].source.data
    assert data_blocks[0].source.data != data_blocks[1].source.data
    assert [message.model_dump() for message in messages] == originals
    assert all(after is not before for after, before in zip(prepared, messages))


@pytest.mark.asyncio
@pytest.mark.parametrize("history", ["append", "backfill", "same-id"])
async def test_direct_preserves_original_main_jsonl_merge_contract(harness, history):
    original = _message()
    await _run(harness, [original])
    original_bytes = harness.session_path.read_bytes()
    other = _message("other", f"{_DAY}T09:00:00" if history == "backfill" else f"{_DAY}T11:00:00")
    if history == "same-id":
        other.id = original.id
        other.content[0].text = "Replacement for the same message ID."
        messages, expected = [other], original_bytes
    elif history == "backfill":
        messages, expected = [other, original], _main_saved_line(other) + _main_saved_line(original)
    else:
        messages, expected = [original, other], original_bytes + _main_saved_line(other)
    before = [message.model_dump() for message in messages]

    response = await _run(harness, messages)

    assert response.success is True
    assert harness.session_path.read_bytes() == expected
    assert [message.model_dump() for message in messages] == before
    assert "[Image" not in harness.session_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_direct_and_caption_use_identical_normalized_provider_bytes(harness, monkeypatch):
    # Capability checking applies to the prepared JPEG, not the source BMP.
    harness.wrapper.as_llm.model.cards[0].input_types = ["text/plain", "image/jpeg"]
    with Image.new("RGB", (2300, 8), (20, 40, 220)) as image:
        buffer = io.BytesIO()
        image.save(buffer, format="BMP")
    original_data = buffer.getvalue()
    message = _message()
    message.content = [message.content[0], message.content[1]]
    message.content[1].source = Base64Source(
        media_type="image/bmp",
        data=base64.b64encode(original_data).decode("ascii"),
    )
    before = message.model_dump()
    step = harness.step()
    step.context = RuntimeContext()
    caption_payloads = []

    async def caption(_model, payload, _prompt, **_kwargs):
        caption_payloads.append(payload)
        return {"name": "blue", "description": "Blue.", "caption": "A blue rectangle."}

    monkeypatch.setattr(_auto_memory_image, "generate_image_caption", caption)

    _, attachments = await _auto_memory_image.prepare_direct_messages(step, [message])
    await _auto_memory_image.prepare_image_messages(step, [message], _DAY)

    assert len(caption_payloads) == 1
    image_input = attachments[1].source
    assert image_input.media_type == caption_payloads[0]["mime"] == "image/jpeg"
    assert image_input.data == caption_payloads[0]["data_b64"]
    with Image.open(io.BytesIO(base64.b64decode(image_input.data))) as image:
        assert max(image.size) == _image_caption.MAX_IMAGE_REQUEST_DIMENSION
    assert message.model_dump() == before


@pytest.mark.asyncio
async def test_workspace_file_is_bounded_and_materialized_before_sdk_input(harness):
    source = harness.workspace / "original image.png"
    source.write_bytes(_png())
    message = _message()
    message.content = [message.content[0], message.content[1]]
    message.content[1].source = URLSource(media_type="image/png", url=source.as_uri())
    before = message.model_dump()

    response = await _run(harness, [message])

    assert response.metadata["auto_memory_images"]["status"] == "completed"
    source_input = harness.wrapper.calls[0][0].content[2].source
    assert source_input.type == "base64"
    assert base64.b64decode(source_input.data) == source.read_bytes() == _png()
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid-base64", "invalid-image", "outside-workspace", "permission"])
async def test_second_image_failure_discards_all_prepared_inputs(harness, failure):
    message = _message()
    kwargs = {}
    if failure == "invalid-base64":
        message.content[2].source.data = "INVALID_BASE64!!!"
    elif failure == "invalid-image":
        message.content[2].source.data = base64.b64encode(b"not an image").decode("ascii")
    elif failure == "outside-workspace":
        source = harness.workspace.parent / "out-of-workspace-image.png"
        source.write_bytes(_png())
        message.content[2].source = URLSource(media_type="image/png", url=source.as_uri())
    else:
        source = harness.workspace / "restricted-image.png"
        source.write_bytes(_png())
        message.content[2].source = URLSource(media_type="image/png", url=source.as_uri())
        kwargs["_allowed_paths"] = ["allowed-image.png"]
    before = message.model_dump()

    response = await _run(harness, [message], **kwargs)

    assert response.success is True
    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert "[Image" not in harness.wrapper.calls[0][0]
    assert "Remember this observation." in harness.wrapper.calls[0][0]
    assert response.metadata["auto_memory_images"]["captioned_images"] == 0
    harness.logger.warning.assert_called_once()
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
async def test_preparation_cancellation_propagates_without_memory_reply(harness, monkeypatch):
    loader = AsyncMock(side_effect=asyncio.CancelledError())
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    with pytest.raises(asyncio.CancelledError):
        await _run(harness, [_message()])

    assert not harness.wrapper.calls
    harness.logger.warning.assert_not_called()
    assert harness.session_path.exists()


@pytest.mark.asyncio
async def test_memory_reply_error_is_never_retried_as_text(harness):
    harness.wrapper.error = RuntimeError("Failure after a possible memory-tool write")

    with pytest.raises(RuntimeError, match="possible memory-tool write"):
        await _run(harness, [_message()])

    assert len(harness.wrapper.calls) == 1
    assert isinstance(harness.wrapper.calls[0][0], Msg)
    harness.logger.warning.assert_not_called()
    assert harness.session_path.exists()
