"""Filesystem snapshots keep ownership lookups fresh without re-parsing stable history."""

import asyncio
import errno
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from reme.schema import Response
from reme.steps.evolve import base_auto_resource

from .auto_resource_test_support import FakeVisionModel, caption_json, write_note

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio


def _processor(env):
    """Use real file jobs with no model requests on these deletion paths."""
    model = FakeVisionModel(caption_json("caption", "A sample image", "A red square."))
    step = env.processor(model)
    step._today = lambda: "2026-01-03"  # pylint: disable=protected-access
    return step


async def _stop_task(task):
    """Clean up an event-blocked consumer even when an assertion fails."""
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _symlink(link, target, *, directory=False):
    """Skip only environments that cannot create test symlinks."""
    try:
        link.symlink_to(target, target_is_directory=directory)
    except NotImplementedError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")
    except OSError as exc:
        if exc.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.EOPNOTSUPP}:
            pytest.skip(f"Symlinks unavailable: {exc}")
        raise


@pytest.mark.parametrize("read_phase", ["history", "dirty-day", "new-day"])
async def test_external_change_during_lookup_is_seen_by_next_resource(read_phase, auto_resource_env, monkeypatch):
    """Keep the pre-read version so an external write is detected by the next resource."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2026-01-01/gate.md", "[[resource/gate.png]]")
    consumer = _processor(env)
    daily_list = env.app_context.jobs["daily_list"]
    ready, resume = asyncio.Event(), asyncio.Event()
    reads = 0
    # Deleting gate takes a history read and a targeted read; its dirty refresh is third.
    blocked_read = 3 if read_phase == "dirty-day" else 1

    async def pause_stale_response(**kwargs):
        nonlocal reads
        response = await daily_list(**kwargs)
        if kwargs["date"] == "2026-01-01":
            reads += 1
            if reads == blocked_read:
                ready.set()
                await resume.wait()
        return response

    monkeypatch.setitem(env.app_context.jobs, "daily_list", pause_stale_response)
    changes = [
        {"change": "deleted", "path": "resource/missing.png"},
        {"change": "deleted", "path": "resource/photo.png"},
    ]
    if read_phase == "dirty-day":
        changes.insert(0, {"change": "deleted", "path": "resource/gate.png"})
    task = asyncio.create_task(env.run(consumer, changes))
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        day = "2026-01-02" if read_phase == "new-day" else "2026-01-01"
        card = env.write_note(f"daily/{day}/photo.md", "[[resource/photo.png]]")
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
        assert response.metadata["results"][-2]["metadata"]["action"] == "skipped"
        result = response.metadata["results"][-1]
        assert result["success"] is True
        assert result["metadata"]["action"] == "deleted"
        assert result["metadata"]["path"] == f"daily/{day}/photo.md"
        assert not card.exists()
    finally:
        resume.set()
        await _stop_task(task)


@pytest.mark.parametrize("alias_change", ["retarget", "missing-target"])
@pytest.mark.parametrize("alias_count", [1, 2], ids=["single-owner", "duplicate-owners"])
async def test_external_alias_change_refreshes_all_logical_dates(
    alias_change,
    alias_count,
    auto_resource_env,
    monkeypatch,
):
    """Alias identities and newly available targets are checked on later resources."""
    env = auto_resource_env
    env.app_context.metadata = {}
    old_target = env.workspace / "storage/old"
    new_target = env.workspace / "storage/new"
    env.write_note("storage/old/archive.md", "[[resource/archive.txt]]")
    if alias_change == "retarget":
        card = env.write_note("storage/new/photo.md", "[[resource/photo.png]]")
    else:
        card = new_target / "photo.md"
    daily = env.workspace / "daily"
    daily.mkdir()
    aliases = [daily / f"2026-01-0{index}" for index in range(1, alias_count + 1)]
    for alias in aliases:
        _symlink(alias, old_target if alias_change == "retarget" else new_target, directory=True)
    consumer = _processor(env)
    ready, resume = asyncio.Event(), asyncio.Event()
    original_delete = consumer._handle_delete  # pylint: disable=protected-access

    async def pause_after_lookup(file_path, date_str, note_stem):
        if file_path == "resource/gate.png":
            ready.set()
            await resume.wait()
        await original_delete(file_path, date_str, note_stem)

    monkeypatch.setattr(consumer, "_handle_delete", pause_after_lookup)
    task = asyncio.create_task(
        env.run(
            consumer,
            [
                {"change": "deleted", "path": "resource/gate.png"},
                {"change": "deleted", "path": "resource/photo.png"},
            ],
        ),
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        if alias_change == "retarget":
            for alias in aliases:
                alias.unlink()
                _symlink(alias, new_target, directory=True)
        else:
            card = env.write_note("storage/new/photo.md", "[[resource/photo.png]]")
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
        result = response.metadata["results"][-1]
        if alias_count == 1:
            assert result["success"] is True
            assert result["metadata"]["action"] == "deleted"
            assert result["metadata"]["path"] == "daily/2026-01-01/photo.md"
            assert not card.exists()
        else:
            assert result["success"] is False
            assert "Multiple daily resource notes claim" in result["metadata"]["error"]
            assert card.exists()
        assert (old_target / "archive.md").exists()
    finally:
        resume.set()
        await _stop_task(task)


@pytest.mark.parametrize("failure_phase", ["initial", "refresh"])
async def test_snapshot_failure_remains_retryable(failure_phase, auto_resource_env, monkeypatch):
    """A stat/scan failure fails one resource without committing an incomplete view."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2026-01-01/gate.md", "[[resource/gate.png]]")
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    consumer = _processor(env)
    snapshot = consumer._resource_note_snapshot  # pylint: disable=protected-access
    original_delete = consumer._handle_delete  # pylint: disable=protected-access
    warmed = False
    failed = False

    def fail_snapshot_once(*args, **kwargs):
        nonlocal failed
        if not failed and (failure_phase == "initial" or warmed):
            failed = True
            raise OSError("temporary snapshot scan failure")
        return snapshot(*args, **kwargs)

    async def mark_warmed(file_path, date_str, note_stem):
        nonlocal warmed
        await original_delete(file_path, date_str, note_stem)
        if file_path == "resource/gate.png":
            warmed = True

    monkeypatch.setattr(consumer, "_resource_note_snapshot", fail_snapshot_once)
    monkeypatch.setattr(consumer, "_handle_delete", mark_warmed)
    changes = [
        {"change": "deleted", "path": "resource/photo.png"},
        {"change": "deleted", "path": "resource/photo.png"},
    ]
    if failure_phase == "refresh":
        changes.insert(0, {"change": "deleted", "path": "resource/gate.png"})
    response = await env.run(consumer, changes)
    results = response.metadata["results"]
    assert results[-2]["success"] is False
    assert "temporary snapshot scan failure" in results[-2]["metadata"]["error"]
    assert results[-1]["success"] is True
    assert results[-1]["metadata"]["action"] == "deleted"
    assert not card.exists()


