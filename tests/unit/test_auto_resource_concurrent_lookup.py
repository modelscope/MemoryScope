"""Concurrent resource invocations must not reuse another batch's stale ownership."""

import asyncio

import pytest

from reme.components.runtime_context import RuntimeContext

from .auto_resource_test_support import FakeVisionModel, caption_json, image_bytes

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio


def _processor(env, day, model=None):
    """Use real file jobs and a deterministic model with no external requests."""
    model = model or FakeVisionModel(caption_json("caption", "A sample image", "A red square."))
    step = env.processor(model)
    step._today = lambda: day  # pylint: disable=protected-access
    return step


async def _stop_task(task):
    """Never leave a blocked consumer behind when an assertion fails."""
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _assert_no_active_batches(env):
    """Completed and cancelled invocations must release application subscriptions."""
    state = env.app_context.metadata.get("_auto_resource_lookup_state")
    assert state is None or not state.batches


@pytest.mark.parametrize("consumer_change", ["modified", "deleted"])
@pytest.mark.parametrize("existing_day", [False, True], ids=["new-day", "existing-day"])
async def test_another_batch_new_owner_is_seen_by_later_resource(
    consumer_change,
    existing_day,
    auto_resource_env,
    monkeypatch,
):
    """After B creates a card, A's later event must use B's day, not A's today."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2025-12-01/archive.md", "[[resource/archive.txt]]")
    if existing_day:
        env.write_note("daily/2026-01-01/archive.md", "[[resource/older.txt]]")
    env.write_binary("resource/photo.png", image_bytes())
    consumer = _processor(env, "2026-01-02")
    producer = _processor(env, "2026-01-01")
    ready, resume = asyncio.Event(), asyncio.Event()
    original_delete = consumer._handle_delete  # pylint: disable=protected-access

    async def pause_after_lookup(file_path, date_str, note_stem):
        if file_path == "resource/gate.png":
            ready.set()
            await resume.wait()
        await original_delete(file_path, date_str, note_stem)

    monkeypatch.setattr(consumer, "_handle_delete", pause_after_lookup)
    context = RuntimeContext(
        changes=[
            {"change": "deleted", "path": "resource/gate.png"},
            {"change": consumer_change, "path": "resource/photo.png"},
        ],
    )
    task = asyncio.create_task(consumer(context))
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        created = await env.run(producer, [{"change": "added", "path": "resource/photo.png"}])
        assert created.success is True
        card_path = created.metadata["results"][0]["metadata"]["path"]
        assert card_path.startswith("daily/2026-01-01/")
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
        result = response.metadata["results"][-1]
        assert result["success"] is True
        assert result["metadata"]["action"] == consumer_change
        assert result["metadata"]["path"] == card_path
        assert (env.workspace / card_path).exists() is (consumer_change != "deleted")
        assert not list((env.workspace / "daily/2026-01-02").glob("*.md"))
    finally:
        resume.set()
        await _stop_task(task)
    _assert_no_active_batches(env)


@pytest.mark.parametrize("read_phase", ["history", "dirty-day"])
async def test_concurrent_write_during_daily_list_does_not_lose_invalidation(
    read_phase,
    auto_resource_env,
    monkeypatch,
):
    """An awaited stale scan must not erase an invalidation arriving while it runs."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2026-01-01/gate.md", "[[resource/gate.png]]")
    env.write_binary("resource/photo.png", image_bytes())
    consumer = _processor(env, "2026-01-02")
    producer = _processor(env, "2026-01-01")
    ready, resume = asyncio.Event(), asyncio.Event()
    daily_list = env.app_context.jobs["daily_list"]
    consumer_reads = 0
    blocked_read = 1 if read_phase == "history" else 3
    task = None

    async def pause_stale_response(**kwargs):
        nonlocal consumer_reads
        response = await daily_list(**kwargs)
        if asyncio.current_task() is task and kwargs["date"] == "2026-01-01":
            consumer_reads += 1
            if consumer_reads == blocked_read:
                ready.set()
                await resume.wait()
        return response

    monkeypatch.setitem(env.app_context.jobs, "daily_list", pause_stale_response)
    changes = [{"change": "deleted", "path": "resource/photo.png"}]
    if read_phase == "dirty-day":
        changes.insert(0, {"change": "deleted", "path": "resource/gate.png"})
    task = asyncio.create_task(env.run(consumer, changes))
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        created = await env.run(producer, [{"change": "added", "path": "resource/photo.png"}])
        assert created.success is True
        card_path = created.metadata["results"][0]["metadata"]["path"]
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
        result = response.metadata["results"][-1]
        assert result["success"] is True
        assert result["metadata"]["action"] == "deleted"
        assert result["metadata"]["path"] == card_path
        assert not (env.workspace / card_path).exists()
    finally:
        resume.set()
        await _stop_task(task)
    _assert_no_active_batches(env)


