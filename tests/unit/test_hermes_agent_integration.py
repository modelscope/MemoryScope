"""Focused tests for the external Hermes memory-provider plugin."""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=protected-access,wrong-import-position,unused-import

from __future__ import annotations

import sys
import types
import importlib
import threading
import time

from dataclasses import dataclass
from pathlib import Path

import pytest

_PLUGIN_PARENT = Path(__file__).resolve().parents[2] / "integrations"
if str(_PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_PARENT))


try:
    import agent.memory_provider  # type: ignore[import-not-found]  # noqa: F401
except ImportError:
    agent_module = types.ModuleType("agent")
    memory_provider_module = types.ModuleType("agent.memory_provider")

    class MemoryProvider:
        """Minimal Hermes contract used when hermes-agent is not installed."""

    @dataclass(frozen=True)
    class RecallStatus:
        provider_label: str
        count: int
        glyph: str = "🧠"

    memory_provider_module.MemoryProvider = MemoryProvider
    memory_provider_module.RecallStatus = RecallStatus
    agent_module.memory_provider = memory_provider_module
    sys.modules["agent"] = agent_module
    sys.modules["agent.memory_provider"] = memory_provider_module

PLUGIN_MODULE = importlib.import_module("hermes_agent")
BACKEND_MODULE = importlib.import_module("hermes_agent.backend")
CONFIG_MODULE = importlib.import_module("hermes_agent.config")
EMBEDDED_MODULE = importlib.import_module("hermes_agent.embedded_backend")
CLIENT_MODULE = importlib.import_module("hermes_agent.client")

ReMeMemoryProvider = PLUGIN_MODULE.ReMeMemoryProvider
ReMeBackendError = BACKEND_MODULE.ReMeBackendError
ReMeConfig = CONFIG_MODULE.ReMeConfig
ReMeConfigError = CONFIG_MODULE.ReMeConfigError
config_path = CONFIG_MODULE.config_path
load_config = CONFIG_MODULE.load_config
parse_config = CONFIG_MODULE.parse_config
save_config = CONFIG_MODULE.save_config
EmbeddedReMeBackend = EMBEDDED_MODULE.EmbeddedReMeBackend
ReMeHttpClient = CLIENT_MODULE.ReMeHttpClient
scoped_session_id = PLUGIN_MODULE._scoped_session_id


def test_config_defaults_to_http(tmp_path):
    config = load_config(tmp_path)

    assert config.mode == "http"
    assert config.endpoint == "http://127.0.0.1:2333"


def test_provider_schema_exposes_mode_specific_and_advanced_fields():
    fields = {field["key"]: field for field in ReMeMemoryProvider().get_config_schema()}

    assert set(fields) == {
        "mode",
        "endpoint",
        "workspace_dir",
        "reme_config",
        "recall_limit",
        "recall_timeout",
        "request_timeout",
        "health_timeout",
        "health_retry_seconds",
        "shutdown_timeout",
    }
    assert fields["endpoint"]["when"] == {"mode": "http"}
    assert fields["workspace_dir"]["when"] == {"mode": "embedded"}


def test_current_config_precedes_legacy(tmp_path):
    (tmp_path / "reme.json").write_text(
        '{"endpoint": "http://legacy:1"}',
        encoding="utf-8",
    )
    current = config_path(tmp_path)
    current.parent.mkdir()
    current.write_text('{"endpoint": "http://current:2"}', encoding="utf-8")

    assert load_config(tmp_path).endpoint == "http://current:2"


def test_embedded_config_normalizes_workspace(tmp_path):
    config = parse_config(
        {"mode": " EMBEDDED ", "workspace_dir": str(tmp_path / "workspace")},
        hermes_home=tmp_path,
    )

    assert config.mode == "embedded"
    assert config.workspace_dir == str((tmp_path / "workspace").absolute())


