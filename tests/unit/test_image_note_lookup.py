"""Zero-model contracts for a bounded, editable image-note ownership snapshot."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest

from reme.steps.evolve._image_note_lookup import ImageNoteLookup, _SnapshotChangedError
from reme.steps.file_io._file_io import get_path_lock
from reme.steps.file_io._path import _check_path_permission, resolve_path

# pylint: disable=protected-access
_FP = "a" * 64
_OTHER = "b" * 64
_RECORD = {"source_sha256": "c" * 64, "source_path": "session/images/" + "c" * 64 + ".png"}


def _lookup(workspace, *, allowed=None, limit=1024 * 1024):
    def resolve(relative):
        target, error = resolve_path(workspace, relative)
        if error or target is None or not _check_path_permission(workspace, target, allowed):
            raise ValueError("Denied image-note path")
        return target

    return ImageNoteLookup(workspace, "daily", resolve=resolve, max_note_bytes=limit)


def _note(workspace, name="renamed.md", *, day="2026-01-01", fingerprint=_FP, body="User caption.", **metadata):
    path = workspace / "daily" / day / name
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(
        body,
        **{
            "kind": "session_image",
            "image_fingerprint": fingerprint,
            "source_sha256": _RECORD["source_sha256"],
            "source_resource": f"[[{_RECORD['source_path']}]]",
            **metadata,
        },
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_metadata_lookup_survives_name_and_day_move(tmp_path):
    """User-selected filenames and legal date moves do not erase ownership."""
    path = _note(tmp_path)
    lookup = _lookup(tmp_path)
    assert (await lookup.find(_FP, _RECORD))[0] == "daily/2026-01-01/renamed.md"
    destination = tmp_path / "daily/2026-02-02/renamed-again.md"
    destination.parent.mkdir()
    path.rename(destination)
    assert (await lookup.find(_FP, _RECORD))[0] == "daily/2026-02-02/renamed-again.md"


@pytest.mark.asyncio
async def test_cached_locator_reads_current_body_and_validates_current_identity(tmp_path):
    """Metadata snapshots never freeze a caption or bypass provenance checks."""
    path = _note(tmp_path)
    lookup = _lookup(tmp_path)
    await lookup.find(_FP, _RECORD)
    _note(tmp_path, body="User corrected the image description.")
    assert (await lookup.find(_FP, _RECORD))[1].content == "User corrected the image description."
    assert all("content" not in row for state in lookup._snapshot.days.values() for row in state.notes.values())
    _note(tmp_path, source_sha256="d" * 64)
    with pytest.raises(ValueError, match="source does not match"):
        await lookup.find(_FP, _RECORD)
    assert path.is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [{"source_resource": "[[other.png]]"}, {"kind": "other"}])
async def test_cached_owner_provenance_and_kind_cannot_be_reassigned(tmp_path, metadata):
    """An existing candidate is checked again even without a directory change."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    await lookup.find(_FP, _RECORD)
    _note(tmp_path, **metadata)
    with pytest.raises(ValueError):
        await lookup.find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_new_invocation_rediscovers_in_place_fingerprint_edit(tmp_path):
    """External unselected identity edits are visible on the next invocation."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    assert await lookup.find(_OTHER, _RECORD) is None
    _note(tmp_path, fingerprint=_OTHER)
    # Unselected in-place edits are outside the call-level snapshot guarantee.
    assert (await _lookup(tmp_path).find(_OTHER, _RECORD))[0].endswith("renamed.md")
    lookup.invalidate_day("2026-01-01")
    assert (await lookup.find(_OTHER, _RECORD))[0].endswith("renamed.md")


@pytest.mark.asyncio
@pytest.mark.parametrize("day", ["2026-01-01", "2026-02-01"])
async def test_duplicate_owners_are_never_last_writer_wins(tmp_path, day):
    """Both same-day and cross-day ambiguity require an explicit repair."""
    _note(tmp_path)
    _note(tmp_path, name="second.md", day=day)
    with pytest.raises(ValueError, match="Multiple daily notes"):
        await _lookup(tmp_path).find(_FP, _RECORD)


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [{"kind": "other"}, {"image_fingerprint": _OTHER}])
async def test_reserved_hash_filename_cannot_hide_another_document(tmp_path, metadata):
    """A fixed-name occupant cannot become a negative just by changing metadata."""
    name = f"session-image-{_FP}.md"
    path = _note(tmp_path, name=name)
    post = frontmatter.load(path)
    post.metadata.update(metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    with pytest.raises(ValueError, match="occupied or has changed"):
        await _lookup(tmp_path).find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_empty_caption_is_not_a_cache_hit(tmp_path):
    """An existing empty image note fails visibly rather than regenerating it."""
    _note(tmp_path, body="  ")
    with pytest.raises(ValueError, match="Stored image note is empty"):
        await _lookup(tmp_path).find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_incomplete_scan_never_publishes_or_poison_next_lookup(tmp_path):
    """Repairing a failed first scan permits a complete subsequent scan."""
    _note(tmp_path)
    damaged = tmp_path / "daily/2026-01-02/broken.md"
    damaged.parent.mkdir()
    damaged.write_text("---\ninvalid: [\n---\nbody", encoding="utf-8")
    lookup = _lookup(tmp_path)
    with pytest.raises(Exception):
        await lookup.find(_FP, _RECORD)
    assert lookup._snapshot is None
    damaged.write_text("An ordinary Markdown note.", encoding="utf-8")
    assert await lookup.find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_failed_dirty_refresh_keeps_previous_complete_snapshot(tmp_path):
    """A partial dirty-day read cannot replace the complete prior index."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    await lookup.find(_FP, _RECORD)
    previous = lookup._snapshot
    _note(tmp_path, name="new.md", fingerprint=_OTHER)
    original_read = lookup._read_identity

    def failing_read(relative, *args):
        if relative.endswith("new.md"):
            raise PermissionError("fixture")
        return original_read(relative, *args)

    with patch.object(lookup, "_read_identity", side_effect=failing_read):
        with pytest.raises(PermissionError):
            await lookup.find(_OTHER, _RECORD)
    assert lookup._snapshot is previous
    assert await lookup.find(_OTHER, _RECORD)


