"""Ordinary writers must remain visible to a live resource ownership lookup."""

import asyncio
import os
import sys

import pytest

from reme.components.runtime_context import RuntimeContext

from .auto_resource_test_support import FakeVisionModel, caption_json, image_bytes

pytest_plugins = ("unit.auto_resource_test_plugin",)
pytestmark = pytest.mark.asyncio

_SOURCE = "resource/photo.png"
_ORIGINAL_CARD = "daily/2026-01-01/photo.md"


def _note_text(source):
    """Build a normal note without calling the resource processor."""
    provenance = f"source_resource: '[[{source}]]'\n" if source else ""
    return f"---\nname: photo\ndescription: external note\n{provenance}---\nExternal note body.\n"


async def _after_history_edit(env, monkeypatch, edit, *, change="deleted"):
    """Pause after a harmless first lookup; complete an external write before the next item."""
    env.app_context.metadata = {}
    env.write_note("daily/2025-12-01/archive.md", "[[resource/archive.txt]]")
    env.write_binary(_SOURCE, image_bytes())
    model = FakeVisionModel(caption_json("photo", "Updated image", "A red square."))
    step = env.processor(model)
    step._today = lambda: "2026-01-02"  # pylint: disable=protected-access
    ready, resume = asyncio.Event(), asyncio.Event()
    original_delete = step._handle_delete  # pylint: disable=protected-access

    async def pause_gate(file_path, date_str, note_stem):
        if file_path == "resource/gate.png":
            ready.set()
            await resume.wait()
        await original_delete(file_path, date_str, note_stem)

    monkeypatch.setattr(step, "_handle_delete", pause_gate)
    context = RuntimeContext(
        changes=[
            {"change": "deleted", "path": "resource/gate.png"},
            {"change": change, "path": _SOURCE},
        ],
        marker="preserve",
    )
    original_keys = set(context.data)
    task = asyncio.create_task(step(context))
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)
        await edit()
        resume.set()
        response = await asyncio.wait_for(task, timeout=5)
    finally:
        resume.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert set(context.data) == original_keys
    assert context["marker"] == "preserve"
    results = response.metadata["results"]
    assert [item["path"] for item in results] == ["resource/gate.png", _SOURCE]
    assert results[0]["metadata"]["action"] == "skipped"
    return response, results[1]


@pytest.mark.parametrize("change", ["modified", "deleted"])
@pytest.mark.parametrize("existing_day", [False, True], ids=["new-day", "existing-day"])
async def test_ordinary_write_job_adds_owner_during_resource_batch(
    change,
    existing_day,
    auto_resource_env,
    monkeypatch,
):
    """A normal write job can create the original card after history was cached."""
    env = auto_resource_env
    if existing_day:
        env.write_note("daily/2026-01-01/unrelated.md", "[[resource/other.txt]]")

    async def write_card():
        response = await env.app_context.jobs["write"](
            path=_ORIGINAL_CARD,
            name="photo",
            description="Written through the public write job",
            content="An externally created image card.",
            metadata={"source_resource": f"[[{_SOURCE}]]"},
        )
        assert response.success is True

    response, result = await _after_history_edit(env, monkeypatch, write_card, change=change)

    assert response.success is True
    assert result["metadata"]["action"] == change
    assert result["metadata"]["path"] == _ORIGINAL_CARD
    assert result["metadata"]["index"]["date"] == "2026-01-01"
    assert (env.workspace / _ORIGINAL_CARD).exists() is (change == "modified")
    if change == "modified":
        assert result["metadata"]["created"] is False
    assert not list((env.workspace / "daily/2026-01-02").glob("*.md"))


@pytest.mark.parametrize("restore_mtime", [False, True], ids=["add-provenance", "same-size-restored-mtime"])
async def test_in_place_frontmatter_change_is_seen_without_directory_change(
    restore_mtime,
    auto_resource_env,
    monkeypatch,
):
    """Ownership edits need file metadata checks, including ctime when mtime is restored."""
    env = auto_resource_env
    original = _note_text("resource/other.png" if restore_mtime else None)
    card = env.write_binary(_ORIGINAL_CARD, original.encode())

    async def edit_card():
        before = card.stat()
        directory_before = card.parent.stat()
        replacement = _note_text(_SOURCE).encode()
        if restore_mtime:
            assert len(replacement) == before.st_size
        card.write_bytes(replacement)
        if restore_mtime:
            os.utime(card, ns=(before.st_atime_ns, before.st_mtime_ns))
            after = card.stat()
            assert after.st_size == before.st_size
            assert after.st_mtime_ns == before.st_mtime_ns
            if after.st_ctime_ns == before.st_ctime_ns:
                pytest.skip("Filesystem does not expose this edit through a distinct ctime")
        assert card.parent.stat().st_mtime_ns == directory_before.st_mtime_ns

    response, result = await _after_history_edit(env, monkeypatch, edit_card)

    assert response.success is True
    assert result["metadata"]["action"] == "deleted"
    assert result["metadata"]["path"] == _ORIGINAL_CARD
    assert not card.exists()


