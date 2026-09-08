"""Saved block positions and user-owned caption publication race regressions."""

# pylint: disable=protected-access

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import frontmatter
import pytest

from reme.steps.evolve import _session_images
from reme.steps.evolve._image_caption import ImageCaption

from .test_auto_memory_images import _DAY, _Harness, _image, _message, _png, _text


@pytest.fixture(name="caption")
def caption_boundary(monkeypatch):
    """Only the model boundary is mocked; transcript and note writes are real."""
    model = AsyncMock(
        return_value=ImageCaption(name="board", description="Blue board", caption="Generated board caption."),
    )
    monkeypatch.setattr(_session_images, "caption_image", model)
    return model


def _duplicate_images():
    first, second = _image(_png(1)), _image(_png(2))
    first["id"] = second["id"] = "shared-block-id"
    return first, second


@pytest.mark.asyncio
async def test_duplicate_image_ids_replay_their_own_saved_positions(tmp_path, caption):
    """Distinct image bytes sharing an accepted block ID must remain replayable."""
    first, second = _duplicate_images()
    harness = _Harness(tmp_path)
    initial = await harness.run(
        [_message(_text("Before"), first, _text("Between"), second)],
        include_images=True,
    )
    assert initial.success
    saved = harness.saved()
    provenance = saved[0].metadata["reme_image_sources"]
    assert [item["block_index"] for item in provenance] == [1, 3]
    assert [(tmp_path / item["source_path"]).read_bytes() for item in provenance] == [_png(1), _png(2)]
    # Metadata list order is not block order; the explicit positions own it.
    provenance.reverse()
    fresh = _Harness(tmp_path)
    replay = await fresh.run(saved, include_images=True)
    assert replay.success
    assert replay.metadata["auto_memory_images"]["cache_hits"] == 2
    assert replay.metadata["image_note_paths"] == initial.metadata["image_note_paths"]
    assert [item["block_index"] for item in fresh.saved()[0].metadata["reme_image_sources"]] == [1, 3]
    assert caption.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "duplicate",
        "conflict",
        "wrong-position",
        "swapped-positions",
        "missing-id",
        "bool-index",
        "bad-entry",
        "bad-list",
    ],
)
async def test_ambiguous_saved_provenance_fails_before_rewriting_transcript(tmp_path, caption, kind):
    """No dict overwrite or unmatched lookup may bypass immutable source checks."""
    harness = _Harness(tmp_path)
    assert (await harness.run([_message(*_duplicate_images())], include_images=True)).success
    transcript = tmp_path / "session/dialog/s1.jsonl"
    original = transcript.read_bytes()
    saved = harness.saved()
    provenance = saved[0].metadata["reme_image_sources"]
    if kind in ("duplicate", "conflict"):
        repeated = deepcopy(provenance[0])
        if kind == "conflict":
            repeated["source_sha256"] = provenance[1]["source_sha256"]
            repeated["source_path"] = provenance[1]["source_path"]
        provenance.append(repeated)
    elif kind == "wrong-position":
        provenance[0]["block_index"] = 10
    elif kind == "swapped-positions":
        provenance[0]["block_index"], provenance[1]["block_index"] = 1, 0
    elif kind == "missing-id":
        provenance[0]["block_id"] = "missing-image"
    elif kind == "bool-index":
        provenance[0]["block_index"] = False
    elif kind == "bad-entry":
        provenance.append("not-a-source-record")
    else:
        saved[0].metadata["reme_image_sources"] = {"not": "a source list"}
    result = await _Harness(tmp_path).run(saved, include_images=True)
    assert not result.success
    assert result.metadata["auto_memory_images"]["error_stage"] == "source"
    assert transcript.read_bytes() == original
    assert caption.await_count == 2


@pytest.mark.asyncio
async def test_legacy_unique_image_position_recovers_without_losing_digest_validation(tmp_path, caption):
    """An old sanitizer's stale position is recoverable only for an unambiguous ID."""
    harness = _Harness(tmp_path)
    assert (await harness.run([_message(_image())], include_images=True)).success
    saved = harness.saved()
    saved[0].metadata["reme_image_sources"][0]["block_index"] = 1
    result = await _Harness(tmp_path).run(saved, include_images=True)
    assert result.success
    assert harness.saved()[0].metadata["reme_image_sources"][0]["block_index"] == 0
    # The fallback must still use saved identity, not treat its file URI as new.
    source = saved[0].metadata["reme_image_sources"][0]
    (tmp_path / source["source_path"]).write_bytes(_png(20))
    assert not (await _Harness(tmp_path).run(saved, include_images=True)).success
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("dropped_kind", ["tool-result", "non-image-base64"])
async def test_saved_positions_follow_sanitizer_with_duplicate_image_ids(tmp_path, caption, dropped_kind):
    """Removing non-source blocks must reindex both repeated-ID source mappings."""
    dropped = (
        {"type": "tool_result", "id": "tool-call", "name": "tool", "output": [_text("tool output")]}
        if dropped_kind == "tool-result"
        else {"type": "data", "source": {"type": "base64", "data": "AA==", "media_type": "audio/wav"}}
    )
    first, second = _duplicate_images()
    harness = _Harness(tmp_path)
    initial = await harness.run(
        [_message(dropped, first, _text("Between"), second, role="assistant")],
        include_images=True,
    )
    assert initial.success
    saved = harness.saved()
    assert [block.type for block in saved[0].content] == ["data", "text", "data"]
    assert [item["block_index"] for item in saved[0].metadata["reme_image_sources"]] == [0, 2]
    replay = await _Harness(tmp_path).run(saved, include_images=True)
    assert replay.success
    assert replay.metadata["auto_memory_images"]["cache_hits"] == 2
    assert caption.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["restore", "overwrite", "rename", "canonical"])
