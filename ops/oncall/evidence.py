"""Evidence for one incident: fixed queries, redaction and truncation (docs/on-call.md).

Standard library only. Every query below is a constant template. The only values taken from the
alert are its start time (parsed, never interpolated as text) and nothing else: no label, annotation
or URL from the payload becomes part of a query. Read-only HTTP GETs to Grafana's datasource proxy
and one `docker compose ps`.

Everything written is redacted first (database URLs, passwords, key-like values, IP addresses,
home paths) and capped in size, with a note where text was cut.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REDACTED = "[REDACTED]"
IP_PLACEHOLDER = "[ip]"

URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*(?:\+[a-z0-9]+)?://)[^\s/@:]+:[^\s/@]+@")
KEY_VALUE = re.compile(
    r"""(?ix)
    (\b[\w.\-]*(?:password|passwd|secret|token|api[_-]?key|private[_-]?key)[\w.\-]*["']?\s*[:=]\s*["']?)
    (?!\[REDACTED\])([^\s"',}&]+)
    """
)
BEARER = re.compile(r"[Bb]earer\s+[A-Za-z0-9_.~+/=\-]{16,}")
API_KEY = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
HOME_PATH = re.compile(r"/home/[^/\s\"']+")

# What a journey request is: the route matcher of the alert rule (docs/alerting.md).
JOURNEY_ROUTE_REGEX = "/api/findings.*"
LOKI_ERRORS = '{service_name="cfe-backend"} | detected_level=~"error|warn|warning|critical|fatal"'
LOKI_JOURNEY = '{service_name="cfe-backend"} |= "/api/findings"'
TEMPO_JOURNEY = (
    '{ resource.service.name = "cfe-backend" && kind = server && span.http.route =~ "'
    + JOURNEY_ROUTE_REGEX
    + '" } | select(span.http.response.status_code)'
)
LOG_FIELDS = ("detected_level", "route", "status", "method", "duration_ms", "trace_id",
              "code_function_name", "exception_type", "exception_message")
COMPOSE_FIELDS = ("Service", "State", "Health", "ExitCode")


def redact(text: str, secrets: tuple[str, ...] = (), repo: str = "") -> str:
    """Remove credentials, IP addresses and home paths from text."""
    text = URL_CREDENTIALS.sub(lambda m: f"{m.group(1)}{REDACTED}@", text)
    text = KEY_VALUE.sub(lambda m: m.group(1) + REDACTED, text)
    text = BEARER.sub(f"Bearer {REDACTED}", text)
    text = API_KEY.sub(REDACTED, text)
    for secret in secrets:
        if len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    if repo:
        text = text.replace(repo, ".")
    text = HOME_PATH.sub("~", text)
    return IPV4.sub(IP_PLACEHOLDER, text)


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Cut text to at most `limit` bytes of UTF-8, with a note that says how much was dropped."""
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text, False
    kept = data[:limit].decode("utf-8", errors="ignore")
    return f"{kept}\n[truncated: {len(data) - len(kept.encode('utf-8'))} bytes omitted]\n", True


def parse_time(value: object, default: datetime) -> datetime:
    """Parse Grafana's RFC 3339 time (up to nanoseconds); on anything else return `default`."""
    if not isinstance(value, str):
        return default
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})", value)
    if not match:
        return default
    fraction = (match.group(2) or "")[:7]
    zone = "+00:00" if match.group(3) == "Z" else match.group(3)
    try:
        return datetime.fromisoformat(f"{match.group(1)}{fraction}{zone}").astimezone(UTC)
    except ValueError:
        return default


Fetch = Callable[[str], tuple[int, bytes]]


def compact_logs(body: bytes, limit: int) -> dict[str, Any]:
    """Loki query_range -> a short list of {time, message, selected labels}, newest last."""
    try:
        streams = json.loads(body)["data"]["result"]
    except (ValueError, KeyError, TypeError):
        return {"error": "unreadable response", "lines": []}
    lines: list[dict[str, Any]] = []
    for stream in streams:
        labels = stream.get("stream", {})
        for stamp, message in stream.get("values", []):
            entry = {"time": datetime.fromtimestamp(int(stamp) / 1e9, UTC).isoformat(timespec="seconds"),
                     "message": str(message)[:500]}
            entry.update({k: labels[k] for k in LOG_FIELDS if k in labels})
            lines.append(entry)
    lines.sort(key=lambda e: e["time"])
    return {"count": len(lines), "lines": lines[-limit:]}


def compact_traces(body: bytes) -> dict[str, Any]:
    """Tempo search -> counts of journey server spans per status code, plus a few trace IDs."""
    try:
        traces = json.loads(body)["traces"]
    except (ValueError, KeyError, TypeError):
        return {"error": "unreadable response", "status_codes": {}}
    counts: dict[str, int] = {}
    failing: list[dict[str, Any]] = []
    for trace in traces:
        for span_set in trace.get("spanSets") or [trace.get("spanSet") or {}]:
            for span in span_set.get("spans", []):
                code = "unknown"
                for attribute in span.get("attributes", []):
                    if str(attribute.get("key", "")).endswith("http.response.status_code"):
                        value = attribute.get("value", {})
                        code = str(value.get("intValue", value.get("stringValue", "unknown")))
                counts[code] = counts.get(code, 0) + 1
                if code.startswith("5") and len(failing) < 10:
                    failing.append({"trace_id": trace.get("traceID"), "status": code,
                                    "duration_ms": round(int(span.get("durationNanos", 0)) / 1e6, 1)})
    return {"traces_searched": len(traces), "status_codes": counts, "failing_examples": failing}


def compact_compose(raw: str) -> list[dict[str, Any]]:
    """`docker compose ps --format json` (one object per line, or one array) -> service states only."""
    raw = raw.strip()
    if not raw:
        return []
    try:
        rows = json.loads(raw)
        rows = rows if isinstance(rows, list) else [rows]
    except ValueError:
        rows = []
        for line in raw.splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return [{k: row.get(k) for k in COMPOSE_FIELDS} for row in rows if isinstance(row, dict)]


class Packet:
    """The evidence folder: redacted, size-capped files plus a manifest of what each one is."""

    def __init__(self, folder: Path, total_limit: int, file_limit: int,
                 secrets: tuple[str, ...] = (), repo: str = "") -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.remaining = total_limit
        self.file_limit = file_limit
        self.secrets = secrets
        self.repo = repo
        self.manifest: list[dict[str, Any]] = []

    def write(self, name: str, content: Any, source: str) -> None:
        text = content if isinstance(content, str) else json.dumps(content, indent=1, ensure_ascii=False)
        text = redact(text, self.secrets, self.repo)
        limit = max(0, min(self.file_limit, self.remaining))
        text, cut = truncate(text, limit)
        data = text.encode("utf-8")
        self.remaining -= len(data)
        (self.folder / name).write_bytes(data)
        self.manifest.append({"file": name, "source": source, "bytes": len(data), "truncated": cut,
                              "sha256": hashlib.sha256(data).hexdigest()})

    def finish(self) -> None:
        (self.folder / "manifest.json").write_text(
            json.dumps({"files": self.manifest, "redacted": True}, indent=1) + "\n", encoding="utf-8")


def collect(packet: Packet, alert: dict[str, Any], *, grafana: str, backend: str, site: str,
            fetch: Fetch, compose_ps: Callable[[], str], lookback_min: int, log_limit: int,
            replay: Callable[[], dict[str, Any]], now: datetime | None = None) -> None:
    """Write the fixed evidence set. Nothing here changes any state."""
    now = now or datetime.now(UTC)
    start = parse_time(alert.get("startsAt"), now) - timedelta(minutes=lookback_min)
    if start > now:
        start = now - timedelta(minutes=lookback_min)

    packet.write("alert.json", {k: alert.get(k) for k in ("status", "labels", "annotations", "startsAt", "values")},
                 "the alert as received (selected fields)")
    packet.write("compose-ps.json", compact_compose(compose_ps()),
                 "docker compose ps -a (Service, State, Health, ExitCode)")
    status, body = fetch(f"{backend}/api/health")
    packet.write("backend-health.json", {"http_status": status, "body": body.decode("utf-8", "replace")[:300]},
                 "GET backend /api/health")
    packet.write("journey-replay.json", replay(), "one GET of /api/findings through the frontend")

    window = {"start": f"{int(start.timestamp())}000000000", "end": f"{int(time.time())}000000000"}
    loki = f"{grafana}/api/datasources/proxy/uid/loki/loki/api/v1/query_range"
    for name, query in (("logs-errors.json", LOKI_ERRORS), ("logs-journey.json", LOKI_JOURNEY)):
        url = loki + "?" + _query({"query": query, "limit": str(log_limit), **window, "direction": "backward"})
        code, data = fetch(url)
        packet.write(name, compact_logs(data, log_limit) if code == 200 else {"error": f"HTTP {code}", "lines": []},
                     f"Loki query_range {query} (limit {log_limit}, from alert start minus {lookback_min} min to now)")

    tempo = f"{grafana}/api/datasources/proxy/uid/tempo/api/search"
    url = tempo + "?" + _query({"q": TEMPO_JOURNEY, "limit": "100", "start": str(int(start.timestamp())),
                                "end": str(int(time.time()))})
    code, data = fetch(url)
    packet.write("traces-journey.json", compact_traces(data) if code == 200 else {"error": f"HTTP {code}"},
                 f"Tempo search {TEMPO_JOURNEY} (limit 100)")
    packet.finish()


def _query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode
    return urlencode(params)