@pytest.mark.parametrize("cancel_phase", ["history", "processor"])
async def test_cancelled_batch_does_not_leak_lookup_into_reused_context(
    cancel_phase,
    auto_resource_env,
    monkeypatch,
):
    """Cancellation during a scan or a processor releases state before the next call."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2026-01-01/archive.md", "[[resource/archive.txt]]")
    step = _processor(env, "2026-01-02")
    context = RuntimeContext(changes=[{"change": "deleted", "path": "resource/photo.png"}], marker="keep")
    keys = set(context.data)
    ready = asyncio.Event()
    never = asyncio.Event()
    daily_list = env.app_context.jobs["daily_list"]
    original_delete = step._handle_delete  # pylint: disable=protected-access

    async def block_history(**kwargs):
        response = await daily_list(**kwargs)
        ready.set()
        await never.wait()
        return response

    async def block_processor(*args):
        ready.set()
        await never.wait()
        await original_delete(*args)

    with monkeypatch.context() as patcher:
        if cancel_phase == "history":
            patcher.setitem(env.app_context.jobs, "daily_list", block_history)
        else:
            patcher.setattr(step, "_handle_delete", block_processor)
        task = asyncio.create_task(step(context))
        try:
            await asyncio.wait_for(ready.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await _stop_task(task)
    assert set(context.data) == keys
    assert context["marker"] == "keep"
    _assert_no_active_batches(env)
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    response = await step(context)
    assert response.success is True
    assert response.metadata["results"][0]["metadata"]["action"] == "deleted"
    assert not card.exists()
    assert set(context.data) == keys
    _assert_no_active_batches(env)


async def test_cancelled_writer_invalidates_other_batch_after_partial_write(auto_resource_env, monkeypatch):
    """Cancelling after a card is saved still notifies an overlapping reader."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2025-12-01/archive.md", "[[resource/archive.txt]]")
    env.write_binary("resource/photo.png", image_bytes())
    consumer = _processor(env, "2026-01-02")
    producer = _processor(env, "2026-01-01")
    ready, resume, written = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_delete = consumer._handle_delete  # pylint: disable=protected-access

    async def pause_consumer(file_path, date_str, note_stem):
        if file_path == "resource/gate.png":
            ready.set()
            await resume.wait()
        await original_delete(file_path, date_str, note_stem)

    async def pause_after_write(_day):
        written.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(consumer, "_handle_delete", pause_consumer)
    monkeypatch.setattr(producer, "_refresh_day_index", pause_after_write)
    consumer_task = asyncio.create_task(
        env.run(
            consumer,
            [
                {"change": "deleted", "path": "resource/gate.png"},
                {"change": "deleted", "path": "resource/photo.png"},
            ],
        ),
    )
    producer_task = None
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        producer_task = asyncio.create_task(env.run(producer, [{"change": "added", "path": "resource/photo.png"}]))
        await asyncio.wait_for(written.wait(), timeout=5)
        card = env.workspace / "daily/2026-01-01/caption.md"
        assert card.exists()
        producer_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await producer_task
        resume.set()
        response = await asyncio.wait_for(consumer_task, timeout=5)
        result = response.metadata["results"][-1]
        assert result["success"] is True
        assert result["metadata"]["action"] == "deleted"
        assert result["metadata"]["path"] == "daily/2026-01-01/caption.md"
        assert not card.exists()
    finally:
        resume.set()
        await _stop_task(consumer_task)
        if producer_task is not None:
            await _stop_task(producer_task)
    _assert_no_active_batches(env)


