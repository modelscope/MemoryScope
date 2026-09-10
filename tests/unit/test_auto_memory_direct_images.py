"""Direct image inputs select a per-call AgentScope model without caption calls."""

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
from reme.enumeration import ComponentEnum
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
    """Local model with no API client or required model-catalog entry."""

    def __init__(self, name="custom-memory-model"):
        self.model = name
        self.context_size = 200000
        self.formatter = OpenAIChatFormatter()

    def list_models(self, custom_yaml_dir=None):
        del custom_yaml_dir
        raise AssertionError("Direct image routing must not inspect model catalogs")


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


class _DirectHarness(_Harness):
    """Use the product default instead of the old caption-only test preset."""

    def __init__(self, workspace, monkeypatch):
        super().__init__(workspace, monkeypatch)
        self.app_context.components = {}

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
    instance.app_context.components[ComponentEnum.AS_LLM] = {"default": instance.wrapper.as_llm}
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
    message.content[0].text += " Keep literal [Image 1]; image ID: gallery-before."
    message.content.insert(2, TextBlock(text="Between observations; image ID: gallery-after."))
    message.content.append(TextBlock(text="After both observations."))
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
    assert [block.type for block in inputs.content] == ["text", "data", "text", "data", "text"]
    assert "Remember this observation." in inputs.content[0].text
    assert "Keep literal [Image 1]; image ID: gallery-before." in inputs.content[0].text
    assert inputs.content[2].text.strip() == "Between observations; image ID: gallery-after."
    assert "After both observations." in inputs.content[4].text
    assert "# Your Task" in inputs.content[4].text
    assert inputs.content[4].text.index("After both observations.") < inputs.content[4].text.index("# Your Task")
    assert inputs.get_text_content().count("[Image 1]") == 1
    assert "[Image 2]" not in inputs.get_text_content()
    assert "__reme_image_" not in inputs.get_text_content()
    assert "TOOL_RESULT_MUST_NOT_BE_SAVED" not in inputs.get_text_content()
    assert "Caption (model-generated)" not in inputs.get_text_content()
    assert "image captions" not in kwargs["system_prompt"].lower()
    assert inputs.content[1].model_dump() == message.content[1].model_dump()
    assert inputs.content[3].model_dump() == message.content[3].model_dump()
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)
    assert not (harness.workspace / "resource").exists()
    caption.assert_not_called()
    assert not harness.vision.calls
    assert kwargs["_model"] is harness.wrapper.as_llm.model

    formatted = await harness.wrapper.as_llm.model.formatter.format([inputs])
    assert len(formatted) == 1
    assert [part["type"] for part in formatted[0]["content"]] == [
        "text",
        "image_url",
        "text",
        "image_url",
        "text",
    ]
    assert [part["text"] for part in formatted[0]["content"] if part["type"] == "text"] == [
        block.text for block in inputs.content if block.type == "text"
    ]
    image_parts = [part for part in formatted[0]["content"] if part["type"] == "image_url"]
    assert [part["image_url"]["url"] for part in image_parts] == [
        f"data:image/png;base64,{message.content[index].source.data}" for index in (1, 3)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("include_images", [None, False])
async def test_disabled_keeps_original_string_and_does_not_prepare(harness, monkeypatch, include_images):
    prepare = AsyncMock(side_effect=AssertionError("Disabled images must not be inspected"))
    monkeypatch.setattr("reme.steps.evolve.auto_memory.prepare_direct_message", prepare)
    original_component = harness.wrapper.as_llm
    original_model = original_component.model
    harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = SimpleNamespace(model=_DirectModel("vision"))
    step = harness.step()
    kwargs = {} if include_images is None else {"include_images": include_images}

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], image_mode="future-mode", **kwargs)

    assert step.context.response.success is True
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert "[Image" not in harness.wrapper.calls[0][0]
    assert "auto_memory_images" not in step.context.response.metadata
    assert "_model" not in harness.wrapper.calls[0][1]
    assert harness.wrapper.as_llm is original_component
    assert original_component.model is original_model
    prepare.assert_not_called()


@pytest.mark.asyncio
async def test_no_images_skips_model_selection_and_source_checks(harness, monkeypatch):
    original_model = harness.wrapper.as_llm.model
    harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = None
    loader = AsyncMock(side_effect=AssertionError("No image should be loaded"))
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    response = await _run(harness, [_message(images=False)])

    assert response.success is True
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert response.metadata["auto_memory_images"]["status"] == "skipped"
    assert response.metadata["auto_memory_images"]["image_count"] == 0
    assert "_model" not in harness.wrapper.calls[0][1]
    assert harness.wrapper.as_llm.model is original_model
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
    assert "_model" not in harness.wrapper.calls[0][1]
    harness.logger.warning.assert_called_once()
    loader.assert_not_called()


