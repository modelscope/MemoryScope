"""Session image source identity, bounded reuse, and failure recovery regressions."""

# pylint: disable=protected-access

import asyncio
from unittest.mock import AsyncMock, MagicMock

import frontmatter
import httpx
import pytest

from reme.steps.evolve import _session_images
from reme.steps.evolve._image_caption import ImageCaption

from .test_auto_memory_images import _Harness, _image, _message, _png, _url


@pytest.fixture(name="caption")
def caption_boundary(monkeypatch):
    """No test reaches a provider; only the visual model boundary is mocked."""
    model = AsyncMock(
        return_value=ImageCaption(name="board", description="A blue board", caption="Board code ORBIT-42."),
    )
    monkeypatch.setattr(_session_images, "caption_image", model)
    return model


def _internal_link(harness):
    (harness.path / "session").mkdir()
    (harness.path / "attachments").mkdir()
    (harness.path / "session/images").symlink_to("../attachments", target_is_directory=True)


@pytest.mark.asyncio
async def test_internal_source_symlink_preserves_logical_uri_and_replay(tmp_path, caption):
    """Workspace-contained directory aliases retain logical durable provenance."""
    harness = _Harness(tmp_path / "workspace")
    _internal_link(harness)
    first = await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    source = saved[0].metadata["reme_image_sources"][0]
    assert str(saved[0].content[0].source.url).endswith("/" + source["source_path"])
    assert (harness.path / source["source_path"]).is_file()
    assert first.metadata["auto_memory_images"]["images"][0]["source_modified"]
    second = await harness.run(saved, include_images=True)
    assert second.success
    assert not second.metadata["auto_memory_images"]["images"][0]["source_modified"]
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_resolved_internal_source_uri_remains_replayable(tmp_path, caption):
    """Previously persisted resolved aliases upgrade to logical source URLs."""
    harness = _Harness(tmp_path)
    _internal_link(harness)
    await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    source = saved[0].metadata["reme_image_sources"][0]
    saved[0].content[0].source.url = (harness.path / source["source_path"]).resolve().as_uri()
    result = await harness.run(saved, include_images=True)
    assert result.success
    assert str(harness.saved()[0].content[0].source.url).endswith("/" + source["source_path"])
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
async def test_saved_identity_survives_legacy_single_file_alias_without_trusting_changed_bytes(
    tmp_path,
    caption,
    changed,
):
    """Legacy single-file aliases still enforce the saved immutable digest."""
    harness = _Harness(tmp_path)
    await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    source = saved[0].metadata["reme_image_sources"][0]
    canonical = harness.path / source["source_path"]
    alias = harness.path / "user-named-photo.png"
    canonical.rename(alias)
    canonical.symlink_to("../../user-named-photo.png")
    saved[0].content[0].source.url = alias.as_uri()
    if changed:
        alias.write_bytes(_png(15))
    response = await harness.run(saved, include_images=True)
    assert response.success is not changed
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_saved_identity_cannot_be_bypassed_by_changing_filename(tmp_path, caption):
    """Changing a saved URL basename does not discard its source identity."""
    harness = _Harness(tmp_path)
    await harness.run([_message(_image())], include_images=True)
    saved = harness.saved()
    other = harness.path / "different-image.png"
    other.write_bytes(_png(80))
    saved[0].content[0].source.url = other.as_uri()
    result = await harness.run(saved, include_images=True)
    assert not result.success
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_relative_internal_symlink_survives_workspace_move(tmp_path, caption):
    """Portable internal aliases replay after the entire workspace moves."""
    harness = _Harness(tmp_path / "before")
    _internal_link(harness)
    await harness.run([_message(_image())], include_images=True)
    harness.path.rename(tmp_path / "after")
    moved = _Harness(tmp_path / "after")
    response = await moved.run(moved.saved(), include_images=True)
    assert response.success
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_repeated_source_validates_once_and_warm_caption_never_encodes(tmp_path, caption, monkeypatch):
    """Duplicate bytes validate once, while a caption hit needs no encoding."""
    validate = MagicMock(wraps=_session_images.validate_image)
    normalize = MagicMock(wraps=_session_images.normalize_image)
    monkeypatch.setattr(_session_images, "validate_image", validate)
    monkeypatch.setattr(_session_images, "normalize_image", normalize)
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image(), _image(), _image())], include_images=True)
    assert first.success
    validate.assert_called_once()
    normalize.assert_called_once()
    caption.assert_awaited_once()
    validate.reset_mock()
    normalize.reset_mock()
    second = await harness.run(harness.saved(), include_images=True)
    assert second.success
    validate.assert_called_once()
    normalize.assert_not_called()
    assert second.metadata["auto_memory_images"]["cache_hits"] == 3


