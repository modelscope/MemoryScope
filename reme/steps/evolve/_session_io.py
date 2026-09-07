"""Atomic publication of session evidence; callers own the destination lock."""

import asyncio
import os
from pathlib import Path
import stat
import tempfile
import threading


def _publish(path: Path, data: bytes, overwrite: bool, expected: bytes | None, cancelled: threading.Event) -> None:
    """Stage all bytes beside the destination before publishing a complete file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".reme-session-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(data) != len(data):
                raise OSError("Incomplete session evidence write")
            stream.flush()
            os.fsync(stream.fileno())
        if cancelled.is_set():
            return
        if overwrite and expected is not None:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Session destination must be a regular file")
            with path.open("rb") as current:
                if current.read(len(expected) + 1) != expected:
                    raise RuntimeError("Session changed while preparing an update")
            os.chmod(temporary, stat.S_IMODE(info.st_mode))
            if not cancelled.is_set():
                os.replace(temporary, path)
        elif not cancelled.is_set():
            # A hard link publishes without clobbering an existing user file.
            # Both paths are on the same filesystem; unlinking the staging
            # name below leaves the complete destination intact.
            os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


async def atomic_write(
    path: Path,
    content: str | bytes,
    *,
    overwrite: bool = False,
    expected: bytes | None = None,
) -> None:
    """Publish complete content, checking the previous snapshot before replacement.

    ``overwrite=True`` requires the exact previous bytes, or ``None`` for an
    absent destination. This catches intervening edits but is not a filesystem
    compare-and-swap against external writers. Cancellation waits for the worker
    to finish before releasing the caller's lock. A publication racing with
    cancellation can have completed; callers can inspect the durable file.
    """
    data = content.encode("utf-8") if isinstance(content, str) else content
    cancelled = threading.Event()
    worker = asyncio.create_task(asyncio.to_thread(_publish, path, data, overwrite, expected, cancelled))
    try:
        await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:  # pylint: disable=broad-except
                break
        if not worker.cancelled():
            worker.exception()
        raise