@pytest.mark.asyncio
async def test_model_catalog_and_formatter_declarations_do_not_gate_direct_inputs(harness, monkeypatch):
    model = _DirectModel("custom-deployment")
    model.formatter = OpenAIChatFormatter(input_types=["text/plain"])
    catalog = Mock(side_effect=AssertionError("Model capabilities belong to the caller"))
    monkeypatch.setattr(model, "list_models", catalog)
    harness.wrapper.as_llm.model = model

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "completed"
    assert isinstance(harness.wrapper.calls[0][0], Msg)
    assert harness.wrapper.calls[0][1]["_model"] is model
    assert not harness.vision.calls
    catalog.assert_not_called()
    harness.logger.warning.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper_binding", ["default", "custom"])
async def test_dedicated_vision_model_is_preferred_without_rebinding_shared_components(harness, wrapper_binding):
    models = harness.app_context.components[ComponentEnum.AS_LLM]
    default_component = models["default"]
    custom_component = BaseAsLLM()
    custom_component.model = _DirectModel("custom-memory")
    vision_component = BaseAsLLM()
    vision_component.model = _DirectModel("dedicated-vision")
    models.update(custom=custom_component, vision=vision_component)
    harness.wrapper.as_llm = models[wrapper_binding]
    original_components = dict(models)
    original_models = {name: component.model for name, component in models.items()}
    wrapper_options = {"context_config": {"trigger_ratio": 0.7}, "model_config": {"max_retries": 2}}
    harness.wrapper.kwargs.update(wrapper_options)

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "completed"
    assert harness.wrapper.calls[0][1]["_model"] is vision_component.model
    assert harness.wrapper.as_llm is original_components[wrapper_binding]
    assert all(models[name] is component for name, component in original_components.items())
    assert all(models[name].model is model for name, model in original_models.items())
    assert harness.wrapper.kwargs["context_config"] is wrapper_options["context_config"]
    assert harness.wrapper.kwargs["model_config"] is wrapper_options["model_config"]
    assert wrapper_options == {"context_config": {"trigger_ratio": 0.7}, "model_config": {"max_retries": 2}}
    assert default_component.model is original_models["default"]
    assert not harness.vision.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("application_context", [True, False])
async def test_absent_vision_uses_actual_custom_wrapper_binding(harness, application_context):
    default_component = harness.app_context.components[ComponentEnum.AS_LLM]["default"]
    custom_component = BaseAsLLM()
    custom_component.model = _DirectModel("custom-memory")
    harness.wrapper.as_llm = custom_component
    step = harness.step()
    if not application_context:
        step.app_context = None

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True)

    assert step.context.response.metadata["auto_memory_images"]["status"] == "completed"
    assert harness.wrapper.calls[0][1]["_model"] is custom_component.model
    assert harness.wrapper.calls[0][1]["_model"] is not default_component.model
    assert harness.wrapper.as_llm is custom_component
    assert not harness.vision.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["bound-model", "vision-model", "vision-component"])
async def test_selected_model_must_be_started_without_silent_model_substitution(harness, monkeypatch, unavailable):
    if unavailable == "bound-model":
        harness.wrapper.as_llm.model = None
    elif unavailable == "vision-model":
        harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = BaseAsLLM()
    else:
        harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = None
    original_component = harness.wrapper.as_llm
    original_model = original_component.model
    loader = AsyncMock(side_effect=AssertionError("Missing model must be rejected before image IO"))
    monkeypatch.setattr(_auto_memory_image, "_image_bytes", loader)

    response = await _run(harness, [_message()])

    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert response.metadata["auto_memory_images"]["reason"] == "model: ValueError"
    assert isinstance(harness.wrapper.calls[0][0], str)
    assert "_model" not in harness.wrapper.calls[0][1]
    assert "context_config" not in harness.wrapper.calls[0][1]
    assert harness.wrapper.as_llm is original_component
    assert original_component.model is original_model
    assert not harness.vision.calls
    loader.assert_not_called()


@pytest.mark.asyncio
async def test_caption_only_uses_vision_for_captions_and_keeps_original_memory_model(harness):
    original_component = harness.wrapper.as_llm
    original_model = original_component.model
    harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = SimpleNamespace(model=harness.vision)
    step = harness.step()
    step.kwargs.pop("as_llm")

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True, image_mode="caption-only")

    assert step.context.response.metadata["auto_memory_images"]["status"] == "completed"
    assert step.context.response.metadata["auto_memory_images"]["mode"] == "caption-only"
    assert len(harness.vision.calls) == 2
    assert len(harness.wrapper.calls) == 1
    inputs, options = harness.wrapper.calls[0]
    assert isinstance(inputs, str)
    assert "Caption (model-generated)" in inputs
    assert "_model" not in options
    assert harness.wrapper.as_llm is original_component
    assert original_component.model is original_model


