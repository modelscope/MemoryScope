"""Keep upstream optional tag semantics intact alongside session image memory."""

# pylint: disable=protected-access

import json
from unittest.mock import AsyncMock

import frontmatter
import pytest

from reme.steps.evolve import _session_images
from reme.steps.evolve._image_caption import ImageCaption
from reme.steps.evolve.auto_memory_cc import AutoMemoryCCStep

from .test_auto_memory_images import _DAY, _Harness, _image, _message, _text

_RAW_TAGS = [" GPT-5 ", "gpt-5", "C++", "two words", 100, True, "++", ".NET"]
_NORMALIZED_TAGS = ["GPT-5", "C++", "100", ".NET"]


@pytest.fixture(name="caption")
def caption_fixture(monkeypatch):
    """Keep model access mocked while source, caption card, and note IO stay real."""
    caption = AsyncMock(return_value=ImageCaption(name="board", description="A blue board", caption="A blue board."))
    monkeypatch.setattr(_session_images, "caption_image", caption)
    return caption


async def _write_card(harness, *, name="memory", path=None, metadata=None):
    """A real write intentionally replaces prior frontmatter, as an agent fallback can."""
    response = await harness.app.jobs["write"](
        path=path or f"daily/{_DAY}/memory.md",
        name=name,
        description="Project memory",
        content="Remember the project board.",
        metadata={"session_id": "s1", **(metadata or {})},
    )
    assert response.success


@pytest.mark.asyncio
@pytest.mark.parametrize("include_images", [False, True])
@pytest.mark.parametrize("enable_tags", [None, False, True], ids=["tags-default", "tags-off", "tags-on"])
@pytest.mark.parametrize("existing", [False, True], ids=["create", "update"])
async def test_image_and_tag_switches_preserve_upstream_note_contract(
    tmp_path,
    caption,
    include_images,
    enable_tags,
    existing,
):
    """Tags are opt-in Step configuration; image processing neither enables nor disables them."""
    harness = _Harness(tmp_path)
    # These isolated notes have no indexed inbound links; still exercise the
    # real copy/retarget/unlink move instead of mocking the rename hook.
    harness.store.file_graph = None
    if enable_tags is not None:
        harness.step.kwargs["enable_tags"] = enable_tags
    if existing:
        await _write_card(harness, metadata={"tags": ["outdated"]})

    async def replace_note():
        # Missing source_conversation exercises upstream's post-write repair.
        await _write_card(harness, name="renamed" if existing else "memory", metadata={"tags": _RAW_TAGS})

    harness.agent.on_reply = replace_note
    response = await harness.run([_message(_text("Remember this board."), _image())], include_images=include_images)

    assert response.success
    expected_path = f"daily/{_DAY}/{'renamed' if existing else 'memory'}.md"
    assert response.metadata["path"] == expected_path
    post = frontmatter.load(tmp_path / expected_path)
    assert post["tags"] == (_NORMALIZED_TAGS if enable_tags else _RAW_TAGS)
    assert post["session_id"] == "s1"
    if existing or enable_tags:
        assert post["source_conversation"] == "[[session/dialog/s1.jsonl]]"
    else:
        # Upstream does not normalize a newly created note while tags are off.
        assert "source_conversation" not in post
    if existing:
        assert not (tmp_path / "daily" / _DAY / "memory.md").exists()

    user_prompt, options = harness.agent.calls[-1]
    assert ("`tags`" in options["system_prompt"]) is bool(enable_tags)
    assert ('"tags"' in user_prompt) is bool(enable_tags)
    if include_images:
        assert post["image_notes"] == [f"[[{path}]]" for path in response.metadata["image_note_paths"]]
        assert len(post["image_notes"]) == 1
        assert harness.saved()[0].metadata["reme_image_sources"]
        caption.assert_awaited_once()
    else:
        assert "image_notes" not in post
        assert "auto_memory_images" not in response.metadata
        assert not (tmp_path / "session" / "images").exists()
        caption.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("include_images", [False, True])
@pytest.mark.parametrize("existing", [False, True], ids=["create", "update"])
async def test_enabled_tags_always_add_empty_list_without_losing_image_links(
    tmp_path,
    caption,
    include_images,
    existing,
):
    """A model omitting tags still gets the upstream mandatory empty-list normalization."""
    harness = _Harness(tmp_path)
    harness.step.kwargs["enable_tags"] = True
    if existing:
        await _write_card(harness, metadata={"tags": ["old"]})

    async def replace_note():
        await _write_card(harness)

    harness.agent.on_reply = replace_note
    response = await harness.run([_message(_image())], include_images=include_images)

    assert response.success
    post = frontmatter.load(tmp_path / response.metadata["path"])
    assert post["tags"] == []
    assert post["source_conversation"] == "[[session/dialog/s1.jsonl]]"
    assert bool(post.get("image_notes")) is include_images
    assert caption.await_count == int(include_images)