async def test_another_batch_deletion_removes_cached_day(auto_resource_env, monkeypatch):
    """After another invocation deletes a card, a new card uses this invocation's day."""
    env = auto_resource_env
    env.app_context.metadata = {}
    old_card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    env.write_binary("resource/photo.png", image_bytes())
    consumer = _processor(env, "2026-01-02")
    producer = _processor(env, "2026-01-01")
    ready, resume = asyncio.Event(), asyncio.Event()
    original_delete = consumer._handle_delete  # pylint: disable=protected-access

    async def pause_consumer(file_path, date_str, note_stem):
        if file_path == "resource/gate.png":
            ready.set()
            await resume.wait()
        await original_delete(file_path, date_str, note_stem)

    monkeypatch.setattr(consumer, "_handle_delete", pause_consumer)
    task = asyncio.create_task(
        env.run(
            consumer,
            [
                {"change": "deleted", "path": "resource/gate.png"},
                {"change": "added", "path": "resource/photo.png"},
            ],
        ),
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        removed = await env.run(producer, [{"change": "deleted", "path": "resource/photo.png"}])
        assert removed.success is True
        assert not old_card.exists()
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
        result = response.metadata["results"][-1]
        assert result["success"] is True
        assert result["metadata"]["created"] is True
        assert result["metadata"]["path"] == "daily/2026-01-02/caption.md"
        assert not list((env.workspace / "daily/2026-01-01").glob("*.md"))
    finally:
        resume.set()
        await _stop_task(task)
    _assert_no_active_batches(env)


@pytest.mark.parametrize("mutation", [False, True], ids=["no-op", "continuous-writes"])
async def test_concurrent_activity_does_not_cause_unbounded_refresh(mutation, auto_resource_env, monkeypatch):
    """No-ops preserve a scan; uninterrupted real writes fail closed in bounded reads."""
    env = auto_resource_env
    env.app_context.metadata = {}
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    env.write_note("daily/2026-01-01/churn.md", "[[resource/churn.png]]")
    env.write_binary("resource/churn.png", image_bytes())
    consumer = _processor(env, "2026-01-02")
    model = FakeVisionModel(caption_json("churn", "Changed image", "version 0"))
    producer = _processor(env, "2026-01-01", model)
    daily_list = env.app_context.jobs["daily_list"]
    consumer_reads = 0
    task = None

    async def inject_concurrent_activity(**kwargs):
        nonlocal consumer_reads
        response = await daily_list(**kwargs)
        if asyncio.current_task() is task and kwargs["date"] == "2026-01-01":
            consumer_reads += 1
            assert consumer_reads <= 5, "lookup failed to bound its refresh attempts"
            if mutation:
                model.text = caption_json("churn", "Changed image", f"version {consumer_reads}")
                changes = [{"change": "modified", "path": "resource/churn.png"}]
            else:
                changes = [{"change": "deleted", "path": "resource/missing.png"}]
            other = await asyncio.create_task(env.run(producer, changes))
            assert other.success is True
            assert other.metadata["modified"] is mutation
        return response

    monkeypatch.setitem(env.app_context.jobs, "daily_list", inject_concurrent_activity)
    task = asyncio.create_task(env.run(consumer, [{"change": "deleted", "path": "resource/photo.png"}]))
    try:
        response = await asyncio.wait_for(task, timeout=5)
        result = response.metadata["results"][0]
        if mutation:
            assert result["success"] is False
            assert result["metadata"]["action"] == "failed"
            assert "ownership kept changing" in result["metadata"]["error"]
            assert 2 <= consumer_reads <= 4
            assert card.exists()
        else:
            assert result["success"] is True
            assert result["metadata"]["action"] == "deleted"
            assert consumer_reads == 2  # One history scan and one fresh, targeted ownership check.
            assert not card.exists()
    finally:
        await _stop_task(task)
    _assert_no_active_batches(env)