def test_embedded_config_requires_workspace(tmp_path):
    with pytest.raises(ReMeConfigError, match="workspace_dir"):
        parse_config({"mode": "embedded"}, hermes_home=tmp_path)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_config_rejects_non_finite_timeouts(tmp_path, value):
    with pytest.raises(ReMeConfigError, match="positive number"):
        parse_config({"request_timeout": value}, hermes_home=tmp_path)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://user:secret@127.0.0.1:2333",
        "http://127.0.0.1:2333?token=secret",
        "http://127.0.0.1:2333#fragment",
        "http://127.0.0.1:invalid",
    ],
)
def test_config_and_client_reject_unsafe_endpoint_shapes(tmp_path, endpoint):
    with pytest.raises(ReMeConfigError, match="absolute http"):
        parse_config({"endpoint": endpoint}, hermes_home=tmp_path)
    with pytest.raises(ValueError, match="absolute http"):
        ReMeHttpClient(endpoint, timeout=1)


def test_save_config_uses_dashboard_layout_and_private_permissions(tmp_path):
    saved = save_config({"mode": "http", "recall_limit": 7}, tmp_path)
    path = config_path(tmp_path)

    assert saved.recall_limit == 7
    assert path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600


class _FakeResponse:
    def __init__(self, answer="", metadata=None, success=True):
        self.answer = answer
        self.metadata = metadata or {}
        self.success = success

    def model_dump(self):
        return {
            "answer": self.answer,
            "metadata": self.metadata,
            "success": self.success,
        }