def _http_mock(monkeypatch, requested):
    client_class = httpx.AsyncClient

    def handle(request):
        requested.append(str(request.url))
        return httpx.Response(200, content=_png(), headers={"content-type": "image/png"})

    monkeypatch.setattr(
        _session_images.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs),
    )


@pytest.mark.asyncio
async def test_repeated_http_source_downloads_once_per_invocation(tmp_path, caption, monkeypatch):
    """A repeated remote source reuses a verified file without storing its URL."""
    requested = []
    _http_mock(monkeypatch, requested)
    harness = _Harness(tmp_path)
    url = "https://example.test/board.png?signature=never-cache-this-plaintext"
    result = await harness.run([_message(_url(url), _url(url))], include_images=True)
    assert result.success
    assert requested == [url]
    assert url not in str(result.metadata)
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_http_locator_cache_is_bounded_and_evicts_safely(tmp_path, caption, monkeypatch):
    """Evicting a locator permits a new download rather than stale byte reuse."""
    # Replace the default argument too: the production limit is a fixed 256.
    remember = _session_images.SessionImages._remember

    def bounded(cache, key, value, limit=1):
        return remember(cache, key, value, limit)

    monkeypatch.setattr(_session_images.SessionImages, "_remember", staticmethod(bounded))
    requested = []
    _http_mock(monkeypatch, requested)
    urls = ["https://example.test/a.png", "https://example.test/b.png", "https://example.test/a.png"]
    harness = _Harness(tmp_path)
    result = await harness.run([_message(*[_url(url) for url in urls])], include_images=True)
    assert result.success
    assert requested == urls
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_source_change_before_caption_cache_hit_is_rejected(tmp_path, caption, monkeypatch):
    """Caption reuse rechecks source bytes after materialization yielded."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    path = harness.path / first.metadata["auto_memory_images"]["images"][0]["source_path"]
    enrich = _session_images.SessionImages.enrich

    async def change_before_enrich(images, messages, day):
        path.write_bytes(_png(10))
        return await enrich(images, messages, day)

    monkeypatch.setattr(_session_images.SessionImages, "enrich", change_before_enrich)
    response = await harness.run(harness.saved(), include_images=True)
    assert not response.success
    assert response.metadata["auto_memory_images"]["images"][0]["status"] == "failed"
    caption.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["source", "note"])
async def test_cancel_after_atomic_publication_keeps_traceable_committed_path(tmp_path, caption, monkeypatch, kind):
    """A cancellation racing with publication reports committed evidence."""
    harness = _Harness(tmp_path)
    real_write = _session_images.atomic_write
    cancelled = False

    async def publish_then_cancel(path, content, **kwargs):
        nonlocal cancelled
        await real_write(path, content, **kwargs)
        if not cancelled and (
            (kind == "source" and path.suffix == ".png") or (kind == "note" and path.suffix == ".md")
        ):
            cancelled = True
            raise asyncio.CancelledError()

    monkeypatch.setattr(_session_images, "atomic_write", publish_then_cancel)
    message = _message(_image())
    with pytest.raises(asyncio.CancelledError):
        await harness.run([message], include_images=True)
    metadata = harness.step.context.response.metadata
    record = metadata["auto_memory_images"]["images"][0]
    field = "source_path" if kind == "source" else "note_path"
    assert (harness.path / record[field]).is_file()
    assert record["source_modified" if kind == "source" else "note_modified"]
    if kind == "note":
        assert metadata["image_note_paths"] == [record["note_path"]]
        assert record["status"] == "ready"
    retried = await harness.run([message], include_images=True)
    assert retried.success
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_index_failure_reports_card_then_retry_repairs_without_caption(tmp_path, caption, monkeypatch):
    """A derived-index failure preserves card identity and avoids recaptioning."""
    harness = _Harness(tmp_path)
    refresh = _session_images.refresh_day_index
    monkeypatch.setattr(
        _session_images,
        "refresh_day_index",
        AsyncMock(return_value={"error": "do-not-publish-secret"}),
    )
    first = await harness.run([_message(_image())], include_images=True)
    assert not first.success
    record = first.metadata["auto_memory_images"]["images"][0]
    assert record["status"] == "ready"
    assert record["note_modified"]
    assert first.metadata["image_note_paths"] == [record["note_path"]]
    indexes = first.metadata["auto_memory_images"]["indexes"]
    assert indexes[0]["error_type"] == "RuntimeError"
    assert "do-not-publish-secret" not in str(first)
    monkeypatch.setattr(_session_images, "refresh_day_index", refresh)
    second = await harness.run(harness.saved(), include_images=True)
    assert second.success
    assert (harness.path / "daily/2026-01-02.md").is_file()
    assert not second.metadata["auto_memory_images"]["images"][0]["note_modified"]
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_current_warm_day_index_is_not_rebuilt(tmp_path, caption, monkeypatch):
    """An unchanged index needs no full daily-note scan on cache hits."""
    harness = _Harness(tmp_path)
    await harness.run([_message(_image())], include_images=True)
    refresh = AsyncMock(wraps=_session_images.refresh_day_index)
    monkeypatch.setattr(_session_images, "refresh_day_index", refresh)
    response = await harness.run(harness.saved(), include_images=True)
    assert response.success
    refresh.assert_not_awaited()
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_warm_day_index_missing_link_is_repaired_even_with_newer_mtime(tmp_path, caption, monkeypatch):
    """A partial index cannot masquerade as current just because it is newer."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    index = harness.path / "daily/2026-01-02.md"
    index.write_text("A user-owned introduction without the generated links.", encoding="utf-8")
    refresh = AsyncMock(wraps=_session_images.refresh_day_index)
    monkeypatch.setattr(_session_images, "refresh_day_index", refresh)
    response = await harness.run(harness.saved(), include_images=True)
    assert response.success
    refresh.assert_awaited_once()
    assert first.metadata["image_note_paths"][0] in index.read_text(encoding="utf-8")
    assert "user-owned introduction" in index.read_text(encoding="utf-8")
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_renamed_corrected_card_is_reused_and_its_index_repaired(tmp_path, caption):
    """User-owned names and corrected captions survive the next invocation."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    old = harness.path / first.metadata["image_note_paths"][0]
    renamed = old.with_name("user-selected-title.md")
    post = frontmatter.loads(old.read_text(encoding="utf-8"))
    post.content = "User-corrected image description ORBIT-43."
    old.rename(renamed)
    renamed.write_text(frontmatter.dumps(post), encoding="utf-8")
    response = await harness.run(harness.saved(), include_images=True)
    assert response.success
    assert "ORBIT-43" in harness.agent.calls[-1][0]
    assert response.metadata["image_note_paths"] == [renamed.relative_to(harness.path).as_posix()]
    assert not old.exists()
    assert "user-selected-title.md" in (harness.path / "daily/2026-01-02.md").read_text(encoding="utf-8")
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_conflicting_source_frontmatter_is_not_a_caption_cache_hit(tmp_path, caption):
    """A caption claiming another source fails rather than becoming evidence."""
    harness = _Harness(tmp_path)
    first = await harness.run([_message(_image())], include_images=True)
    path = harness.path / first.metadata["image_note_paths"][0]
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    post["source_sha256"] = "0" * 64
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    response = await harness.run(harness.saved(), include_images=True)
    assert not response.success
    assert response.metadata["auto_memory_images"]["cache_hits"] == 0
    caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_different_sessions_publish_distinct_cards(tmp_path, caption):
    """Catalog writes serialize briefly while all visual model calls overlap."""
    (tmp_path / "daily/2026-01-02").mkdir(parents=True)
    entered = 0
    all_entered = asyncio.Event()

    async def model_boundary(*_args, **_kwargs):
        nonlocal entered
        entered += 1
        if entered == 20:
            all_entered.set()
        await asyncio.wait_for(all_entered.wait(), timeout=10)
        return ImageCaption(name="board", description="A blue board", caption="Board code ORBIT-42.")

    caption.side_effect = model_boundary
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                _Harness(tmp_path).run(
                    [_message(_image(_png(index)), msg_id=f"image-{index}")],
                    session_id=f"session-{index}",
                    include_images=True,
                )
                for index in range(20)
            ],
        ),
        timeout=30,
    )
    assert entered == 20
    assert all(response.success for response in responses), [
        response.answer for response in responses if not response.success
    ]
    assert len(list((tmp_path / "daily/2026-01-02").glob("session-image-*.md"))) == 20
    assert caption.await_count == 20