async def test_caption_wait_honors_concurrent_user_card_and_fresh_replay(tmp_path, caption, operation):
    """A real file-step restore during model IO cannot create a second owner."""
    harness = _Harness(tmp_path)
    relative = f"daily/{_DAY}/user-restored-caption.md"
    if operation == "overwrite":
        written = await harness.app.jobs["write"](path=relative, content="An ordinary existing note.")
        assert written.success
    started, release = asyncio.Event(), asyncio.Event()

    async def paused_caption(*_args):
        started.set()
        await asyncio.wait_for(release.wait(), timeout=10)
        return ImageCaption(name="unused", description="Unused output", caption="Generated output must not win.")

    caption.side_effect = paused_caption
    memory = asyncio.create_task(harness.run([_message(_image())], include_images=True))
    try:
        await asyncio.wait_for(started.wait(), timeout=10)
        record = harness.step.context.response.metadata["auto_memory_images"]["images"][0]
        canonical = f"daily/{_DAY}/session-image-{record['image_fingerprint']}.md"
        if operation == "canonical":
            relative = canonical
        written = await harness.app.jobs["write"](
            path=relative,
            name="User corrected image",
            description="A user-owned caption",
            content="User corrected the code to ORBIT-43.",
            metadata={
                "kind": "session_image",
                "image_fingerprint": record["image_fingerprint"],
                "source_sha256": record["source_sha256"],
                "source_resource": f"[[{record['source_path']}]]",
            },
        )
        assert written.success
        if operation == "rename":
            destination = f"daily/{_DAY}/renamed-by-user.md"
            moved = await harness.app.jobs["move"](src_path=relative, dst_path=destination, retarget=False)
            assert moved.success
            relative = destination
        user_card = (tmp_path / relative).read_bytes()
    finally:
        release.set()
    initial = await asyncio.wait_for(memory, timeout=10)
    assert initial.success, initial.answer
    assert initial.metadata["image_note_paths"] == [relative]
    assert initial.metadata["auto_memory_images"]["cache_hits"] == 1
    assert not initial.metadata["auto_memory_images"]["notes_modified"]
    assert "ORBIT-43" in harness.agent.calls[0][0]
    assert "Generated output must not win" not in harness.agent.calls[0][0]
    replay = await asyncio.wait_for(_Harness(tmp_path).run(harness.saved(), include_images=True), timeout=10)
    assert replay.success
    assert replay.metadata["image_note_paths"] == [relative]
    assert (tmp_path / relative).read_bytes() == user_card
    cards = list((tmp_path / f"daily/{_DAY}").glob("*.md"))
    assert cards == [tmp_path / relative]
    assert frontmatter.load(cards[0])["image_fingerprint"] == record["image_fingerprint"]
    if operation != "canonical":
        assert not (tmp_path / canonical).exists()
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", ["source-mismatch", "duplicate-owners"])
async def test_caption_wait_reports_restored_identity_conflicts_without_extra_card(tmp_path, caption, conflict):
    """Invalid restored identity is not silently accepted or compounded by a write."""
    harness = _Harness(tmp_path)

    async def restore_conflicting_card(*_args):
        record = harness.step.context.response.metadata["auto_memory_images"]["images"][0]
        for index in range(2 if conflict == "duplicate-owners" else 1):
            written = await harness.app.jobs["write"](
                path=f"daily/{_DAY}/user-card-{index}.md",
                content="User supplied caption.",
                metadata={
                    "kind": "session_image",
                    "image_fingerprint": record["image_fingerprint"],
                    "source_sha256": "0" * 64 if conflict == "source-mismatch" else record["source_sha256"],
                    "source_resource": f"[[{record['source_path']}]]",
                },
            )
            assert written.success
        return ImageCaption(name="unused", description="Unused", caption="Must not create another card.")

    caption.side_effect = restore_conflicting_card
    result = await asyncio.wait_for(harness.run([_message(_image())], include_images=True), timeout=10)
    assert not result.success
    assert result.metadata["auto_memory_images"]["error_stage"] == "caption"
    assert result.metadata["auto_memory_images"]["notes_modified"] is False
    assert not list((tmp_path / f"daily/{_DAY}").glob("session-image-*.md"))
    assert len(list((tmp_path / f"daily/{_DAY}").glob("user-card-*.md"))) == (
        2 if conflict == "duplicate-owners" else 1
    )
    caption.assert_awaited_once()
