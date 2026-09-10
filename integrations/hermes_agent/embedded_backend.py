"""In-process ReMe backend with one dedicated asyncio loop thread."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time

from enum import Enum
from typing import Any, Coroutine

from .backend import ReMeBackendError, require_healthy


class _State(Enum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class EmbeddedReMeBackend:
    """Own a ReMe Application and all of its async resources on one event loop."""

    def __init__(
        self,
        workspace_dir: str,
        *,
        reme_config: str = "default",
        start_timeout: float = 600.0,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.reme_config = reme_config
        self.start_timeout = start_timeout
        self.label = f"embedded:{workspace_dir}"
        self._state = _State.NEW
        self._state_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._loop_ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._app: Any = None
        self._failure: BaseException | None = None

    @property
    def state(self) -> str:
        """Expose lifecycle state for diagnostics and focused tests."""
        with self._state_lock:
            return self._state.value

    def start(self) -> None:
        """Start the loop thread and construct the Application on that loop."""
        with self._state_lock:
            if self._state is _State.RUNNING:
                return
            if self._state is not _State.NEW:
                detail = f": {self._failure}" if self._failure else ""
                raise ReMeBackendError(
                    f"Embedded ReMe cannot start from state {self._state.value}{detail}",
                )
            self._state = _State.STARTING
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="reme-embedded-loop",
            )
            self._thread.start()

        if not self._loop_ready.wait(timeout=self.start_timeout):
            self._fail(
                TimeoutError("Timed out while starting the embedded ReMe event loop"),
            )
            self.close(timeout=self.start_timeout)
            raise ReMeBackendError(
                "Timed out while starting the embedded ReMe event loop",
            )

        try:
            self._submit(
                self._start_application(),
                timeout=self.start_timeout,
                allow_starting=True,
            )
        except ReMeBackendError as exc:
            self._fail(exc)
            self.close(timeout=self.start_timeout)
            raise
        with self._state_lock:
            self._state = _State.RUNNING

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._state_lock:
            self._loop = loop
            should_run = self._state in {_State.STARTING, _State.RUNNING}
        self._loop_ready.set()
        try:
            if should_run:
                loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True),
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def _start_application(self) -> None:
        try:
            from reme import Application
            from reme.config import resolve_app_config
        except ImportError as exc:
            raise ReMeBackendError(
                'Embedded ReMe mode requires the SDK. Install it with: pip install "reme-ai[core]"',
            ) from exc

        app_config = resolve_app_config(
            config=self.reme_config,
            log_config=False,
            workspace_dir=self.workspace_dir,
            enable_logo=False,
            log_to_console=False,
            log_to_file=False,
        )
        app = Application(**app_config)
        self._app = app
        try:
            await app.start()
        except BaseException:
            await app.close()
            self._app = None
            raise

    def _fail(self, error: BaseException) -> None:
        with self._state_lock:
            self._failure = self._failure or error
            if self._state not in {_State.CLOSING, _State.CLOSED}:
                self._state = _State.FAILED

    def _submit(
        self,
        coroutine: Coroutine[Any, Any, Any],
        *,
        timeout: float,
        allow_starting: bool = False,
    ) -> Any:
        with self._state_lock:
            allowed = {_State.RUNNING}
            if allow_starting:
                allowed.add(_State.STARTING)
            if (
                self._state not in allowed
                or self._loop is None
                or not self._loop.is_running()
            ):
                coroutine.close()
                raise ReMeBackendError(
                    f"Embedded ReMe is not running (state: {self._state.value})",
                )
            loop = self._loop
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise ReMeBackendError(
                f"Embedded ReMe operation timed out after {timeout:.1f}s",
            ) from exc
        except ReMeBackendError:
            raise
        except BaseException as exc:
            raise ReMeBackendError(str(exc) or type(exc).__name__) from exc

    @staticmethod
    def _response_dict(response: Any) -> dict[str, Any]:
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        elif isinstance(response, dict):
            result = dict(response)
        else:
            raise ReMeBackendError("ReMe returned an unsupported response object")
        if result.get("success") is not True:
            raise ReMeBackendError(
                str(result.get("answer") or "ReMe action did not report success"),
            )
        return result

    async def _run_job(self, name: str, **kwargs: Any) -> dict[str, Any]:
        if self._app is None:
            raise ReMeBackendError("Embedded ReMe Application is unavailable")
        response = await self._app.run_job(name, **kwargs)
        return self._response_dict(response)

    def health(self, *, timeout: float) -> dict[str, Any]:
        """Run ReMe's health-check job on the owned loop."""
        with self._operation_lock:
            return require_healthy(
                self._submit(self._run_job("health_check"), timeout=timeout),
            )

    def search(self, query: str, *, limit: int, timeout: float) -> dict[str, Any]:
        """Run ReMe's search job on the owned loop."""
        with self._operation_lock:
            return self._submit(
                self._run_job("search", query=query, limit=limit),
                timeout=timeout,
            )

    def auto_memory(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        """Run ReMe's automatic-memory job on the owned loop."""
        with self._operation_lock:
            return self._submit(
                self._run_job("auto_memory", session_id=session_id, messages=messages),
                timeout=timeout,
            )

    def close(self, *, timeout: float) -> None:
        """Close the Application, stop its loop, and join its thread."""
        deadline = time.monotonic() + max(0.1, timeout)
        # A context manager cannot express the bounded wait required by shutdown.
        acquired = self._operation_lock.acquire(  # pylint: disable=consider-using-with
            timeout=max(0.1, deadline - time.monotonic()),
        )
        if not acquired:
            raise ReMeBackendError(
                "Timed out waiting for an embedded ReMe operation to finish"
            )
        try:
            self._close_locked(deadline)
        finally:
            self._operation_lock.release()

    def _close_locked(self, deadline: float) -> None:
        """Close while holding the operation lock so jobs cannot overlap shutdown."""
        close_error: BaseException | None = None
        with self._state_lock:
            if self._state is _State.CLOSED:
                return
            if self._state is _State.NEW:
                self._state = _State.CLOSED
                return
            self._state = _State.CLOSING
            loop = self._loop
            thread = self._thread

        if loop is not None and loop.is_running() and self._app is not None:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                future = asyncio.run_coroutine_threadsafe(self._app.close(), loop)
                future.result(timeout=remaining)
            except concurrent.futures.TimeoutError:
                future.cancel()
                close_error = TimeoutError(
                    "Timed out while closing the embedded ReMe Application"
                )
            except BaseException as exc:
                close_error = exc
            finally:
                self._app = None
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

        with self._state_lock:
            self._state = (
                _State.CLOSED
                if thread is None or not thread.is_alive()
                else _State.FAILED
            )
            if self._state is _State.FAILED and self._failure is None:
                self._failure = TimeoutError(
                    "Timed out while stopping the embedded ReMe event loop",
                )
            failure = self._failure if self._state is _State.FAILED else close_error
        if failure is not None:
            raise ReMeBackendError(str(failure)) from failure
