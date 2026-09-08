"""Cross-mode serialization and durable state under auto-memory failures."""

# pylint: disable=protected-access

import asyncio
import importlib
from unittest.mock import AsyncMock

import frontmatter
import pytest

from reme.steps.evolve import _session_images, _session_io, auto_memory
from reme.steps.evolve._image_caption import ImageCaption

from .test_auto_memory_images import _DAY, _Harness, _image, _message, _png, _text


@pytest.fixture(name="caption_mock", autouse=True)
def mock_caption(monkeypatch):
    """All scenarios use deterministic model output, never an external API."""
    caption = AsyncMock(return_value=ImageCaption(name="board", description="A board", caption="Project ORBIT-42."))
    monkeypatch.setattr(_session_images, "caption_image", caption)
    return caption


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_fails", [False, True])
async def test_off_rewrite_preserves_existing_image_links(tmp_path, caption_mock, agent_fails):
    """Neither a full rewrite nor a later agent error may erase old image links."""
    on = _Harness(tmp_path)
    on.write_session_card_on_reply()
    assert (await on.run([_message(_image())], include_images=True)).success
    path = tmp_path / "daily" / _DAY / "memory.md"
    links = frontmatter.load(path)["image_notes"]
    off = _Harness(tmp_path)
    off.write_session_card_on_reply()
    writer = off.agent.on_reply

    async def write_then_fail():
        await writer()
        raise RuntimeError("agent failed after writing")

    if agent_fails:
        off.agent.on_reply = write_then_fail
        with pytest.raises(RuntimeError):
            await off.run([_message(_text("New text only."), msg_id="text")])
        assert off.step.context.response.metadata["path"] == f"daily/{_DAY}/memory.md"
    else:
        assert (await off.run([_message(_text("New text only."), msg_id="text")])).success
    assert frontmatter.load(path)["image_notes"] == links
    assert caption_mock.await_count == 1
    assert "auto_memory_images" not in off.step.context.response.metadata


@pytest.mark.asyncio
async def test_off_update_waits_for_on_transaction(tmp_path):
    """The disabled path uses the same lock and retains both message deltas."""
    on, off = _Harness(tmp_path), _Harness(tmp_path)
    on.write_session_card_on_reply()
    off.write_session_card_on_reply()
    writer = on.agent.on_reply
    started, release = asyncio.Event(), asyncio.Event()

    async def held_reply():
        started.set()
        await release.wait()
        await writer()

    on.agent.on_reply = held_reply
    image_task = asyncio.create_task(on.run([_message(_image())], include_images=True))
    text_task = None
    try:
        await asyncio.wait_for(started.wait(), 5)
        text_task = asyncio.create_task(off.run([_message(_text("Text update"), msg_id="text")]))
        await asyncio.sleep(0.05)
        assert not off.agent.calls
    finally:
        release.set()
        tasks = [image_task, *([text_task] if text_task else [])]
        results = await asyncio.wait_for(asyncio.gather(*tasks), 5)
    assert all(result.success for result in results)
    assert {message.id for message in off.saved()} == {"m1", "text"}
    assert frontmatter.load(tmp_path / "daily" / _DAY / "memory.md")["image_notes"]