@pytest.mark.asyncio
@pytest.mark.parametrize("enable_tags", [False, True])
async def test_image_links_survive_text_only_rewrite_with_tag_normalization(tmp_path, caption, enable_tags):
    """Turning images off must retain previous image provenance while respecting the tag switch."""
    harness = _Harness(tmp_path)
    harness.step.kwargs["enable_tags"] = enable_tags

    async def replace_note():
        await _write_card(harness, metadata={"tags": _RAW_TAGS})

    harness.agent.on_reply = replace_note
    first = await harness.run([_message(_image())], include_images=True)
    assert first.success
    previous_links = frontmatter.load(tmp_path / first.metadata["path"])["image_notes"]

    second = await harness.run([_message(_text("The board is approved."), msg_id="m2")], include_images=False)

    assert second.success
    post = frontmatter.load(tmp_path / second.metadata["path"])
    assert post["image_notes"] == previous_links
    assert post["tags"] == (_NORMALIZED_TAGS if enable_tags else _RAW_TAGS)
    assert harness.saved()[0].metadata["reme_image_sources"]
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True], ids=["create", "update"])
async def test_tag_enabled_agent_failure_keeps_image_provenance_and_supports_retry(tmp_path, caption, existing):
    """Recovery preserves durable links without claiming a failed agent completed tag normalization."""
    harness = _Harness(tmp_path)
    harness.step.kwargs["enable_tags"] = True
    if existing:
        await _write_card(harness, metadata={"tags": ["old"], "image_notes": ["[[user-owned/manual.md]]"]})

    async def replace_then_fail():
        await _write_card(harness, metadata={"tags": _RAW_TAGS})
        raise RuntimeError("PRIVATE_MODEL_ERROR")

    messages = [_message(_image())]
    harness.agent.on_reply = replace_then_fail
    failed = await harness.run(messages, include_images=True)

    assert not failed.success
    assert failed.metadata["auto_memory_images"]["error_stage"] == "memory"
    assert failed.metadata["modified"] is True
    assert "PRIVATE_MODEL_ERROR" not in failed.answer
    note_path = tmp_path / failed.metadata["path"]
    links = [f"[[{path}]]" for path in failed.metadata["image_note_paths"]]
    if existing:
        links.insert(0, "[[user-owned/manual.md]]")
    assert frontmatter.load(note_path)["image_notes"] == links

    harness.agent.on_reply = None
    recovered = await harness.run(harness.saved(), include_images=True)

    assert recovered.success
    assert recovered.metadata["auto_memory_images"]["cache_hits"] == 1
    post = frontmatter.load(note_path)
    assert post["tags"] == _NORMALIZED_TAGS
    assert post["image_notes"] == links
    assert post["source_conversation"] == "[[session/dialog/s1.jsonl]]"
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("enable_tags", [False, True])
@pytest.mark.parametrize("include_images", [False, True])
async def test_cc_keeps_its_source_layout_and_tag_contract(tmp_path, monkeypatch, caption, enable_tags, include_images):
    """Inherited optional tags must not redirect CC transcripts or require a vision model."""
    harness = _Harness(tmp_path)
    harness.step = AutoMemoryCCStep(
        app_context=harness.app,
        file_store=harness.store,
        agent_wrapper=harness.agent,
        enable_tags=enable_tags,
        include_images=include_images,
    )
    entries = [{"uuid": "cc-1", "type": "user", "message": {"role": "user", "content": "Remember GPT-5."}}]
    monkeypatch.setattr(harness.step, "_load_cc_session", AsyncMock(return_value=entries))

    async def replace_note():
        await _write_card(harness, metadata={"tags": _RAW_TAGS})

    harness.agent.on_reply = replace_note
    response = await harness.run([], date=_DAY, _allowed_paths=["daily", "session/claude_code"])

    assert response.success
    post = frontmatter.load(tmp_path / response.metadata["path"])
    assert post["tags"] == (_NORMALIZED_TAGS if enable_tags else _RAW_TAGS)
    if enable_tags:
        assert post["source_conversation"] == "[[session/claude_code/s1.jsonl]]"
    assert "image_notes" not in post
    transcript = tmp_path / "session" / "claude_code" / "s1.jsonl"
    assert [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines()] == entries
    assert not (tmp_path / "session" / "dialog").exists()
    assert not (tmp_path / "session" / "images").exists()
    caption.assert_not_awaited()
