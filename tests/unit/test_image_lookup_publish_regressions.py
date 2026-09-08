"""Real image-card publication checks for differential invocation-local lookup."""

from unittest.mock import AsyncMock

import frontmatter
import pytest

from reme.steps.evolve import _session_images
from reme.steps.evolve._image_caption import ImageCaption
from reme.steps.evolve._image_note_lookup import ImageNoteLookup

from .test_auto_memory_images import _Harness, _image, _message, _png

# pylint: disable=protected-access
_CAPTION = ImageCaption(name="board", description="A board", caption="Board code ORBIT-42.")
_DAY = "2026-01-02"


@pytest.mark.asyncio
@pytest.mark.parametrize("old_count", [0, 100])
async def test_real_batch_publication_reads_each_identity_once(tmp_path, monkeypatch, old_count):
    """Ten real new cards read M+10 identities, not 10*M+45 old identities."""
    day = tmp_path / "daily" / _DAY
    day.mkdir(parents=True)
    for index in range(old_count):
        (day / f"historical-{index}.md").write_text("User note.", encoding="utf-8")
    caption = AsyncMock(return_value=_CAPTION)
    monkeypatch.setattr(_session_images, "caption_image", caption)
    original_read = ImageNoteLookup._read_identity
    reads = []

    def counted(lookup, relative):
        reads.append(relative)
        return original_read(lookup, relative)

    monkeypatch.setattr(ImageNoteLookup, "_read_identity", counted)
    result = await _Harness(tmp_path).run(
        [_message(_image(_png(index)), msg_id=f"m{index}") for index in range(10)],
        include_images=True,
    )
    assert result.success, result.answer
    assert caption.await_count == 10
    assert len(list(day.glob("session-image-*.md"))) == 10
    assert len(reads) == len(set(reads)) == old_count + 10


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_path", [False, True])
async def test_real_external_write_in_publication_window_is_not_hidden(tmp_path, monkeypatch, existing_path):
    """Real WriteStep restores are seen even between atomic write and cache update."""
    harness = _Harness(tmp_path)
    day = tmp_path / "daily" / _DAY
    day.mkdir(parents=True)
    if existing_path:
        (day / "restored.md").write_text("Previously an ordinary note.", encoding="utf-8")
    monkeypatch.setattr(_session_images, "caption_image", AsyncMock(return_value=_CAPTION))
    original_write = _session_images.atomic_write

    async def write_and_restore(path, content, **kwargs):
        await original_write(path, content, **kwargs)
        if path.name.startswith("session-image-"):
            post = frontmatter.loads(content)
            result = await harness.app.jobs["write"](
                path=f"daily/{_DAY}/restored.md",
                name="User-restored caption",
                description="User restored this independently.",
                content="User-owned caption body.",
                metadata=dict(post.metadata),
            )
            assert result.success

    monkeypatch.setattr(_session_images, "atomic_write", write_and_restore)
    result = await harness.run([_message(_image())], include_images=True)
    assert not result.success
    assert result.metadata["auto_memory_images"]["error_type"] == "ValueError"
    assert (day / "restored.md").is_file()
    assert result.metadata["auto_memory_images"]["images"][0]["note_modified"]
