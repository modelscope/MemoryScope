"""Internal model overrides stay local to one AgentScope invocation."""

# pylint: disable=protected-access,missing-function-docstring

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from agentscope.agent import Agent
from agentscope.message import Msg
from agentscope.model import ChatModelBase
import pytest
import pytest_asyncio

from reme.components.agent_wrapper.as_agent_wrapper import AsAgentWrapper
from reme.components.application_context import ApplicationContext
from reme.components.as_llm import BaseAsLLM
from reme.enumeration import ComponentEnum


class _Model(ChatModelBase):
    """Local model double with no provider client or network calls."""

    def __init__(self, name):
        self.model = name
        self.structured_calls = []

    async def generate_structured_output(self, **kwargs):
        self.structured_calls.append(kwargs)
        return SimpleNamespace(
            content={"model": self.model},
            usage=SimpleNamespace(input_tokens=2, output_tokens=1),
        )


@pytest_asyncio.fixture(name="models")
async def model_fixture(tmp_path):
    context = ApplicationContext(workspace_dir=str(tmp_path))
    default = BaseAsLLM(name="default")
    default.model = _Model("default")
    vision = BaseAsLLM(name="vision")
    vision.model = _Model("vision")
    context.components = {ComponentEnum.AS_LLM: {"default": default, "vision": vision}}
    wrapper = AsAgentWrapper(
        app_context=context,
        system_prompt="Configured prompt",
        model_config={"max_retries": 1},
    )
    await default.start()
    await vision.start()
    await wrapper.start()
    yield SimpleNamespace(wrapper=wrapper, default=default, vision=vision, context=context)
    await wrapper.close()
    await vision.close()
    await default.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [False, True, None])
async def test_build_agent_binds_call_model_without_replacing_default(models, override):
    wrapper = models.wrapper
    before_kwargs = deepcopy(wrapper.kwargs)
    before_bindings = wrapper.dependency_bindings
    kwargs = {} if override is False else {"_model": models.vision.model if override else None}

    agent, inputs = await wrapper._build_agent("hello", **kwargs)

    assert isinstance(agent, Agent)
    assert isinstance(inputs, Msg)
    assert inputs.role == "user"
    assert agent.model is (models.vision.model if override else models.default.model)
    ordinary_agent, _ = await wrapper._build_agent("ordinary")
    assert ordinary_agent.model is models.default.model
    assert wrapper.as_llm is models.default
    assert wrapper.kwargs == before_kwargs
    assert wrapper.dependency_bindings == before_bindings
    assert wrapper._owned == []
    assert models.context.components == {ComponentEnum.AS_LLM: {"default": models.default, "vision": models.vision}}
    assert kwargs == ({} if override is False else {"_model": models.vision.model if override else None})


@pytest.mark.asyncio
@pytest.mark.parametrize("override", ["vision", {}, object()])
async def test_invalid_internal_model_override_fails_before_agent_construction(models, override):
    with pytest.raises(TypeError, match="ChatModelBase"):
        await models.wrapper._build_agent("hello", _model=override)
    assert models.wrapper.as_llm is models.default


@pytest.mark.asyncio
async def test_concurrent_replies_keep_agent_and_structured_output_on_each_call_model(models, monkeypatch):
    wrapper = models.wrapper
    barrier = asyncio.Barrier(3)
    observed = {}
    before_kwargs = deepcopy(wrapper.kwargs)
    before_bindings = wrapper.dependency_bindings

    async def observe(agent, inputs):
        agent.state.context = [inputs]

    async def reply(agent):
        label = agent.state.context[0].get_text_content()
        observed[label] = agent.model
        await asyncio.wait_for(barrier.wait(), timeout=5)
        assert wrapper.as_llm is models.default
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=3, output_tokens=1),
            model_dump=lambda: {"text": label},
            get_text_content=lambda: label,
        )

    monkeypatch.setattr(Agent, "observe", observe)
    monkeypatch.setattr(Agent, "reply", reply)
    monkeypatch.setattr(wrapper, "_dump_state", AsyncMock())
    schema = {"type": "object"}
    kwargs = {"_model": models.vision.model, "output_schema": schema}

    vision_result, ordinary_result, second_vision_result = await asyncio.gather(
        wrapper.reply("vision-first", **kwargs),
        wrapper.reply("ordinary", output_schema=schema),
        wrapper.reply("vision-second", **kwargs),
    )

    assert observed == {
        "vision-first": models.vision.model,
        "ordinary": models.default.model,
        "vision-second": models.vision.model,
    }
    for result, expected in ((vision_result, "vision"), (ordinary_result, "default"), (second_vision_result, "vision")):
        assert result["structured_output"] == {"model": expected}
        assert result["usage"] == {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    assert [call["messages"][0].get_text_content() for call in models.default.model.structured_calls] == ["ordinary"]
    assert {call["messages"][0].get_text_content() for call in models.vision.model.structured_calls} == {
        "vision-first",
        "vision-second",
    }
    assert wrapper.as_llm is models.default
    assert wrapper.kwargs == before_kwargs
    assert wrapper.dependency_bindings == before_bindings
    assert models.context.components == {ComponentEnum.AS_LLM: {"default": models.default, "vision": models.vision}}
    assert kwargs == {"_model": models.vision.model, "output_schema": {"type": "object"}}
    assert models.default.is_started and models.vision.is_started
    await wrapper.close()
    assert models.default.is_started and models.vision.is_started


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [False, True])
async def test_stream_builds_with_the_call_model_without_changing_default(models, monkeypatch, override):
    observed = []

    async def reply_stream(agent, inputs):
        observed.append((agent.model, inputs.get_text_content()))
        if inputs is None:
            yield None

    monkeypatch.setattr(Agent, "reply_stream", reply_stream)
    monkeypatch.setattr(models.wrapper, "_dump_state", AsyncMock())
    kwargs = {"_model": models.vision.model} if override else {}

    assert [chunk async for chunk in models.wrapper.reply_stream("hello", **kwargs)] == []
    assert observed == [(models.vision.model if override else models.default.model, "hello")]
    assert models.wrapper.as_llm is models.default