@pytest.mark.asyncio
async def test_concurrent_new_card_retries_a_full_snapshot(tmp_path):
    """A new card during enumeration is discovered without publishing half a scan."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    original_read = lookup._read_identity
    inserted = False

    def insert_after_read(relative):
        nonlocal inserted
        metadata = original_read(relative)
        assert lookup._snapshot is None
        if not inserted:
            inserted = True
            _note(tmp_path, name="new.md", fingerprint=_OTHER)
        return metadata

    with (
        patch.object(lookup, "_read_identity", side_effect=insert_after_read),
        patch.object(lookup, "_refresh", wraps=lookup._refresh) as refresh,
    ):
        assert (await lookup.find(_OTHER, _RECORD))[0] == "daily/2026-01-01/new.md"
    assert [call.kwargs["rebuild"] for call in refresh.call_args_list] == [False, True]
    assert set(lookup._snapshot.owners) == {_FP, _OTHER}


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_snapshot", [False, True])
async def test_continuous_directory_changes_stop_after_three_attempts(tmp_path, existing_snapshot):
    """Bounded retries preserve the previous complete snapshot and invalidation."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    if existing_snapshot:
        await lookup.find(_FP, _RECORD)
    previous = lookup._snapshot
    lookup.invalidate_day("2026-01-01")
    dirty = dict(lookup._dirty)
    _note(tmp_path, body="Changed before the retry probe.")
    original_read = lookup._read_identity
    count = 0

    def change_day_after_read(relative):
        nonlocal count
        metadata = original_read(relative)
        assert lookup._snapshot is previous
        if relative.endswith("renamed.md"):
            count += 1
            path = tmp_path / "daily/2026-01-01" / f"unrelated-{count}.txt"
            path.write_text("Concurrent publication", encoding="utf-8")
        return metadata

    with (
        patch.object(lookup, "_read_identity", side_effect=change_day_after_read),
        patch.object(lookup, "_refresh", wraps=lookup._refresh) as refresh,
    ):
        with pytest.raises(_SnapshotChangedError, match="directory changed"):
            await lookup.find(_OTHER, _RECORD)
    assert count == 3
    assert [call.kwargs["rebuild"] for call in refresh.call_args_list] == [False, True, True]
    assert lookup._snapshot is previous
    assert lookup._dirty == dirty


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [PermissionError("unreadable"), ValueError("invalid metadata")])
async def test_source_errors_do_not_trigger_snapshot_retries(tmp_path, error):
    """Retries are reserved for our explicit internal concurrent-change signal."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    with (
        patch.object(lookup, "_read_identity", side_effect=error),
        patch.object(lookup, "_refresh", wraps=lookup._refresh) as refresh,
    ):
        with pytest.raises(type(error), match=str(error)):
            await lookup.find(_FP, _RECORD)
    assert refresh.call_count == 1
    assert lookup._snapshot is None


@pytest.mark.asyncio
async def test_committed_cards_only_read_new_identity_bytes(tmp_path):
    """Real new files do not trigger repeated parsing of stable historical notes."""
    day = tmp_path / "daily/2026-01-01"
    day.mkdir(parents=True)
    for index in range(100):
        (day / f"old-{index}.md").write_text("User note.", encoding="utf-8")
    lookup = _lookup(tmp_path)
    with patch.object(lookup, "_read_identity", wraps=lookup._read_identity) as read:
        for index in range(10):
            fingerprint = f"{index:064x}"
            assert await lookup.find(fingerprint, _RECORD) is None
            async with await lookup.get_catalog_lock():
                assert await lookup.find_locked(fingerprint, _RECORD) is None
                path = _note(tmp_path, name=f"new-{index}.md", fingerprint=fingerprint)
                await lookup.record_committed(path.relative_to(tmp_path).as_posix(), frontmatter.load(path))
        assert read.call_count == 110
    assert len(lookup._snapshot.days["2026-01-01"].notes) == 110


@pytest.mark.asyncio
async def test_prepublication_lookup_detects_in_place_restored_owner(tmp_path):
    """A plain note changed to an owner while the model waits is not a negative."""
    path = _note(tmp_path, fingerprint=_OTHER)
    lookup = _lookup(tmp_path)
    assert await lookup.find(_FP, _RECORD) is None
    parent_signature = lookup._directory_signature("daily/2026-01-01")
    _note(tmp_path, body="Restored by user.")
    assert lookup._directory_signature("daily/2026-01-01") == parent_signature
    with patch.object(lookup, "_read_identity", wraps=lookup._read_identity) as read:
        async with await lookup.get_catalog_lock():
            found = await lookup.find_locked(_FP, _RECORD)
        assert read.call_count == 1
    assert found[0] == path.relative_to(tmp_path).as_posix()
    assert found[1].content == "Restored by user."


@pytest.mark.asyncio
async def test_commit_update_preserves_external_rename_and_new_owner(tmp_path):
    """Publish acknowledgment does not absorb unrelated directory changes."""
    old = _note(tmp_path, name="old.md", fingerprint=_OTHER)
    lookup = _lookup(tmp_path)
    assert await lookup.find(_FP, _RECORD) is None
    async with await lookup.get_catalog_lock():
        assert await lookup.find_locked(_FP, _RECORD) is None
        path = _note(tmp_path, name="own.md")
        old.rename(old.with_name("external-name.md"))
        external_fp = "d" * 64
        _note(tmp_path, name="external-new.md", fingerprint=external_fp)
        await lookup.record_committed(path.relative_to(tmp_path).as_posix(), frontmatter.load(path))
    assert (await lookup.find(_OTHER, _RECORD))[0].endswith("external-name.md")
    assert (await lookup.find(external_fp, _RECORD))[0].endswith("external-new.md")
    assert "daily/2026-01-01/old.md" not in lookup._snapshot.days["2026-01-01"].notes


@pytest.mark.asyncio
async def test_commit_update_rejects_external_duplicate_in_place(tmp_path):
    """A same-path identity edit inside the publication window remains visible."""
    _note(tmp_path, name="ordinary.md", fingerprint=_OTHER)
    lookup = _lookup(tmp_path)
    assert await lookup.find(_FP, _RECORD) is None
    async with await lookup.get_catalog_lock():
        assert await lookup.find_locked(_FP, _RECORD) is None
        path = _note(tmp_path, name="own.md")
        _note(tmp_path, name="ordinary.md")
        with pytest.raises(ValueError, match="Multiple daily notes"):
            await lookup.record_committed(path.relative_to(tmp_path).as_posix(), frontmatter.load(path))
    assert "2026-01-01" in lookup._dirty


@pytest.mark.asyncio
async def test_failed_commit_update_keeps_complete_snapshot_and_dirty_day(tmp_path):
    """A failed differential read cannot bless a partial committed-file index."""
    _note(tmp_path, fingerprint=_OTHER)
    lookup = _lookup(tmp_path)
    assert await lookup.find(_FP, _RECORD) is None
    previous = lookup._snapshot
    async with await lookup.get_catalog_lock():
        path = _note(tmp_path, name="own.md")
        with patch.object(lookup, "_read_identity", side_effect=PermissionError("fixture")):
            with pytest.raises(PermissionError):
                await lookup.record_committed(path.relative_to(tmp_path).as_posix(), frontmatter.load(path))
    assert lookup._snapshot is previous
    assert "2026-01-01" in lookup._dirty
    assert await lookup.find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_catalog_lock_is_shared_and_does_not_create_files(tmp_path):
    """Invocation-local locators synchronize without adding durable lock state."""
    first, second = _lookup(tmp_path), _lookup(tmp_path)
    assert await first.get_catalog_lock() is await second.get_catalog_lock()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_catalog_scan_waits_for_card_publication(tmp_path):
    """An in-process scan never observes a publisher's unfinished metadata."""
    publisher, reader = _lookup(tmp_path), _lookup(tmp_path)
    lock = await publisher.get_catalog_lock()
    arrived = asyncio.Event()
    original_get_lock = reader.get_catalog_lock

    async def announce_lock():
        result = await original_get_lock()
        arrived.set()
        return result

    async with lock:
        path = _note(tmp_path)
        path.write_text("---\nkind: session_image\n", encoding="utf-8")
        with (
            patch.object(reader, "get_catalog_lock", side_effect=announce_lock),
            patch.object(reader, "_read_identity", wraps=reader._read_identity) as read,
        ):
            task = asyncio.create_task(reader.find(_FP, _RECORD))
            await asyncio.wait_for(arrived.wait(), timeout=5)
            assert not task.done()
            assert read.call_count == 0
            _note(tmp_path, body="Completely published caption.")
    assert (await task)[1].content == "Completely published caption."


