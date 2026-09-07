"""Batch-scoped historical lookup keeps resource ownership safe without repeated scans."""

from collections import Counter
from unittest.mock import patch

import pytest

from reme.components.file_store import LocalFileStore
from reme.components.runtime_context import RuntimeContext
from reme.schema import Response
from reme.steps.evolve.auto_image_resource import AutoImageResourceStep
from reme.steps.evolve.base_auto_resource import BaseAutoResourceStep, _resource_lookup_scope
from reme.steps.file_io import DailyListStep

from .auto_resource_test_support import FakeVisionModel, caption_json, image_bytes, make_app_context, write_note

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio

_HISTORY_DAYS = ("2025-12-01", "2025-12-02", "2025-12-03")


def _seed_history(env) -> None:
    """Create untouched days that should not be re-read for each resource."""
    for day in _HISTORY_DAYS:
        env.write_note(f"daily/{day}/archive.md", f"[[resource/archive-{day}.txt]]")


def _count_daily_lists(env, monkeypatch) -> Counter:
    """Count real job calls without replacing file parsing or result contracts."""
    calls = Counter()
    daily_list = env.app_context.jobs["daily_list"]

    async def counted_daily_list(**kwargs):
        calls[kwargs["date"]] += 1
        return await daily_list(**kwargs)

    monkeypatch.setitem(env.app_context.jobs, "daily_list", counted_daily_list)
    return calls


def _model() -> FakeVisionModel:
    """Use deterministic model output while retaining the real note lifecycle."""
    return FakeVisionModel(caption_json("caption", "A sample image", "A red square."))


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("resource_count", [1, 8])
async def test_loose_batch_scans_unchanged_history_once(routed, resource_count, auto_resource_env, monkeypatch):
    """Increasing the number of loose resources does not multiply historical scans."""
    env = auto_resource_env
    _seed_history(env)
    calls = _count_daily_lists(env, monkeypatch)
    changes = []
    for index in range(resource_count):
        source = env.write_binary(f"resource/photo-{index}.png", image_bytes())
        changes.append({"change": "added", "path": str(source)})

    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-01"):
        response = await env.run(env.processor(_model(), routed=routed), changes)

    assert response.success is True
    assert response.metadata["processed"] == resource_count
    assert all(result["metadata"]["created"] for result in response.metadata["results"])
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)
    paths = [result["metadata"]["path"] for result in response.metadata["results"]]
    assert len(set(paths)) == resource_count
    assert all((env.workspace / path).is_file() for path in paths)


async def test_mixed_processors_share_one_historical_scan(auto_resource_env, monkeypatch):
    """Text and image sub-batches share lookup work and retain original result order."""
    env = auto_resource_env
    _seed_history(env)
    text_note = env.write_note("daily/2026-01-01/report.md", "[[resource/report.txt]]")
    image_note = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    changes = [
        {"change": "deleted", "path": "resource/report.txt"},
        {"change": "deleted", "path": "resource/photo.png"},
    ]

    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-02"):
        response = await env.run(env.processor(_model(), routed=True), changes)

    assert response.success is True
    results = response.metadata["results"]
    assert [result["path"] for result in results] == [item["path"] for item in changes]
    assert all(result["metadata"]["action"] == "deleted" for result in results)
    assert not text_note.exists()
    assert not image_note.exists()
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_dated_batch_does_not_scan_history(routed, auto_resource_env, monkeypatch):
    """Dated paths retain their direct-day lookup and do not build a global index."""
    env = auto_resource_env
    _seed_history(env)
    source = env.write_binary("resource/2026-01-01/photo.png", image_bytes())
    calls = _count_daily_lists(env, monkeypatch)

    response = await env.run(
        env.processor(_model(), routed=routed),
        [{"change": "added", "path": str(source)}],
    )

    assert response.success is True
    assert response.metadata["results"][0]["metadata"]["path"] == "daily/2026-01-01/caption.md"
    assert all(calls[day] == 0 for day in _HISTORY_DAYS)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("lookup_value", [None, "user-owned input"], ids=["absent-key", "existing-key"])