async def test_failed_changed_day_read_does_not_accept_new_fingerprint(auto_resource_env, monkeypatch):
    """A failed refresh must not mark an externally added owner as already indexed."""
    env = auto_resource_env
    env.app_context.metadata = {}
    env.write_note("daily/2026-01-01/gate.md", "[[resource/gate.png]]")
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/other.png]]")
    consumer = _processor(env)
    original_delete = consumer._handle_delete  # pylint: disable=protected-access
    daily_list = env.app_context.jobs["daily_list"]
    changed = False
    failed = False

    async def change_owner_after_gate(file_path, date_str, note_stem):
        nonlocal changed
        await original_delete(file_path, date_str, note_stem)
        if file_path == "resource/gate.png":
            env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
            changed = True

    async def fail_refresh_once(**kwargs):
        nonlocal failed
        if changed and not failed:
            failed = True
            return Response(success=False, answer="temporary changed-day read failure")
        return await daily_list(**kwargs)

    monkeypatch.setattr(consumer, "_handle_delete", change_owner_after_gate)
    monkeypatch.setitem(env.app_context.jobs, "daily_list", fail_refresh_once)
    response = await env.run(
        consumer,
        [
            {"change": "deleted", "path": "resource/gate.png"},
            {"change": "deleted", "path": "resource/photo.png"},
            {"change": "deleted", "path": "resource/photo.png"},
        ],
    )
    results = response.metadata["results"]
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "temporary changed-day read failure" in results[1]["metadata"]["error"]
    assert results[2]["success"] is True
    assert results[2]["metadata"]["action"] == "deleted"
    assert not card.exists()


async def test_unchanged_snapshots_do_not_reparse_historical_notes(auto_resource_env, monkeypatch):
    """Every resource checks metadata, but unchanged historical days are parsed once."""
    env = auto_resource_env
    env.app_context.metadata = {}
    days = ("2025-12-01", "2025-12-02")
    for day in days:
        for index in range(8):
            env.write_note(f"daily/{day}/archive-{index}.md", f"[[resource/archive-{day}-{index}.txt]]")
    daily_list = env.app_context.jobs["daily_list"]
    calls = Counter()

    async def counted_daily_list(**kwargs):
        calls[kwargs["date"]] += 1
        return await daily_list(**kwargs)

    monkeypatch.setitem(env.app_context.jobs, "daily_list", counted_daily_list)
    response = await env.run(
        _processor(env),
        [{"change": "deleted", "path": f"resource/missing-{index}.png"} for index in range(8)],
    )
    assert response.success is True
    assert response.metadata["modified"] is False
    assert response.metadata["processed"] == 8
    assert {day: calls[day] for day in days} == dict.fromkeys(days, 1)


