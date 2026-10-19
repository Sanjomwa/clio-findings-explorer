"""Tests for ops/oncall/receiver.py. No Docker: the receiver runs on a loopback port in a thread.

The fixture is the real Grafana payload shown in docs/alerting.md, read from that file.

Run from the repository root:
    python3 -m unittest discover -s ops/tests -v
"""

import http.client
import io
import json
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "oncall"))

import receiver  # noqa: E402


def real_payload() -> dict:
    text = (REPO / "docs" / "alerting.md").read_text(encoding="utf-8")
    block = re.search(r"## What the on-call agent receives.*?```json\n(.*?)\n```", text, re.S)
    assert block, "the example payload is missing from docs/alerting.md"
    return json.loads(block.group(1))


PAYLOAD = real_payload()
FILE_NAME = re.compile(r"^\d{8}T\d{6}\.\d{6}Z-1ee17afeb9fa5762-firing\.json$")


class ReceiverCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inbox = Path(self.tmp.name)
        self.log = io.StringIO()
        receiver.configure_logging(self.log)
        self.server = receiver.make_server(self.inbox, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def post(self, body: bytes, path: str = "/alert"):
        return self.request("POST", path, body, {"Content-Type": "application/json"})

    def files(self) -> list[str]:
        return sorted(p.name for p in self.inbox.iterdir())


class AcceptedPayload(ReceiverCase):
    def test_valid_payload_is_written_once_with_the_right_name(self) -> None:
        status, body = self.post(json.dumps(PAYLOAD).encode())
        self.assertEqual(status, 200)
        files = self.files()
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], FILE_NAME)
        self.assertEqual(json.loads(body), {"accepted": files})

    def test_the_alert_is_stored_as_received(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        stored = json.loads((self.inbox / self.files()[0]).read_text(encoding="utf-8"))
        self.assertEqual(stored, PAYLOAD["alerts"][0])

    def test_no_temp_file_is_left_behind(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        self.assertFalse([n for n in self.files() if n.endswith(".tmp") or n.startswith(".")])

    def test_resolved_status_is_in_the_name(self) -> None:
        resolved = json.loads(json.dumps(PAYLOAD))
        resolved["alerts"][0]["status"] = "resolved"
        self.post(json.dumps(resolved).encode())
        self.assertTrue(self.files()[0].endswith("-1ee17afeb9fa5762-resolved.json"))

    def test_two_alerts_make_two_files(self) -> None:
        two = json.loads(json.dumps(PAYLOAD))
        other = json.loads(json.dumps(two["alerts"][0]))
        other["fingerprint"] = "aaaa"
        two["alerts"].append(other)
        self.post(json.dumps(two).encode())
        self.assertEqual(len(self.files()), 2)

    def test_the_same_alert_twice_is_two_files_never_an_overwrite(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        self.post(json.dumps(PAYLOAD).encode())
        self.assertEqual(len(self.files()), 2)

    def test_a_hostile_fingerprint_cannot_leave_the_inbox(self) -> None:
        hostile = json.loads(json.dumps(PAYLOAD))
        hostile["alerts"][0]["fingerprint"] = "../../etc/passwd"
        self.post(json.dumps(hostile).encode())
        files = self.files()
        self.assertEqual(len(files), 1)
        self.assertNotIn("/", files[0])
        self.assertIn("etcpasswd", files[0])

    def test_an_empty_alert_list_is_accepted_and_writes_nothing(self) -> None:
        status, _ = self.post(b'{"alerts": []}')
        self.assertEqual(status, 200)
        self.assertEqual(self.files(), [])


class RejectedRequests(ReceiverCase):
    def assertRejected(self, status: tuple[int, ...] | int, got: int) -> None:
        self.assertIn(got, (status,) if isinstance(status, int) else status)
        self.assertEqual(self.files(), [], "nothing may be written for a rejected request")

    def test_invalid_json(self) -> None:
        self.assertRejected(400, self.post(b"{not json")[0])

    def test_body_that_is_not_an_object(self) -> None:
        self.assertRejected(400, self.post(b"[1, 2]")[0])

    def test_missing_alerts(self) -> None:
        self.assertRejected(400, self.post(json.dumps({"status": "firing"}).encode())[0])

    def test_alerts_not_a_list(self) -> None:
        self.assertRejected(400, self.post(b'{"alerts": {"status": "firing"}}')[0])

    def test_alert_missing_a_required_field(self) -> None:
        for key in ("status", "labels", "startsAt"):
            broken = json.loads(json.dumps(PAYLOAD))
            del broken["alerts"][0][key]
            self.assertRejected(400, self.post(json.dumps(broken).encode())[0])

    def test_unknown_status(self) -> None:
        broken = json.loads(json.dumps(PAYLOAD))
        broken["alerts"][0]["status"] = "pending"
        self.assertRejected(400, self.post(json.dumps(broken).encode())[0])

    def test_one_bad_alert_rejects_the_whole_request(self) -> None:
        mixed = json.loads(json.dumps(PAYLOAD))
        mixed["alerts"].append({"status": "firing"})
        self.assertRejected(400, self.post(json.dumps(mixed).encode())[0])

    def test_oversized_body(self) -> None:
        big = json.loads(json.dumps(PAYLOAD))
        big["alerts"][0]["annotations"]["pad"] = "x" * receiver.MAX_BODY_BYTES
        body = json.dumps(big).encode()
        self.assertGreater(len(body), receiver.MAX_BODY_BYTES)
        self.assertRejected(413, self.post(body)[0])

    def test_body_just_under_the_limit_is_accepted(self) -> None:
        ok = json.loads(json.dumps(PAYLOAD))
        pad = receiver.MAX_BODY_BYTES - len(json.dumps(ok).encode()) - 200
        ok["alerts"][0]["annotations"]["pad"] = "x" * pad
        self.assertLess(len(json.dumps(ok).encode()), receiver.MAX_BODY_BYTES)
        self.assertEqual(self.post(json.dumps(ok).encode())[0], 200)

    def test_missing_content_length(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/alert")
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 411)
        conn.close()
        self.assertEqual(self.files(), [])

    def test_wrong_path(self) -> None:
        for path in ("/", "/alerts", "/alert/", "/health/x", "/../alert"):
            self.assertRejected(404, self.post(json.dumps(PAYLOAD).encode(), path)[0])

    def test_wrong_method(self) -> None:
        body = json.dumps(PAYLOAD).encode()
        for method in ("GET", "PUT", "DELETE", "PATCH"):
            self.assertRejected(405, self.request(method, "/alert", body if method != "GET" else None)[0])
        self.assertRejected(405, self.request("POST", "/health", b"{}")[0])


class Health(ReceiverCase):
    def test_health_returns_200(self) -> None:
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})


class Logging(ReceiverCase):
    def lines(self) -> list[dict]:
        return [json.loads(line) for line in self.log.getvalue().splitlines()]

    def test_logs_are_json_in_the_backend_shape(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        self.request("GET", "/nope")
        lines = self.lines()
        self.assertGreaterEqual(len(lines), 2)
        for entry in lines:
            for key in ("timestamp", "severity", "message", "logger", "trace_id", "span_id"):
                self.assertIn(key, entry)
        self.assertEqual(lines[0]["route"], "/alert")
        self.assertEqual(lines[0]["status"], 200)
        self.assertEqual(lines[1]["route"], "unmatched")

    def test_logs_carry_no_client_address(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        self.post(b"{bad")
        self.request("GET", "/health")
        text = self.log.getvalue()
        self.assertNotIn("127.0.0.1", text)
        self.assertNotIn("localhost", text)
        self.assertIsNone(re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text))

    def test_logs_do_not_echo_the_body(self) -> None:
        self.post(json.dumps(PAYLOAD).encode())
        self.assertNotIn("Finding pages", self.log.getvalue())


class FingerprintNames(unittest.TestCase):
    def test_fallback_when_absent_or_empty(self) -> None:
        self.assertEqual(receiver.fingerprint_of({}), "nofingerprint")
        self.assertEqual(receiver.fingerprint_of({"fingerprint": "../"}), "nofingerprint")


if __name__ == "__main__":
    unittest.main()
