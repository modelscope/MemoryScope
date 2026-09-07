"""Every resource modality consumes the same Base-managed ownership lookup."""

from collections import Counter
from unittest.mock import patch

import pytest

from reme.components import R
from reme.steps.evolve.auto_resource import AutoResourceStep
from reme.steps.evolve.auto_text_resource import AutoTextResourceStep
from reme.steps.evolve.base_auto_resource import BaseAutoResourceStep

from .auto_resource_test_support import FakeAudioResourceStep, FakeVisionModel

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio

_HISTORY_DAYS = ("2025-12-01", "2025-12-02", "2025-12-03")


def _count_history(env, monkeypatch):
    """Count the real daily_list jobs on history untouched by resource processing."""
    for day in _HISTORY_DAYS:
        env.write_note(f"daily/{day}/archive.md", f"[[resource/archive-{day}.txt]]")
    calls = Counter()
    daily_list = env.app_context.jobs["daily_list"]

    async def counted(**kwargs):
        calls[kwargs["date"]] += 1
        return await daily_list(**kwargs)

    monkeypatch.setitem(env.app_context.jobs, "daily_list", counted)
    env.app_context.metadata = {}
    return calls


@pytest.mark.parametrize("audio_first", [True, False], ids=["audio-first", "image-first"])
@pytest.mark.parametrize("invalid_audio", [False, True], ids=["valid-batch", "one-invalid-resource"])
async def test_third_modality_shares_history_regardless_of_processor_order(
    audio_first,
    invalid_audio,
    auto_resource_env,
    monkeypatch,
):
    """A new Step inherits the common lookup without any image-specific dependency."""
    env = auto_resource_env
    calls = _count_history(env, monkeypatch)
    notes = [
        env.write_note(f"daily/2026-01-01/{stem}.md", f"[[resource/{stem}.{suffix}]]")
        for stem, suffix in (("report", "txt"), ("photo", "png"), ("recording", "wav"))
    ]
    env.app_context.registry = R.copy()
    env.app_context.registry.add("test_audio_resource_step", FakeAudioResourceStep, owner=__name__)
    specific = ["test_audio_resource_step", "auto_image_resource_step"]
    if not audio_first:
        specific.reverse()
    model = FakeVisionModel("must not be called for deletion")
    router = AutoResourceStep(
        app_context=env.app_context,
        file_store=env.file_store,
        as_llm=model,
        dispatch_steps=[*specific, "auto_text_resource_step"],
    )
    changes = [
        {"change": "deleted", "path": f"resource/{stem}.{suffix}"}
        for stem, suffix in (("report", "txt"), ("photo", "png"), ("recording", "wav"))
    ]
    if invalid_audio:
        changes.insert(0, {"change": "deleted", "path": "resource/../private.wav"})
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-02"):
        response = await env.run(router, changes)

    results = response.metadata["results"]
    assert response.success is not invalid_audio
    assert [result["path"] for result in results] == [change["path"] for change in changes]
    assert all(result["metadata"]["action"] == "deleted" for result in results[int(invalid_audio) :])
    assert all(not note.exists() for note in notes)
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)
    assert not model.calls
    if invalid_audio:
        assert results[0]["metadata"]["action"] == "failed"
        assert results[0]["metadata"]["modified"] is False


@pytest.mark.parametrize("routed", [False, True], ids=["text-step", "text-only-router"])
@pytest.mark.parametrize("dated", [False, True], ids=["loose-root", "dated-resource"])
async def test_text_only_batch_uses_common_lookup_without_image_step(routed, dated, auto_resource_env, monkeypatch):
    """Text does not depend on an image processor priming the cache; dated files stay direct."""
    env = auto_resource_env
    calls = _count_history(env, monkeypatch)
    env.app_context.registry = R.copy()
    prefix = "resource/2026-01-01" if dated else "resource"
    notes = [env.write_note(f"daily/2026-01-01/report-{i}.md", f"[[{prefix}/report-{i}.txt]]") for i in range(3)]
    options = {"app_context": env.app_context, "file_store": env.file_store}
    step = (
        AutoResourceStep(**options, dispatch_steps=["auto_text_resource_step"])
        if routed
        else AutoTextResourceStep(**options)
    )
    response = await env.run(step, [{"change": "deleted", "path": f"{prefix}/report-{i}.txt"} for i in range(3)])

    assert response.success is True
    assert all(not note.exists() for note in notes)
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 0 if dated else 1)