@pytest.mark.asyncio
@pytest.mark.parametrize("include_images", [False, True])
@pytest.mark.parametrize("raises", [False, True])
async def test_final_index_failure_reports_saved_note(tmp_path, monkeypatch, include_images, raises):
    """Index return errors and exceptions must expose the already saved note."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    refresh = (
        AsyncMock(side_effect=OSError("private signed URL")) if raises else AsyncMock(return_value={"error": "bad"})
    )
    monkeypatch.setattr(auto_memory, "refresh_day_index", refresh)
    response = await harness.run([_message(_image(), _text("Remember this"))], include_images=include_images)
    assert not response.success
    assert response.metadata["path"] == f"daily/{_DAY}/memory.md"
    assert response.metadata["modified"] and response.metadata["created"]
    assert response.metadata["index"]["success"] is False
    assert "private" not in str(response)
    assert (tmp_path / response.metadata["path"]).is_file()


@pytest.mark.asyncio
async def test_failed_rewrite_preserves_transcript_and_retry_succeeds(tmp_path, monkeypatch):
    """A failed same-ID image replacement keeps every previous source message."""
    harness = _Harness(tmp_path)
    original = [_message(_image(), msg_id="first"), _message(_text("Keep this fact"), msg_id="second")]
    assert (await harness.run(original, include_images=True)).success
    path = tmp_path / "session/dialog/s1.jsonl"
    before = path.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(_session_io.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("disk full")))
        failed = await harness.run([_message(_image(_png(255)), msg_id="first")], include_images=True)
    assert not failed.success
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".reme-session-*"))
    retried = await harness.run([_message(_image(_png(255)), msg_id="first")], include_images=True)
    assert retried.success
    assert {message.id for message in harness.saved()} == {"first", "second"}
    assert path.read_bytes() != before


@pytest.mark.asyncio
async def test_invalid_saved_message_is_not_silently_discarded(tmp_path):
    """Malformed source JSONL remains user-owned, rather than being repaired away."""
    harness = _Harness(tmp_path)
    path = tmp_path / "session/dialog/s1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{"user-edited": "preserve"}\n')
    with pytest.raises(ValueError, match="invalid message"):
        await harness.run([_message(_text("New fact"))])
    assert path.read_bytes() == b'{"user-edited": "preserve"}\n'
    assert not harness.agent.calls


@pytest.mark.asyncio
async def test_agent_failure_after_creation_keeps_path_and_image_links(tmp_path):
    """Newly written notes stay observable and linked after a model error."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    writer = harness.agent.on_reply

    async def fail_after_write():
        await writer()
        raise RuntimeError("private model request")

    harness.agent.on_reply = fail_after_write
    response = await harness.run([_message(_image())], include_images=True)
    assert not response.success
    assert response.metadata["modified"] and response.metadata["created"]
    note = frontmatter.load(tmp_path / response.metadata["path"])
    assert note["image_notes"] == [f"[[{response.metadata['image_note_paths'][0]}]]"]
    assert "private" not in str(response)


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_fails", [False, True])
async def test_reused_renamed_card_retargets_only_known_missing_links(tmp_path, caption_mock, agent_fails):
    """A renamed caption must not leave the old canonical image_notes link dangling."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    first = await harness.run([_message(_image())], include_images=True)
    assert first.success
    old = first.metadata["image_note_paths"][0]
    renamed = f"daily/{_DAY}/user-edited-card.md"
    (tmp_path / old).rename(tmp_path / renamed)
    session_path = tmp_path / first.metadata["path"]
    post = frontmatter.load(session_path)
    unknown = f"[[daily/{_DAY}/user-kept-reference.md]]"
    post["image_notes"].append(unknown)
    session_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    writer = harness.agent.on_reply

    async def write_then_fail():
        await writer()
        raise RuntimeError("model error after write")

    if agent_fails:
        harness.agent.on_reply = write_then_fail
    response = await harness.run(harness.saved(), include_images=True)
    assert response.success is not agent_fails
    links = frontmatter.load(session_path)["image_notes"]
    assert f"[[{old}]]" not in links
    assert links == [f"[[{renamed}]]", unknown]
    assert caption_mock.await_count == 1


@pytest.mark.asyncio
async def test_link_retarget_does_not_remove_occupied_or_unknown_paths(tmp_path):
    """Only a known, now-missing canonical card can be normalized to its owner."""
    harness = _Harness(tmp_path)
    await harness.run([])
    fingerprint = "a" * 64
    old = f"daily/{_DAY}/session-image-{fingerprint}.md"
    path = tmp_path / old
    path.parent.mkdir(parents=True)
    path.write_text("User-owned occupant", encoding="utf-8")
    relocated = {fingerprint: f"daily/{_DAY}/renamed.md"}
    assert harness.step._current_image_link(f"[[{old}]]", relocated) == f"[[{old}]]"
    for link in ("A note", "[[../outside.md]]", f"[[other/{_DAY}/session-image-{fingerprint}.md]]"):
        assert harness.step._current_image_link(link, relocated) == link


@pytest.mark.asyncio
async def test_enabled_text_only_agent_error_reports_memory_stage(tmp_path, caption_mock):
    """An enabled no-image call must not mislabel a text-model error as image IO."""
    harness = _Harness(tmp_path)
    harness.agent.on_reply = AsyncMock(side_effect=RuntimeError("private request"))
    response = await harness.run([_message(_text("Remember this"))], include_images=True)
    assert not response.success
    assert response.metadata["auto_memory_images"]["error_stage"] == "memory"
    assert response.metadata["auto_memory_images"]["image_count"] == 0
    assert response.metadata["auto_memory_images"]["source_modified"]
    caption_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_renamed_card_body_links_are_repaired_without_relying_on_agent(tmp_path, caption_mock):
    """Known targets in prose, embeds and anchored aliases track the current card."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    first = await harness.run([_message(_image())], include_images=True)
    old = first.metadata["image_note_paths"][0]
    renamed = f"daily/{_DAY}/reviewed.md"
    (tmp_path / old).rename(tmp_path / renamed)
    session_path = tmp_path / first.metadata["path"]
    post = frontmatter.load(session_path)
    post.content = f"Project facts. [[{old}]], ![[{old}#Caption|Board]], [[user-owned/missing.md]]."
    session_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    # Simulate an agent that leaves both stale metadata and stale prose alone.
    harness.agent.on_reply = None
    response = await harness.run(harness.saved(), include_images=True)
    assert response.success
    updated = frontmatter.load(session_path)
    assert updated["image_notes"] == [f"[[{renamed}]]"]
    assert updated.content == f"Project facts. [[{renamed}]], ![[{renamed}#Caption|Board]], [[user-owned/missing.md]]."
    assert old not in session_path.read_text(encoding="utf-8")
    assert caption_mock.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_fails", [False, True])
