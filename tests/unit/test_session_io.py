"""Fault injection at the atomic session evidence publication boundary."""

# pylint: disable=protected-access

import asyncio
import os
import threading
from unittest.mock import Mock

import pytest

from reme.steps.evolve import _session_io
from reme.steps.evolve._session_io import atomic_write


@pytest.mark.asyncio
async def test_new_and_replaced_files_are_complete_and_keep_mode(tmp_path):
    """Replacement changes content without broadening original file permissions."""
    path = tmp_path / "nested" / "source.jsonl"
    await atomic_write(path, "original\n")
    path.chmod(0o640)
    await atomic_write(path, "updated\n", overwrite=True, expected=b"original\n")
    assert path.read_bytes() == b"updated\n"
    assert path.stat().st_mode & 0o777 == 0o640
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite,expected", [(False, None), (True, None), (True, b"stale")])
async def test_existing_user_file_is_not_clobbered(tmp_path, overwrite, expected):
    """Creating over an occupant or replacing a stale snapshot fails closed."""
    path = tmp_path / "source"
    path.write_bytes(b"user content")
    with pytest.raises((FileExistsError, RuntimeError)):
        await atomic_write(path, b"new content", overwrite=overwrite, expected=expected)
    assert path.read_bytes() == b"user content"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["fsync", "replace", "link"])
async def test_publication_failure_keeps_original_and_allows_retry(tmp_path, monkeypatch, operation):
    """All publication seams leave either an absent destination or the old bytes."""
    path = tmp_path / "source"
    previous = None if operation == "link" else b"original"
    if previous is not None:
        path.write_bytes(previous)
    with monkeypatch.context() as patch:
        patch.setattr(_session_io.os, operation, Mock(side_effect=OSError("disk failure")))
        with pytest.raises(OSError):
            await atomic_write(path, b"replacement", overwrite=True, expected=previous)
    assert path.read_bytes() == previous if previous is not None else not path.exists()
    assert not list(tmp_path.glob(".reme-session-*"))
    await atomic_write(path, b"replacement", overwrite=True, expected=previous)
    assert path.read_bytes() == b"replacement"


@pytest.mark.asyncio
async def test_short_write_never_publishes(tmp_path, monkeypatch):
    """A short successful write is still incomplete evidence."""
    real_open = os.fdopen

    class ShortWriter:
        """A disk stream that writes only a prefix without raising."""

        def __init__(self, descriptor, mode):
            self.stream = real_open(descriptor, mode)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            """Return a successful-looking but incomplete byte count."""
            return self.stream.write(data[:2])

    monkeypatch.setattr(_session_io.os, "fdopen", ShortWriter)
    with pytest.raises(OSError, match="Incomplete"):
        await atomic_write(tmp_path / "source", b"complete source")
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_replacement_rejects_symlink_even_when_bytes_match(tmp_path):
    """The writer itself does not follow a swapped final symlink on replacement."""
    target = tmp_path / "user"
    target.write_bytes(b"old")
    link = tmp_path / "source"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        await atomic_write(link, b"new", overwrite=True, expected=b"old")
    assert link.is_symlink() and target.read_bytes() == b"old"
    assert not list(tmp_path.glob(".reme-session-*"))


@pytest.mark.asyncio
async def test_cancellation_waits_for_worker_and_cleans_staging(tmp_path, monkeypatch):
    """Repeated cancellation cannot release a caller's lock before worker exit."""
    entered, release = threading.Event(), threading.Event()
    real_sync = os.fsync

    def paused_sync(descriptor):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("test did not release writer")
        real_sync(descriptor)

    monkeypatch.setattr(_session_io.os, "fsync", paused_sync)
    path = tmp_path / "source"
    task = asyncio.create_task(atomic_write(path, b"evidence"))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "The destination lock must not be released while its worker is running"
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not list(tmp_path.iterdir())
    await atomic_write(path, b"retry")
    assert path.read_bytes() == b"retry"
