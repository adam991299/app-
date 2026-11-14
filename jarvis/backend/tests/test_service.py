from __future__ import annotations

import io
import json
import logging
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jarvis import __version__
from jarvis.service import __main__ as entrypoint
from jarvis.service.app import create_app
from jarvis.service.logging import configure_logging
from jarvis.service.names import ServiceName


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level


@pytest.mark.parametrize("service", list(ServiceName))
def test_every_service_reports_health(service: ServiceName) -> None:
    response = TestClient(create_app(service)).get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == service.value
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert datetime.fromisoformat(body["time"]).utcoffset() is not None


def test_logs_are_json_with_service_name() -> None:
    stream = io.StringIO()
    configure_logging("risk-engine", stream)
    logging.getLogger("x").info("hej %s", "Adam")
    record = json.loads(stream.getvalue())
    assert record["service"] == "risk-engine"
    assert record["level"] == "INFO"
    assert record["message"] == "hej Adam"
    assert "exception" not in record


def test_logged_exceptions_keep_their_traceback() -> None:
    stream = io.StringIO()
    configure_logging("api", stream)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logging.getLogger("x").exception("failed")
    assert "RuntimeError: boom" in json.loads(stream.getvalue())["exception"]


def test_logging_defaults_to_stdout() -> None:
    configure_logging("api")
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout


def test_service_refuses_to_start_with_invalid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("risk:\n  per_trade:\n    max_risk_pct: 99\n", encoding="utf-8")
    monkeypatch.setenv("JARVIS_CONFIG", str(bad))
    started: list[object] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: started.append(a))
    assert entrypoint.main(["--name", "risk-engine"]) == 1
    assert started == []


def test_service_starts_with_valid_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = tmp_path / "good.yaml"
    good.write_text("", encoding="utf-8")
    monkeypatch.setenv("JARVIS_CONFIG", str(good))
    monkeypatch.delenv("JARVIS_CONFIG_OVERRIDE", raising=False)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **k: calls.append({"app": app, **k}))
    assert entrypoint.main(["--name", "api", "--port", "9000"]) == 0
    assert calls[0]["port"] == 9000
    assert calls[0]["log_config"] is None


def test_unknown_service_name_is_rejected() -> None:
    with pytest.raises(SystemExit):
        entrypoint.main(["--name", "not-a-service"])