@pytest.mark.asyncio
async def test_candidate_body_read_does_not_hold_catalog_lock(tmp_path):
    """A slow selected-file read does not block unrelated card publication."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    lock = await lookup.get_catalog_lock()
    original_read = lookup._read_post

    def read_without_catalog(relative, *args):
        assert not lock.locked()
        return original_read(relative, *args)

    with patch.object(lookup, "_read_post", side_effect=read_without_catalog):
        assert await lookup.find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_byte_limit_precedes_note_parse(tmp_path):
    """A bounded header cannot silently truncate identity metadata."""
    _note(tmp_path, body="x" * 1024)
    with pytest.raises(ValueError, match="byte limit"):
        await _lookup(tmp_path, limit=100).find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_unrelated_empty_or_long_notes_do_not_block_bounded_metadata_lookup(tmp_path):
    """Only a selected caption's body is subject to the caption byte limit."""
    _note(tmp_path)
    day = tmp_path / "daily/2026-01-01"
    (day / "draft.md").write_text("", encoding="utf-8")
    (day / "long-ordinary.md").write_text("Ordinary body " + "x" * 4096, encoding="utf-8")
    (day / "long-body.md").write_text("---\nname: ordinary\n---\n" + "x" * 4096, encoding="utf-8")
    (day / "unicode-body.md").write_text("好" * 4096, encoding="utf-8")
    assert await _lookup(tmp_path, limit=1024).find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_empty_reserved_filename_is_an_occupied_target(tmp_path):
    """An empty fixed-name file is never overwritten after a negative lookup."""
    day = tmp_path / "daily/2026-01-01"
    day.mkdir(parents=True)
    (day / f"session-image-{_FP}.md").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        await _lookup(tmp_path).find(_FP, _RECORD)