@pytest.mark.parametrize("cycle", ["self", "mutual"])
async def test_cyclic_note_links_do_not_block_unrelated_resource(cycle, auto_resource_env):
    """Like daily_list, metadata scans skip cyclic links that are not readable files."""
    env = auto_resource_env
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    link = card.parent / "loop.md"
    _symlink(link, "loop.md" if cycle == "self" else "other-loop.md")
    if cycle == "mutual":
        _symlink(card.parent / "other-loop.md", "loop.md")
    response = await env.run(_processor(env), [{"change": "deleted", "path": "resource/photo.png"}])
    assert response.success is True
    assert response.metadata["results"][0]["metadata"]["action"] == "deleted"
    assert not card.exists()
    assert link.is_symlink()


@pytest.mark.parametrize("cycle", ["self", "mutual"])
async def test_cyclic_daily_links_do_not_block_unrelated_resource(cycle, auto_resource_env):
    """Unresolvable date directories do not hide a normal historical owner."""
    env = auto_resource_env
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    link = card.parent.parent / "2025-12-01"
    _symlink(link, "2025-12-01" if cycle == "self" else "2025-12-02", directory=True)
    if cycle == "mutual":
        _symlink(link.with_name("2025-12-02"), "2025-12-01", directory=True)
    response = await env.run(_processor(env), [{"change": "deleted", "path": "resource/photo.png"}])
    assert response.success is True
    assert response.metadata["results"][0]["metadata"]["action"] == "deleted"
    assert not card.exists()
    assert link.is_symlink()


@pytest.mark.parametrize("failure_site", ["directory-stat", "scandir", "file-stat"])
@pytest.mark.parametrize("error_number", [errno.ELOOP, errno.EACCES, errno.EIO], ids=["loop", "permission", "io"])
async def test_snapshot_handles_only_loop_errors(failure_site, error_number, tmp_path, monkeypatch):
    """Exercise late OS errors on every Python version, without bypassing safety failures."""
    day = tmp_path / "daily" / "2026-01-01"
    day.mkdir(parents=True)
    (day / "valid.md").write_text("A normal note.", encoding="utf-8")
    error = OSError(error_number, "snapshot probe failed")
    original_stat = Path.stat
    with base_auto_resource.os.scandir(day) as entries:
        valid_entries = list(entries)

    def stat_with_failure(path, *args, **kwargs):
        if path == day:
            raise error
        return original_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        if failure_site == "directory-stat":
            patch.setattr(Path, "stat", stat_with_failure)
        elif failure_site == "scandir":
            patch.setattr(base_auto_resource.os, "scandir", Mock(side_effect=error))
        else:
            unreadable = SimpleNamespace(
                name="unreadable.md",
                is_symlink=lambda: False,
                stat=Mock(side_effect=error),
            )
            patch.setattr(
                base_auto_resource.os,
                "scandir",
                lambda _: nullcontext(iter([unreadable, *valid_entries])),
            )
        if error_number != errno.ELOOP:
            with pytest.raises(OSError) as caught:
                base_auto_resource._snapshot_note_day(tmp_path, day)  # pylint: disable=protected-access
            assert caught.value is error
            return
        snapshot = base_auto_resource._snapshot_note_day(tmp_path, day)  # pylint: disable=protected-access

    if failure_site == "file-stat":
        assert snapshot is not None
        assert set(snapshot.files) == {"valid.md"}
    else:
        assert snapshot is None
    assert (day / "valid.md").read_text(encoding="utf-8") == "A normal note."


async def test_escaping_note_link_fails_before_daily_list(auto_resource_env, monkeypatch):
    """Metadata inspection refuses an escaping Markdown target before parsing any notes."""
    env = auto_resource_env
    card = env.write_note("daily/2026-01-01/photo.md", "[[resource/photo.png]]")
    outside = write_note(env.workspace.parent / "outside.md", "[[resource/other.png]]")
    original = outside.read_bytes()
    _symlink(card.parent / "escape.md", outside)
    calls = 0
    daily_list = env.app_context.jobs["daily_list"]

    async def counted_daily_list(**kwargs):
        nonlocal calls
        calls += 1
        return await daily_list(**kwargs)

    monkeypatch.setitem(env.app_context.jobs, "daily_list", counted_daily_list)
    response = await env.run(_processor(env), [{"change": "deleted", "path": "resource/photo.png"}])
    result = response.metadata["results"][0]
    assert result["success"] is False
    assert "invalid resource note path" in result["metadata"]["error"]
    assert calls == 0
    assert card.exists()
    assert outside.read_bytes() == original