@pytest.mark.parametrize("new_source", [None, "resource/other.png"], ids=["remove-owner", "change-owner"])
async def test_external_owner_removal_stops_reusing_previous_date(new_source, auto_resource_env, monkeypatch):
    """A card no longer owned by this resource is preserved; a replacement uses today."""
    env = auto_resource_env
    card = env.write_binary(_ORIGINAL_CARD, _note_text(_SOURCE).encode())
    replacement = _note_text(new_source).encode()

    async def edit_card():
        card.write_bytes(replacement)

    response, result = await _after_history_edit(env, monkeypatch, edit_card, change="modified")

    assert response.success is True
    assert result["metadata"]["created"] is True
    assert result["metadata"]["path"] == "daily/2026-01-02/photo.md"
    assert result["metadata"]["index"]["date"] == "2026-01-02"
    assert card.read_bytes() == replacement


@pytest.mark.parametrize("operation", ["move", "delete"])
async def test_external_move_or_delete_updates_cached_owner(operation, auto_resource_env, monkeypatch):
    """Manual moves and deletion cannot leave a cached historical owner behind."""
    env = auto_resource_env
    card = env.write_binary(_ORIGINAL_CARD, _note_text(_SOURCE).encode())
    destination = env.workspace / "daily/2026-01-03/moved.md"

    async def edit_card():
        if operation == "move":
            destination.parent.mkdir(parents=True)
            card.rename(destination)
        else:
            card.unlink()

    change = "deleted" if operation == "move" else "modified"
    response, result = await _after_history_edit(env, monkeypatch, edit_card, change=change)

    assert response.success is True
    assert result["metadata"]["action"] == change
    expected = "daily/2026-01-03/moved.md" if operation == "move" else "daily/2026-01-02/photo.md"
    assert result["metadata"]["path"] == expected
    assert not card.exists()
    if operation == "move":
        assert not destination.exists()
    else:
        assert result["metadata"]["created"] is True


async def test_external_second_owner_fails_closed_before_mutating_cards(auto_resource_env, monkeypatch):
    """A second exact owner added between resources must retain the duplicate-owner safeguard."""
    env = auto_resource_env
    card = env.write_binary(_ORIGINAL_CARD, _note_text(_SOURCE).encode())
    before = card.read_bytes()
    duplicate = env.workspace / "daily/2026-01-03/duplicate.md"

    async def add_duplicate():
        duplicate.parent.mkdir(parents=True)
        duplicate.write_bytes(before)

    response, result = await _after_history_edit(env, monkeypatch, add_duplicate)

    assert response.success is False
    assert result["success"] is False
    assert result["metadata"]["action"] == "failed"
    assert result["metadata"]["modified"] is False
    assert "Multiple daily resource notes claim resource/photo.png" in result["metadata"]["error"]
    assert _ORIGINAL_CARD in result["metadata"]["error"]
    assert "daily/2026-01-03/duplicate.md" in result["metadata"]["error"]
    assert card.read_bytes() == duplicate.read_bytes() == before


async def test_separate_process_write_is_visible_inside_resource_batch(auto_resource_env, monkeypatch):
    """A writer without this Application or event subscriptions can establish ownership."""
    env = auto_resource_env
    card = env.workspace / _ORIGINAL_CARD

    async def write_in_child():
        code = (
            "from pathlib import Path\n"
            "import sys\n"
            "path = Path(sys.argv[1])\n"
            "path.parent.mkdir(parents=True, exist_ok=True)\n"
            "path.write_text(sys.argv[2], encoding='utf-8')\n"
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            str(card),
            _note_text(_SOURCE),
            cwd=env.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        assert process.returncode == 0, stderr.decode()
        assert card.is_file()

    response, result = await _after_history_edit(env, monkeypatch, write_in_child)

    assert response.success is True
    assert result["metadata"]["action"] == "deleted"
    assert result["metadata"]["path"] == _ORIGINAL_CARD
    assert not card.exists()