@pytest.mark.asyncio
async def test_truncated_metadata_does_not_publish_false_negative(tmp_path):
    """An incomplete frontmatter document has an unknown, not absent, owner."""
    day = tmp_path / "daily/2026-01-01"
    day.mkdir(parents=True)
    (day / "unfinished.md").write_text("---\nkind: session_image\n", encoding="utf-8")
    lookup = _lookup(tmp_path)
    with pytest.raises(ValueError, match="closing delimiter"):
        await lookup.find(_FP, _RECORD)
    assert lookup._snapshot is None


@pytest.mark.asyncio
async def test_lookup_never_writes_or_requires_writable_notes(tmp_path):
    """The locator needs read access only and leaves user-owned bytes unchanged."""
    path = _note(tmp_path)
    before = path.read_bytes()
    path.chmod(0o444)
    with (
        patch.object(Path, "write_text", side_effect=AssertionError("lookup is read-only")),
        patch.object(
            Path,
            "write_bytes",
            side_effect=AssertionError("lookup is read-only"),
        ),
    ):
        assert await _lookup(tmp_path).find(_FP, _RECORD)
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_internal_day_symlink_retains_logical_note_path(tmp_path):
    """Authorized internal aliases return the configured logical daily path."""
    private = tmp_path / "owned-day"
    path = _note(tmp_path)
    path.parent.rename(private)
    (tmp_path / "daily/2026-01-01").symlink_to(private, target_is_directory=True)
    relative, _ = await _lookup(tmp_path).find(_FP, _RECORD)
    assert relative == "daily/2026-01-01/renamed.md"