@pytest.mark.asyncio
async def test_reply_hook_model_options_are_read_once_and_passed_unchanged(harness, monkeypatch):
    fallback = _DirectModel()
    fallback.formatter = OpenAIChatFormatter(input_types=["text/plain"])
    harness.wrapper.kwargs["model_config"] = {"max_retries": 2}
    model_config = {"fallback_model": fallback}
    options = {"model_config": model_config}
    step = harness.step()
    hook = Mock(return_value=options)
    monkeypatch.setattr(step, "_reply_extra_kwargs", hook)

    await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True)

    assert step.context.response.metadata["auto_memory_images"]["status"] == "completed"
    assert isinstance(harness.wrapper.calls[0][0], Msg)
    assert harness.wrapper.calls[0][1]["model_config"] is model_config
    assert harness.wrapper.calls[0][1]["_model"] is harness.wrapper.as_llm.model
    assert harness.wrapper.kwargs["model_config"] == {"max_retries": 2}
    assert model_config["fallback_model"] is fallback
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
        assert "_model" not in harness.wrapper.calls[0][1]
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
async def test_interleaving_preserves_whole_history_hook_and_image_only_turn_with_duplicate_ids(harness, monkeypatch):
    first = _message()
    first.content.insert(2, TextBlock(text="This separates the two observations."))
    second = _message("second", f"{_DAY}T11:00:00", images=False)
    second.name = "user"
    second.role = "user"
    second.content = [first.content[1].model_copy(deep=True)]
    messages = [first, second]
    originals = [message.model_dump() for message in messages]
    step = harness.step()

    def format_whole_history(history):
        # Like LME/BEAM, the hook depends on the full slice, not one Msg per call.
        return f"Source excerpt: L41-L{40 + len(history)}\n" + "\n\n".join(
            f"[L{line} | {message.name} @ {message.created_at}]\n{message.get_text_content()}"
            for line, message in enumerate(history, start=41)
        )

    hook = Mock(side_effect=format_whole_history)
    monkeypatch.setattr(step, "_format_history", hook)

    await step(session_id=_SESSION, date=_DAY, messages=messages, include_images=True)

    inputs = harness.wrapper.calls[0][0]
    assert step.context.response.metadata["auto_memory_images"]["status"] == "completed"
    assert hook.call_count == 2  # Original fallback prompt, then the temporary multimodal history.
    assert all(len(call.args[0]) == 2 for call in hook.call_args_list)
    assert inputs.get_text_content().count("Source excerpt: L41-L42") == 1
    assert "[L41 | assistant @" in inputs.content[0].text
    assert inputs.content[2].text.strip() == "This separates the two observations."
    assert f"[L42 | user @ {second.created_at}]" in inputs.content[4].text
    assert "# Your Task" in inputs.content[-1].text
    assert "__reme_image_" not in inputs.get_text_content()
    assert "[Image" not in inputs.get_text_content()
    assert [block.type for block in inputs.content] == ["text", "data", "text", "data", "text", "data", "text"]
    data_blocks = [block for block in inputs.content if block.type == "data"]
    assert len(data_blocks) == 3
    assert len({block.id for block in data_blocks}) == 1
    assert data_blocks[0].source.data == data_blocks[2].source.data
    assert data_blocks[0].source.data != data_blocks[1].source.data
    assert [message.model_dump() for message in messages] == originals
    assert harness.session_path.read_bytes() == b"".join(_main_saved_line(message) for message in messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("language,existing", [("en", False), ("zh", False), ("en", True), ("zh", True)])
async def test_interleaving_keeps_localized_create_update_prompt_boundaries(harness, monkeypatch, language, existing):
    step = harness.step(language=language)
    note_path = f"daily/{_DAY}/existing.md"
    if existing:
        monkeypatch.setattr(step, "_list_session_note", AsyncMock(return_value={"path": note_path}))
        monkeypatch.setattr(step, "_ensure_memory_frontmatter", AsyncMock())
        monkeypatch.setattr(step, "_rename_from_frontmatter_name", AsyncMock(return_value=note_path))
        monkeypatch.setattr("reme.steps.evolve.auto_memory.refresh_day_index", AsyncMock(return_value={}))
    message = _message()

    await step(session_id=_SESSION, date=_DAY, messages=[message], include_images=True)

    inputs, options = harness.wrapper.calls[0]
    assert step.context.response.success is True
    assert step.context.response.metadata["auto_memory_images"]["status"] == "completed"
    assert inputs.content[0].text.startswith("Today:" if language == "en" else "今天：")
    assert "Remember this observation." in inputs.content[0].text
    assert ("# Your Task" if language == "en" else "# 你的任务") in inputs.content[-1].text
    assert ("frontmatter_update" if existing else "daily_write") in inputs.content[-1].text
    assert [block.id for block in inputs.content if block.type == "data"] == [message.content[1].id] * 2
    assert "__reme_image_" not in inputs.get_text_content()
    assert "[Image" not in inputs.get_text_content()
    if existing:
        assert note_path in inputs.content[0].text
        assert options["injected_job_kwargs"] == {"_allowed_paths": [note_path]}


@pytest.mark.asyncio
@pytest.mark.parametrize("template", ["No history requested.", "{history}\n{history}"])
async def test_missing_or_repeated_history_falls_back_without_direct_overrides(harness, monkeypatch, template):
    step = harness.step(prompt_dict={"user_message_create": template})
    original_model = harness.wrapper.as_llm.model
    original_options = {"context_config": {"trigger_ratio": 0.7}, "model_config": {"max_retries": 2}}
    monkeypatch.setattr(step, "_reply_extra_kwargs", Mock(return_value=original_options))
    harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = SimpleNamespace(model=_DirectModel("vision"))
    message = _message()

    await step(session_id=_SESSION, date=_DAY, messages=[message], include_images=True)

    response = step.context.response
    inputs, options = harness.wrapper.calls[0]
    assert response.success is True
    assert response.metadata["auto_memory_images"]["status"] == "fallback"
    assert response.metadata["auto_memory_images"]["reason"] == "prompt: ValueError"
    assert inputs == template.format(history=step._format_history([message]))
    assert "__reme_image_" not in inputs
    assert "_model" not in options
    assert options["context_config"] is original_options["context_config"]
    assert original_options == {"context_config": {"trigger_ratio": 0.7}, "model_config": {"max_retries": 2}}
    assert harness.wrapper.as_llm.model is original_model
    harness.logger.warning.assert_called_once()
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
async def test_invalid_original_prompt_remains_an_error_before_image_preparation(harness, monkeypatch):
    prepare = AsyncMock(side_effect=AssertionError("Invalid templates must fail before image processing"))
    monkeypatch.setattr("reme.steps.evolve.auto_memory.prepare_direct_message", prepare)
    step = harness.step(prompt_dict={"user_message_create": "{missing_variable}"})

    with pytest.raises(KeyError, match="missing_variable"):
        await step(session_id=_SESSION, date=_DAY, messages=[_message()], include_images=True)

    prepare.assert_not_called()
    harness.logger.warning.assert_not_called()
    assert not harness.wrapper.calls


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

    direct_message = await _auto_memory_image.prepare_direct_message(step, [message], step._format_history)
    await _auto_memory_image.prepare_image_messages(step, [message], _DAY)

    assert len(caption_payloads) == 1
    image_input = next(block.source for block in direct_message.content if block.type == "data")
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
    source_input = next(block.source for block in harness.wrapper.calls[0][0].content if block.type == "data")
    assert source_input.type == "base64"
    assert base64.b64decode(source_input.data) == source.read_bytes() == _png()
    assert message.model_dump() == before
    assert harness.session_path.read_bytes() == _main_saved_line(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid-base64", "invalid-image", "outside-workspace", "permission"])
async def test_second_image_failure_discards_all_prepared_inputs(harness, failure):
    message = _six_image_message()
    source_config = {"trigger_ratio": 0.7}
    harness.wrapper.kwargs["context_config"] = source_config
    original_component = harness.wrapper.as_llm
    original_model = original_component.model
    vision_model = _DirectModel("dedicated-vision")
    harness.app_context.components[ComponentEnum.AS_LLM]["vision"] = SimpleNamespace(model=vision_model)
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
    assert "_model" not in harness.wrapper.calls[0][1]
    assert "[Image" not in harness.wrapper.calls[0][0]
    assert "Remember this observation." in harness.wrapper.calls[0][0]
    assert response.metadata["auto_memory_images"]["captioned_images"] == 0
    assert "context_config" not in harness.wrapper.calls[0][1]
    assert "_model" not in harness.wrapper.calls[0][1]
    assert source_config == {"trigger_ratio": 0.7}
    assert harness.wrapper.as_llm is original_component
    assert original_component.model is original_model
    assert harness.app_context.components[ComponentEnum.AS_LLM]["vision"].model is vision_model
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