async def test_link_repair_failure_keeps_metadata_and_body_atomic(tmp_path, monkeypatch, agent_fails):
    """A failed publication cannot leave provenance and body targets half-updated."""
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    first = await harness.run([_message(_image())], include_images=True)
    old = first.metadata["image_note_paths"][0]
    renamed = f"daily/{_DAY}/reviewed.md"
    (tmp_path / old).rename(tmp_path / renamed)
    path = tmp_path / first.metadata["path"]
    post = frontmatter.load(path)
    post.content = f"Image: [[{old}]]"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    before = path.read_bytes()
    harness.agent.on_reply = AsyncMock(side_effect=RuntimeError("model failed")) if agent_fails else None
    publish = auto_memory.atomic_write

    async def failing_repair(target, *args, **kwargs):
        if target == path:
            raise OSError("disk failure during link repair")
        await publish(target, *args, **kwargs)

    monkeypatch.setattr(auto_memory, "atomic_write", failing_repair)
    response = await harness.run(harness.saved(), include_images=True)
    assert not response.success
    assert not response.metadata["auto_memory_images"]["notes_modified"]
    assert not response.metadata["auto_memory_images"]["source_modified"]
    assert path.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement_is_text", [False, True])
async def test_off_history_backfill_keeps_saved_image_message(tmp_path, monkeypatch, caption_mock, replacement_is_text):
    """A forced JSONL rewrite in off mode keeps source identity, without image IO."""
    original = _message(_text("Before"), _image(), _text("After"), metadata={"external": "retained"})
    on = _Harness(tmp_path)
    assert (await on.run([original], include_images=True)).success
    saved = on.saved()[0].model_dump()
    evidence = {path: path.read_bytes() for path in (tmp_path / "session/images").iterdir()}
    incoming = _message(_text("Same-ID text replacement")) if replacement_is_text else original
    earlier = _message(_text("Earlier fact"), msg_id="earlier", created_at=f"{_DAY}T00:00:00Z")
    off = _Harness(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(_session_images.SessionImages, "_read_source", AsyncMock(side_effect=AssertionError("image IO")))
        patch.setattr(_session_images, "normalize_image", lambda *_: pytest.fail("image preprocessing while off"))
        response = await off.run([incoming, earlier], include_images=False)
    assert response.success
    assert "auto_memory_images" not in response.metadata
    assert [msg.id for msg in off.saved()] == ["earlier", original.id]
    assert off.saved()[1].model_dump() == saved
    assert all(path.read_bytes() == data for path, data in evidence.items())
    assert original.content[1].source.type == "base64"
    replay = await _Harness(tmp_path).run(off.saved(), include_images=True)
    assert replay.success
    assert replay.metadata["auto_memory_images"]["image_count"] == 1
    assert replay.metadata["auto_memory_images"]["cache_hits"] == 1
    assert caption_mock.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("writer_job", ["write", "frontmatter_update"])
async def test_link_repair_merges_concurrent_user_links_under_one_lock(tmp_path, monkeypatch, writer_job):
    """Real user file jobs finish before repair re-reads their current metadata."""
    first = _Harness(tmp_path)
    first.write_session_card_on_reply()
    initial = await first.run([_message(_image())], include_images=True)
    old = initial.metadata["image_note_paths"][0]
    renamed = f"daily/{_DAY}/renamed.md"
    (tmp_path / old).rename(tmp_path / renamed)
    relative = initial.metadata["path"]
    target = tmp_path / relative
    post = frontmatter.load(target)
    unknown = "[[user-owned/manual.md]]"
    post["image_notes"].append(unknown)
    post["user_field"] = "keep this"
    post.content = f"User prose with ![[{old}#Caption|Board]]."
    writing, preserving, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    module = importlib.import_module(f"reme.steps.file_io.{writer_job}")
    real_lock = module.get_path_lock
    current = _Harness(tmp_path)
    real_preserve = current.step._preserve_image_links

    class PausedWriterLock:
        """Hold the real shared file lock before the user's write begins."""

        def __init__(self, lock):
            self.lock = lock

        async def __aenter__(self):
            await self.lock.acquire()
            writing.set()
            await release.wait()

        async def __aexit__(self, *_args):
            self.lock.release()

    async def paused_lock(path):
        return PausedWriterLock(await real_lock(path))

    async def observed_preserve(*args, **kwargs):
        preserving.set()
        await real_preserve(*args, **kwargs)

    monkeypatch.setattr(module, "get_path_lock", paused_lock)
    monkeypatch.setattr(current.step, "_preserve_image_links", observed_preserve)
    writer_kwargs = {"path": relative, "metadata": post.metadata}
    if writer_job == "write":
        writer_kwargs.update(content=post.content, name=post["name"], description=post["description"])
    else:
        # FrontmatterUpdate leaves the original body untouched.
        post.content = frontmatter.load(target).content
    writer = asyncio.create_task(current.app.jobs[writer_job](**writer_kwargs))
    memory = None
    try:
        await asyncio.wait_for(writing.wait(), 5)
        memory = asyncio.create_task(current.run(first.saved(), include_images=True))
        await asyncio.wait_for(preserving.wait(), 5)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(writer, *([memory] if memory else [])), 5)
    assert all(result.success for result in results)
    updated = frontmatter.load(target)
    assert updated["image_notes"] == [f"[[{renamed}]]", unknown]
    assert updated["user_field"] == "keep this"
    assert updated.content == post.content.replace(old, renamed)