@pytest.mark.asyncio
async def test_external_day_symlink_is_rejected_before_file_reads(tmp_path):
    """An external alias is rejected before any note content is inspected."""
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "daily").mkdir(parents=True)
    (workspace / "daily/2026-01-01").symlink_to(outside, target_is_directory=True)
    lookup = _lookup(workspace)
    with patch.object(lookup, "_read_post", side_effect=AssertionError("must not read outside")):
        with pytest.raises(ValueError, match="Denied"):
            await lookup.find(_FP, _RECORD)
    assert lookup._snapshot is None


@pytest.mark.asyncio
async def test_allowed_path_denial_does_not_become_missing_owner(tmp_path):
    """A denied lookup domain is an explicit failure, never an empty index."""
    _note(tmp_path)
    lookup = _lookup(tmp_path, allowed=["session"])
    with pytest.raises(ValueError, match="Denied"):
        await lookup.find(_FP, _RECORD)
    assert lookup._snapshot is None


@pytest.mark.asyncio
async def test_repeated_lookup_does_not_reenumerate_unchanged_history(tmp_path):
    """Repeated hits and misses inspect directory signatures, not all entries."""
    for day in range(1, 11):
        _note(tmp_path, day=f"2026-01-{day:02}", fingerprint=f"{day:064x}")
    lookup = _lookup(tmp_path)
    original_iterdir = Path.iterdir
    listings = []

    def listing(path):
        listings.append(path)
        return original_iterdir(path)

    with patch.object(Path, "iterdir", listing):
        assert await lookup.find("1".zfill(64), _RECORD)
        assert len(listings) == 11  # Daily root plus each of the ten dates.
        for fingerprint in ("1".zfill(64), "2".zfill(64), _FP, _OTHER):
            await lookup.find(fingerprint, _RECORD)
        assert len(listings) == 11
        _note(tmp_path, name="new.md", fingerprint=_FP)
        assert await lookup.find(_FP, _RECORD)
        assert len(listings) == 12  # Only the changed day is enumerated again.


@pytest.mark.asyncio
async def test_waiting_fingerprint_lock_does_not_trust_stale_negative(tmp_path):
    """A waiting caller discovers another invocation's newly published owner."""
    (tmp_path / "daily").mkdir()
    lookup = _lookup(tmp_path)
    assert await lookup.find(_FP, _RECORD) is None
    lock = await get_path_lock(tmp_path / "caption-fingerprint.lock")
    await lock.acquire()

    async def waiter():
        async with lock:
            return await lookup.find(_FP, _RECORD)

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    _note(tmp_path, day="2026-02-02")  # Another SessionImages instance publishes before releasing its lock.
    lock.release()
    assert (await task)[0] == "daily/2026-02-02/renamed.md"


@pytest.mark.asyncio
async def test_scan_and_caption_reads_run_outside_the_event_loop(tmp_path):
    """Filesystem reads and YAML decoding run in a worker, not the event loop."""
    _note(tmp_path)
    lookup = _lookup(tmp_path)
    original = lookup._read_post

    def check_thread(relative, *args):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return original(relative, *args)

    with patch.object(lookup, "_read_post", side_effect=check_thread):
        assert await lookup.find(_FP, _RECORD)
