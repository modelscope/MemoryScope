"""Durable state and source-path permission boundaries for session memory."""

import json
from unittest.mock import AsyncMock

import frontmatter
import pytest

from reme.steps.evolve import _session_images
from reme.steps.evolve._image_caption import ImageCaption
from reme.steps.evolve.auto_memory_cc import AutoMemoryCCStep

from .test_auto_memory_images import _Harness, _image, _message, _text


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_raises", [False, True], ids=["post-reply-repair", "exception-recovery-repair"])
async def test_failed_link_repair_reports_already_modified_session_note(tmp_path, monkeypatch, agent_raises):
    """A cache-hit retry must not hide an agent write behind failed link repair."""
    caption = AsyncMock(return_value=ImageCaption(name="board", description="A blue board", caption="A blue board."))
    monkeypatch.setattr(_session_images, "caption_image", caption)
    harness = _Harness(tmp_path)
    harness.write_session_card_on_reply()
    messages = [_message(_image())]

    first = await harness.run(messages, include_images=True)
    assert first.success
    note_path = first.metadata["path"]
    note_file = tmp_path / note_path
    before = note_file.read_bytes()
    assert frontmatter.loads(before.decode())["image_notes"]

    async def overwrite_then_maybe_raise():
        post = frontmatter.loads(note_file.read_text(encoding="utf-8"))
        post.content = "The memory agent has already changed this session note."
        post["image_notes"] = "invalid: this must be a list"
        note_file.write_text(frontmatter.dumps(post), encoding="utf-8")
        if agent_raises:
            raise RuntimeError("PRIVATE_PROVIDER_ERROR_SHOULD_NOT_LEAK")

    harness.agent.on_reply = overwrite_then_maybe_raise
    second = await harness.run(messages, include_images=True)

    assert not second.success
    assert note_file.read_bytes() != before
    assert "already changed" in note_file.read_text(encoding="utf-8")
    # No newly materialized attachment or new caption card can mask a missing
    # session-note mutation flag: every image operation was a cache hit.
    assert second.metadata["auto_memory_images"]["source_modified"] is False
    assert second.metadata["auto_memory_images"]["notes_modified"] is False
    assert second.metadata["auto_memory_images"]["cache_hits"] == 1
    assert caption.await_count == 1
    assert second.metadata["modified"] is True
    assert second.metadata["path"] == note_path
    assert second.metadata["created"] is False
    assert "PRIVATE_PROVIDER_ERROR" not in second.answer


@pytest.mark.asyncio
async def test_cc_scoped_to_its_real_source_does_not_require_dialog_permission(tmp_path, monkeypatch):
    """The virtual shared lock is not IO against the unrelated dialog store."""
    harness = _Harness(tmp_path)
    harness.step = AutoMemoryCCStep(
        app_context=harness.app,
        file_store=harness.store,
        agent_wrapper=harness.agent,
    )
    entries = [
        {
            "uuid": "cc-entry-1",
            "type": "user",
            "message": {"role": "user", "content": "Remember the release date."},
        },
    ]
    load_session = AsyncMock(return_value=entries)
    # Never inspect the developer's Claude Code projects; the ReMe-side copy is
    # still exercised as real IO, entirely inside the temporary workspace.
    monkeypatch.setattr(harness.step, "_load_cc_session", load_session)

    response = await harness.run([], date="2026-01-02", _allowed_paths=["daily", "session/claude_code"])

    assert response.success
    assert response.metadata["n_messages"] == 1
    assert len(harness.agent.calls) == 1
    load_session.assert_awaited_once_with("s1")
    transcript = tmp_path / "session" / "claude_code" / "s1.jsonl"
    assert [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines()] == entries
    assert not (tmp_path / "session" / "dialog").exists()


@pytest.mark.asyncio
async def test_regular_memory_still_rejects_disallowed_real_source_write(tmp_path):
    """Bypassing a virtual lock's permission check must not authorize source IO."""
    harness = _Harness(tmp_path)

    with pytest.raises(ValueError, match="No permission to access session evidence"):
        await harness.run([_message(_text("Remember the release date."))], _allowed_paths=["daily"])

    assert not harness.agent.calls
    assert not (tmp_path / "session" / "dialog").exists()