async def test_reused_step_and_context_rebuild_ownership_next_batch(
    routed,
    lookup_value,
    auto_resource_env,
    monkeypatch,
):
    """A watcher-style reused context sees externally changed ownership on its next call."""
    env = auto_resource_env
    _seed_history(env)
    original = env.write_note("daily/2026-01-01/original.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    step = env.processor(_model(), routed=routed)
    context = RuntimeContext(changes=[{"change": "deleted", "path": "resource/photo.png"}], user_value="preserve")
    if lookup_value is not None:
        context["_auto_resource_lookup_batch"] = lookup_value
    context_keys = set(context.data)

    first = await step(context)
    assert first.success is True
    assert first.metadata["results"][0]["metadata"]["path"] == "daily/2026-01-01/original.md"
    assert not original.exists()
    assert set(context.data) == context_keys
    assert context["user_value"] == "preserve"
    assert context.get("_auto_resource_lookup_batch") == lookup_value

    new_owner = env.write_note("daily/2026-01-02/recreated.md", "[[resource/photo.png]]")
    second = await step(context)

    assert second.success is True
    assert second.metadata["results"][0]["metadata"]["path"] == "daily/2026-01-02/recreated.md"
    assert second.metadata["results"][0]["metadata"]["action"] == "deleted"
    assert not new_owner.exists()
    assert set(context.data) == context_keys
    assert context["user_value"] == "preserve"
    assert context.get("_auto_resource_lookup_batch") == lookup_value
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 2)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_repeated_resource_events_keep_current_ownership_across_midnight(routed, auto_resource_env, monkeypatch):
    """New writes become discoverable and deletion permits a new day's card in the same batch."""
    env = auto_resource_env
    _seed_history(env)
    env.write_binary("resource/photo.png", image_bytes())
    calls = _count_daily_lists(env, monkeypatch)
    clock = {"day": "2026-01-01"}
    # Advance the clock at the shared lifecycle boundary, after the actual write.
    original_refresh = BaseAutoResourceStep._refresh_day_index  # pylint: disable=protected-access

    async def refresh_and_advance(step, day):
        result = await original_refresh(step, day)
        clock["day"] = "2026-01-02"
        return result

    monkeypatch.setattr(BaseAutoResourceStep, "_today", lambda _step: clock["day"])
    monkeypatch.setattr(BaseAutoResourceStep, "_refresh_day_index", refresh_and_advance)
    response = await env.run(
        env.processor(_model(), routed=routed),
        [{"change": change, "path": "resource/photo.png"} for change in ("added", "modified", "deleted", "added")],
    )

    assert response.success is True
    metadata = [result["metadata"] for result in response.metadata["results"]]
    assert [item["action"] for item in metadata] == ["added", "modified", "deleted", "added"]
    assert [item["path"] for item in metadata] == [
        "daily/2026-01-01/caption.md",
        "daily/2026-01-01/caption.md",
        "daily/2026-01-01/caption.md",
        "daily/2026-01-02/caption.md",
    ]
    assert not (env.workspace / "daily/2026-01-01/caption.md").exists()
    assert (env.workspace / "daily/2026-01-02/caption.md").is_file()
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("first_change", ["added", "deleted"])
async def test_partial_index_failure_does_not_stale_batch_ownership(
    routed,
    first_change,
    auto_resource_env,
    monkeypatch,
):
    """Post-write and post-delete failures preserve disk ownership for the next resource event."""
    env = auto_resource_env
    _seed_history(env)
    env.write_binary("resource/photo.png", image_bytes())
    if first_change == "deleted":
        env.write_note("daily/2026-01-01/caption.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    clock = {"day": "2026-01-01"}
    # Inject a failure after disk mutation without replacing note processing.
    original_refresh = BaseAutoResourceStep._refresh_day_index  # pylint: disable=protected-access
    refresh_calls = 0

    async def fail_first_refresh(step, day):
        nonlocal refresh_calls
        refresh_calls += 1
        if refresh_calls == 1:
            clock["day"] = "2026-01-02"
            raise RuntimeError("day index unavailable after disk change")
        return await original_refresh(step, day)

    monkeypatch.setattr(BaseAutoResourceStep, "_today", lambda _step: clock["day"])
    monkeypatch.setattr(BaseAutoResourceStep, "_refresh_day_index", fail_first_refresh)
    next_change = "modified" if first_change == "added" else "added"
    response = await env.run(
        env.processor(_model(), routed=routed),
        [{"change": change, "path": "resource/photo.png"} for change in (first_change, next_change)],
    )

    assert response.success is False
    assert response.metadata["modified"] is True
    failed, recovered = response.metadata["results"]
    assert failed["success"] is False
    assert failed["metadata"]["modified"] is True
    assert "day index unavailable" in failed["metadata"]["error"]
    assert recovered["success"] is True
    day = "2026-01-01" if first_change == "added" else "2026-01-02"
    assert recovered["metadata"]["path"] == f"daily/{day}/caption.md"
    assert recovered["metadata"]["created"] is (first_change == "deleted")
    assert (env.workspace / f"daily/{day}/caption.md").is_file()
    assert len(list((env.workspace / "daily").glob("*/caption.md"))) == 1
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_cross_day_duplicate_owner_only_fails_ambiguous_resource(routed, auto_resource_env, monkeypatch):
    """Ambiguity is kept per source instead of making the shared index unusable for every item."""
    env = auto_resource_env
    _seed_history(env)
    first = env.write_note("daily/2026-01-01/first.md", "[[resource/duplicate.png]]")
    second = env.write_note("daily/2026-01-02/second.md", "[[resource/duplicate.png]]")
    valid = env.write_note("daily/2026-01-02/valid.md", "[[resource/valid.png]]")
    before = {note: note.read_bytes() for note in (first, second)}
    calls = _count_daily_lists(env, monkeypatch)

    response = await env.run(
        env.processor(_model(), routed=routed),
        [
            {"change": "deleted", "path": "resource/duplicate.png"},
            {"change": "deleted", "path": "resource/valid.png"},
        ],
    )

    ambiguous, deleted = response.metadata["results"]
    assert response.success is False
    assert ambiguous["success"] is False
    assert "Multiple daily resource notes claim resource/duplicate.png" in ambiguous["metadata"]["error"]
    assert ambiguous["metadata"]["modified"] is False
    assert deleted["success"] is True
    assert deleted["metadata"]["action"] == "deleted"
    assert not valid.exists()
    assert all(note.read_bytes() == contents for note, contents in before.items())
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_same_day_first_owner_semantics_survive_repeated_deletion(routed, auto_resource_env, monkeypatch):
    """Same-day duplicates retain the existing first-match behavior, including after one is removed."""
    env = auto_resource_env
    _seed_history(env)
    first = env.write_note("daily/2026-01-01/first.md", "[[resource/photo.png]]")
    second = env.write_note("daily/2026-01-01/second.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    changes = [{"change": "deleted", "path": "resource/photo.png"} for _ in range(3)]

    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-02"):
        response = await env.run(env.processor(_model(), routed=routed), changes)

    assert response.success is True
    metadata = [result["metadata"] for result in response.metadata["results"]]
    assert [item["action"] for item in metadata] == ["deleted", "deleted", "skipped"]
    assert [item["path"] for item in metadata[:2]] == [
        "daily/2026-01-01/first.md",
        "daily/2026-01-01/second.md",
    ]
    assert not first.exists()
    assert not second.exists()
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
@pytest.mark.parametrize("next_change", ["deleted", "modified"])
@pytest.mark.parametrize("initially_missing_target", [False, True], ids=["existing-target", "missing-target"])
async def test_shared_daily_directory_aliases_refresh_after_write(
    routed,
    next_change,
    initially_missing_target,
    auto_resource_env,
    monkeypatch,
):
    """Writing through one safe alias invalidates every date exposing the same physical notes."""
    env = auto_resource_env
    _seed_history(env)
    physical_day = env.workspace / ("daily/2026-01-01" if initially_missing_target else "archive-day")
    if not initially_missing_target:
        physical_day.mkdir()
    alias_days = ("2026-01-02",) if initially_missing_target else ("2026-01-01", "2026-01-02")
    for day in alias_days:
        try:
            (env.workspace / "daily" / day).symlink_to(physical_day, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlinks unavailable: {exc}")
    env.write_binary("resource/photo.png", image_bytes())
    calls = _count_daily_lists(env, monkeypatch)
    model = _model()

    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-01"):
        response = await env.run(
            env.processor(model, routed=routed),
            [{"change": change, "path": "resource/photo.png"} for change in ("added", next_change)],
        )

    created, ambiguous = response.metadata["results"]
    assert response.success is False
    assert created["success"] is True
    assert created["metadata"]["created"] is True
    assert ambiguous["success"] is False
    assert ambiguous["metadata"]["modified"] is False
    assert "Multiple daily resource notes claim resource/photo.png" in ambiguous["metadata"]["error"]
    assert "daily/2026-01-01/caption.md" in ambiguous["metadata"]["error"]
    assert "daily/2026-01-02/caption.md" in ambiguous["metadata"]["error"]
    assert (physical_day / "caption.md").is_file()
    assert len(model.calls) == 1
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_failed_dirty_day_refresh_retries_without_changing_ownership(routed, auto_resource_env, monkeypatch):
    """A failed targeted refresh stays dirty; the following event recovers the first-day card."""
    env = auto_resource_env
    _seed_history(env)
    env.write_binary("resource/photo.png", image_bytes())
    calls = _count_daily_lists(env, monkeypatch)
    daily_list = env.app_context.jobs["daily_list"]
    # Fail only the historical read after successful note finalization.
    original_refresh = BaseAutoResourceStep._refresh_day_index  # pylint: disable=protected-access
    clock = {"day": "2026-01-01"}
    failed = False

    async def refresh_and_advance(step, day):
        result = await original_refresh(step, day)
        clock["day"] = "2026-01-02"
        return result

    async def fail_first_dirty_read(**kwargs):
        nonlocal failed
        if clock["day"] == "2026-01-02" and kwargs["date"] == "2026-01-01" and not failed:
            failed = True
            return Response(success=False, answer="temporary dirty-day read failure")
        return await daily_list(**kwargs)

    monkeypatch.setattr(BaseAutoResourceStep, "_today", lambda _step: clock["day"])
    monkeypatch.setattr(BaseAutoResourceStep, "_refresh_day_index", refresh_and_advance)
    monkeypatch.setitem(env.app_context.jobs, "daily_list", fail_first_dirty_read)
    response = await env.run(
        env.processor(_model(), routed=routed),
        [{"change": change, "path": "resource/photo.png"} for change in ("added", "modified", "modified")],
    )

    created, interrupted, recovered = response.metadata["results"]
    assert response.success is False
    assert created["success"] is True
    assert interrupted["success"] is False
    assert interrupted["metadata"]["modified"] is False
    assert "temporary dirty-day read failure" in interrupted["metadata"]["error"]
    assert recovered["success"] is True
    assert recovered["metadata"]["created"] is False
    assert created["metadata"]["path"] == recovered["metadata"]["path"] == "daily/2026-01-01/caption.md"
    assert (env.workspace / "daily/2026-01-01/caption.md").is_file()
    assert not (env.workspace / "daily/2026-01-02/caption.md").exists()
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 1)


@pytest.mark.parametrize("routed", [False, True], ids=["image", "unified-router"])
async def test_interrupted_history_scan_is_not_reused_as_complete(routed, auto_resource_env, monkeypatch):
    """An item after transient daily_list failure rebuilds history and finds previously unvisited ownership."""
    env = auto_resource_env
    _seed_history(env)
    owned_note = env.write_note("daily/2026-01-01/original.md", "[[resource/photo.png]]")
    calls = Counter()
    daily_list = env.app_context.jobs["daily_list"]

    async def fail_once_mid_scan(**kwargs):
        day = kwargs["date"]
        calls[day] += 1
        if day == _HISTORY_DAYS[1] and calls[day] == 1:
            return Response(success=False, answer="temporary history read failure")
        return await daily_list(**kwargs)

    monkeypatch.setitem(env.app_context.jobs, "daily_list", fail_once_mid_scan)
    with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-02"):
        response = await env.run(
            env.processor(_model(), routed=routed),
            [
                {"change": "deleted", "path": "resource/missing.png"},
                {"change": "deleted", "path": "resource/photo.png"},
            ],
        )

    failed, recovered = response.metadata["results"]
    assert response.success is False
    assert failed["success"] is False
    assert failed["metadata"]["modified"] is False
    assert "temporary history read failure" in failed["metadata"]["error"]
    assert recovered["success"] is True
    assert recovered["metadata"]["action"] == "deleted"
    assert recovered["metadata"]["path"] == "daily/2026-01-01/original.md"
    assert not owned_note.exists()
    assert [calls[day] for day in _HISTORY_DAYS] == [2, 2, 1]


async def test_router_dispatch_exception_cleans_lookup_scope(auto_resource_env, monkeypatch):
    """An exception after a processed sub-batch cannot leak a cached index into a reused context."""
    env = auto_resource_env
    _seed_history(env)
    original = env.write_note("daily/2026-01-01/original.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    step = env.processor(_model(), routed=True)
    changes = [{"change": "deleted", "path": "resource/photo.png"}]
    context = RuntimeContext(changes=changes, user_value="preserve")
    context_keys = set(context.data)
    # Interrupt the router after a real processor invocation to test scope cleanup.
    dispatch = step._dispatch_processor  # pylint: disable=protected-access

    async def dispatch_then_fail(*args, **kwargs):
        await dispatch(*args, **kwargs)
        raise RuntimeError("dispatch interrupted after processor completion")

    with patch.object(step, "_dispatch_processor", side_effect=dispatch_then_fail):
        with pytest.raises(RuntimeError, match="dispatch interrupted"):
            await step(context)

    assert not original.exists()
    assert set(context.data) == context_keys
    assert context["changes"] is changes
    assert context["user_value"] == "preserve"
    recreated = env.write_note("daily/2026-01-02/recreated.md", "[[resource/photo.png]]")
    response = await step(context)

    assert response.success is True
    assert response.metadata["results"][0]["metadata"]["path"] == "daily/2026-01-02/recreated.md"
    assert not recreated.exists()
    assert set(context.data) == context_keys
    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 2)


async def _lookup_day(step, context, source="resource/photo.png"):
    """Exercise the lookup helper inside an explicitly shared router-like scope."""
    step.context = context
    return await step._find_loose_resource_day(source)  # pylint: disable=protected-access


@pytest.mark.parametrize("domain", ["workspace", "daily_dir", "file_store"])
async def test_shared_scope_separates_lookup_domains(domain, auto_resource_env, monkeypatch):
    """A processor cannot reuse another workspace, daily layout, or store's cached history."""
    env = auto_resource_env
    env.write_note("daily/2026-01-01/original.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    first = env.processor(_model())
    context = RuntimeContext()

    with _resource_lookup_scope(context):
        assert await _lookup_day(first, context) == "2026-01-01"
        if domain == "workspace":
            other_workspace = env.workspace / "other-workspace"
            write_note(other_workspace / "daily/2026-01-02/other.md", "[[resource/photo.png]]")
            other_app = make_app_context(other_workspace)
            other_store = LocalFileStore(name="read-only-other", app_context=other_app, embedding_store="")

            async def other_daily_list(**kwargs):
                step = DailyListStep(app_context=other_app, file_store=other_store)
                await step(**kwargs)
                return step.context.response

            other_app.jobs = {"daily_list": other_daily_list}
            second = AutoImageResourceStep(app_context=other_app, file_store=other_store)
        elif domain == "daily_dir":
            env.write_note("other-daily/2026-01-02/other.md", "[[resource/photo.png]]")
            monkeypatch.setattr(env.app_context.app_config, "daily_dir", "other-daily")
            second = env.processor(_model())
        else:
            other_store = LocalFileStore(name="read-only-other", app_context=env.app_context, embedding_store="")
            second = AutoImageResourceStep(app_context=env.app_context, file_store=other_store)

        expected = "2026-01-01" if domain == "file_store" else "2026-01-02"
        assert await _lookup_day(second, context) == expected
        if domain == "file_store":
            assert calls["2026-01-01"] == 2

    assert not context.data


@pytest.mark.parametrize("change", ["added", "deleted"])
async def test_mutations_invalidate_other_warmed_store_lookup(change, auto_resource_env, monkeypatch):
    """Separate store indexes of one physical workspace all observe this batch's note mutations."""
    env = auto_resource_env
    _seed_history(env)
    env.write_binary("resource/photo.png", image_bytes())
    if change == "deleted":
        env.write_note("daily/2026-01-01/caption.md", "[[resource/photo.png]]")
    calls = _count_daily_lists(env, monkeypatch)
    other_store = LocalFileStore(name="read-only-observer", app_context=env.app_context, embedding_store="")
    observer = AutoImageResourceStep(app_context=env.app_context, file_store=other_store)
    writer = env.processor(_model())
    context = RuntimeContext(changes=[{"change": change, "path": "resource/photo.png"}])
    previous = "2026-01-01" if change == "deleted" else None

    with _resource_lookup_scope(context):
        assert await _lookup_day(observer, context) == previous
        assert await _lookup_day(writer, context) == previous
        with patch.object(BaseAutoResourceStep, "_today", return_value="2026-01-01"):
            response = await writer(context)
        assert response.success is True
        assert response.metadata["results"][0]["metadata"]["action"] == change
        expected = None if change == "deleted" else "2026-01-01"
        assert await _lookup_day(observer, context) == expected

    assert {day: calls[day] for day in _HISTORY_DAYS} == dict.fromkeys(_HISTORY_DAYS, 2)