class _FakeApplication:
    instances = []

    def __init__(self, **config):
        self.config = config
        self.started = False
        self.closed = False
        self.calls = []
        self.__class__.instances.append(self)

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True

    async def run_job(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if name == "health_check":
            return _FakeResponse(metadata={"health": {"healthy": True}})
        return _FakeResponse(answer=name, metadata={"counts": {"returned": 1}})


def test_embedded_backend_owns_application_lifecycle(monkeypatch, tmp_path):
    import reme
    import reme.config

    _FakeApplication.instances.clear()
    monkeypatch.setattr(reme, "Application", _FakeApplication)
    monkeypatch.setattr(
        reme.config,
        "resolve_app_config",
        lambda **kwargs: {
            "workspace_dir": kwargs["workspace_dir"],
            "marker": kwargs["config"],
        },
    )
    backend = EmbeddedReMeBackend(str(tmp_path), start_timeout=2)

    backend.start()
    assert backend.health(timeout=2)["success"] is True
    assert backend.search("needle", limit=3, timeout=2)["answer"] == "search"
    backend.auto_memory("session", [{"role": "user", "content": "hello"}], timeout=2)
    backend.close(timeout=2)

    app = _FakeApplication.instances[0]
    assert app.started is True
    assert app.closed is True
    assert app.config == {
        "workspace_dir": str(tmp_path),
        "marker": "default",
    }
    assert [name for name, _ in app.calls] == ["health_check", "search", "auto_memory"]
    assert backend.state == "closed"


class _FakeBackend:
    label = "fake"

    def __init__(self):
        self.writes = []
        self.closed = False

    def start(self):
        return None

    def health(self, *, timeout):
        del timeout
        return {"success": True, "metadata": {"health": {"healthy": True}}}

    def search(self, query, *, limit, timeout):
        del query, limit, timeout
        return {
            "success": True,
            "answer": " remembered ",
            "metadata": {"counts": {"returned": 2}},
        }

    def auto_memory(self, session_id, messages, *, timeout):
        del timeout
        self.writes.append((session_id, messages))
        return {"success": True}

    def close(self, *, timeout):
        del timeout
        self.closed = True


def test_provider_selects_backend_recalls_and_writes(monkeypatch, tmp_path):
    backend = _FakeBackend()
    monkeypatch.setattr(PLUGIN_MODULE, "load_config", lambda home=None: ReMeConfig())
    monkeypatch.setattr(PLUGIN_MODULE, "_backend_for", lambda config: backend)
    provider = ReMeMemoryProvider()
    provider.initialize("session/one", hermes_home=tmp_path, agent_identity="work")

    assert provider.prefetch("project decision") == "remembered"
    assert provider.recall_status().count == 2
    provider.sync_turn("hello", "hi")
    provider.shutdown()

    assert len(backend.writes) == 1
    assert backend.writes[0][0].startswith("hermes-work-session-one-")
    assert backend.closed is True


def test_session_scope_distinguishes_profiles_and_ambiguous_names():
    assert scoped_session_id("profile/a", "session") != scoped_session_id(
        "profile-a",
        "session",
    )
    assert scoped_session_id("profile", "session/a") != scoped_session_id(
        "profile",
        "session-a",
    )


def test_reinitialize_closes_previous_backend(monkeypatch, tmp_path):
    backends = [_FakeBackend(), _FakeBackend()]
    monkeypatch.setattr(PLUGIN_MODULE, "load_config", lambda home=None: ReMeConfig())
    monkeypatch.setattr(PLUGIN_MODULE, "_backend_for", lambda config: backends.pop(0))
    provider = ReMeMemoryProvider()

    provider.initialize("first", hermes_home=tmp_path)
    first = provider._backend
    provider.initialize("second", hermes_home=tmp_path)

    assert first is not None and first.closed is True
    assert provider._backend is not first
    provider.shutdown()


def test_provider_failure_does_not_escape_model_path(monkeypatch, tmp_path):
    backend = _FakeBackend()
    backend.search = lambda *args, **kwargs: (_ for _ in ()).throw(
        ReMeBackendError("offline"),
    )
    monkeypatch.setattr(PLUGIN_MODULE, "load_config", lambda home=None: ReMeConfig())
    monkeypatch.setattr(PLUGIN_MODULE, "_backend_for", lambda config: backend)
    provider = ReMeMemoryProvider()
    provider.initialize("session", hermes_home=tmp_path)

    assert provider.prefetch("query") == ""
    assert provider.recall_status() is None
    provider.shutdown()


def test_provider_reports_embedded_workspace_for_hermes_backup(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(
        PLUGIN_MODULE,
        "load_config",
        lambda home=None: ReMeConfig(mode="embedded", workspace_dir=str(workspace)),
    )

    assert ReMeMemoryProvider().backup_paths() == [str(workspace)]


def test_backend_creation_is_serialized(monkeypatch):
    provider = ReMeMemoryProvider()
    provider._config = ReMeConfig()
    created = []

    def factory(config):
        del config
        time.sleep(0.05)
        backend = _FakeBackend()
        created.append(backend)
        return backend

    monkeypatch.setattr(PLUGIN_MODULE, "_backend_for", factory)
    gate = threading.Barrier(3)
    results = []

    def ensure():
        gate.wait()
        results.append(provider._ensure_backend())

    threads = [threading.Thread(target=ensure) for _ in range(2)]
    for thread in threads:
        thread.start()
    gate.wait()
    for thread in threads:
        thread.join(timeout=2)

    assert results == [True, True]
    assert len(created) == 1
    provider.shutdown()


def test_shutdown_defers_close_until_inflight_recall_finishes():
    entered = threading.Event()
    release = threading.Event()

    class BlockingBackend(_FakeBackend):
        def search(self, query, *, limit, timeout):
            del query, limit, timeout
            entered.set()
            release.wait(timeout=2)
            return {"success": True, "answer": "remembered", "metadata": {}}

    backend = BlockingBackend()
    provider = ReMeMemoryProvider()
    provider._config = ReMeConfig()
    provider._backend = backend
    provider._backend_available = True
    provider._shutdown_timeout = 0.05
    recall = threading.Thread(target=provider.prefetch, args=("query",))
    recall.start()
    assert entered.wait(timeout=1)

    provider.shutdown()
    assert backend.closed is False
    release.set()
    recall.join(timeout=2)

    assert recall.is_alive() is False
    assert backend.closed is True


def test_shutdown_discard_keeps_sentinel_for_inflight_writer():
    provider = ReMeMemoryProvider()
    provider._write_queue.put({"session_id": "queued"})
    provider._write_queue.put(None)

    assert provider._discard_queued_writes() == 1
    assert provider._write_queue.get_nowait() is None
