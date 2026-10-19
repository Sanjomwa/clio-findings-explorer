#!/usr/bin/env python3
"""On-call webhook receiver (product spec 7.4, docs/on-call.md). Standard library only.

    POST /alert    Grafana's webhook JSON. Each accepted alert is written, as received, to the inbox.
    GET  /health   200 {"status": "ok"}

The receiver only receives. The actor that reads the inbox runs on the host (issue #7, Part B).
Bodies are untrusted data: size-capped, shape-checked, and never executed or interpolated.
Log lines are JSON in the backend's shape (backend/app/telemetry.py) and carry no client address.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_BODY_BYTES = 256 * 1024
SOCKET_TIMEOUT = 10  # seconds; a stalled sender must not hold a thread forever
STATUSES = ("firing", "resolved")
UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

LOG = logging.getLogger("oncall.receiver")


class JsonFormatter(logging.Formatter):
    """One JSON object per record, the same fields as the backend's formatter."""

    ACCESS_FIELDS = ("method", "route", "status", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "trace_id": None,
            "span_id": None,
        }
        for field in self.ACCESS_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(stream: Any = None) -> None:
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    LOG.handlers[:] = [handler]
    LOG.setLevel(logging.INFO)
    LOG.propagate = False


class PayloadError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate(body: bytes) -> list[dict[str, Any]]:
    """Return the alerts in a Grafana webhook body, or raise PayloadError."""
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError):
        raise PayloadError(400, "body is not valid JSON") from None
    if not isinstance(payload, dict):
        raise PayloadError(400, "body must be a JSON object")
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise PayloadError(400, "alerts must be a list")
    for index, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            raise PayloadError(400, f"alerts[{index}] must be an object")
        for key in ("status", "labels", "startsAt"):
            if key not in alert:
                raise PayloadError(400, f"alerts[{index}] is missing {key}")
        if alert["status"] not in STATUSES:
            raise PayloadError(400, f'alerts[{index}].status must be "firing" or "resolved"')
        if not isinstance(alert["labels"], dict):
            raise PayloadError(400, f"alerts[{index}].labels must be an object")
        if not isinstance(alert["startsAt"], str):
            raise PayloadError(400, f"alerts[{index}].startsAt must be a string")
    return alerts


def fingerprint_of(alert: dict[str, Any]) -> str:
    """The alert's fingerprint made safe for a file name; never a path."""
    value = UNSAFE.sub("", str(alert.get("fingerprint") or ""))[:64]
    return value or "nofingerprint"


def write_alert(inbox: Path, alert: dict[str, Any]) -> str:
    """Write one alert atomically: temp file in the inbox, then a link to its final name."""
    fingerprint = fingerprint_of(alert)
    while True:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        name = f"{stamp}-{fingerprint}-{alert['status']}.json"
        tmp = inbox / f".{name}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(alert, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, inbox / name)  # fails rather than overwrite an existing file
        except FileExistsError:
            continue
        finally:
            tmp.unlink(missing_ok=True)
        return name


class Handler(BaseHTTPRequestHandler):
    inbox: Path = Path("/inbox")
    timeout = SOCKET_TIMEOUT
    server_version = "oncall"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (base class signature)
        pass  # the default writes the client address; access lines are logged by _finish

    def _reply(self, code: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _finish(self, route: str, code: int, started: float, body: dict[str, Any], note: str = "") -> None:
        LOG.info(
            note or f"{self.command} {route} {code}",
            extra={"method": self.command, "route": route, "status": code,
                   "duration_ms": round((time.monotonic() - started) * 1000, 1)},
        )
        self._reply(code, body)

    def _route(self) -> str:
        path = self.path.split("?", 1)[0]
        return path if path in ("/alert", "/health") else "unmatched"

    def do_GET(self) -> None:
        self._handle()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = do_GET

    def _handle(self) -> None:
        started = time.monotonic()
        route = self._route()
        if route == "unmatched":
            return self._finish(route, 404, started, {"error": "not found"})
        allowed = "GET" if route == "/health" else "POST"
        if self.command != allowed:
            return self._finish(route, 405, started, {"error": "method not allowed"})
        if route == "/health":
            return self._finish(route, 200, started, {"status": "ok"})
        try:
            alerts = validate(self._read_body())
            names = [write_alert(self.inbox, alert) for alert in alerts]
        except PayloadError as error:
            return self._finish(route, error.code, started, {"error": str(error)},
                                note=f"rejected: {error}")
        except OSError as error:
            return self._finish(route, 500, started, {"error": "could not write the inbox"},
                                note=f"inbox write failed: {type(error).__name__}")
        self._finish(route, 200, started, {"accepted": names},
                     note=f"accepted {len(names)} alert(s): {', '.join(names)}")

    def _read_body(self) -> bytes:
        if "Transfer-Encoding" in self.headers:
            raise PayloadError(411, "Content-Length is required")
        raw = self.headers.get("Content-Length")
        if raw is None or not raw.isdigit():
            raise PayloadError(411, "Content-Length is required")
        length = int(raw)
        if length > MAX_BODY_BYTES:
            raise PayloadError(413, f"body is over {MAX_BODY_BYTES} bytes")
        body = self.rfile.read(length)
        if len(body) != length:
            raise PayloadError(400, "body is shorter than Content-Length")
        return body


def make_server(inbox: Path, host: str = "0.0.0.0", port: int = 8090) -> ThreadingHTTPServer:  # noqa: S104
    handler = type("InboxHandler", (Handler,), {"inbox": inbox})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    configure_logging()
    inbox = Path(os.environ.get("ONCALL_INBOX", "/inbox"))
    port = int(os.environ.get("ONCALL_PORT", "8090"))
    server = make_server(inbox, port=port)
    LOG.info(f"listening on port {port}, inbox {inbox}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
