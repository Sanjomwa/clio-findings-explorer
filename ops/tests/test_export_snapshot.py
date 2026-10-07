"""Tests for ops/export_snapshot.py.

Every test uses the fake bq runner in fixtures/fake_bq.py; nothing here calls
BigQuery. Output goes to a temporary directory outside any git working tree.

Run from the repository root:
    python3 -m unittest discover -s ops/tests -v
"""

import dataclasses
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE / "fixtures"))

import export_snapshot as es  # noqa: E402
from fake_bq import FAKE_BYTES, FakeBq  # noqa: E402

REGIME = "intelligence.acled_pressure_regimes"
SIGNALS = "features.acled_pressure_signals"
OONI = "features.ooni_weekly_signals"
GOOGLE = "stg.google_transparency_requests"

EXPECTED_FILES = {
    "regime_weeks.ndjson",
    "acled_signal_context.ndjson",
    "ooni_weekly_signals.ndjson",
    "google_transparency_requests.ndjson",
}


class ExportTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.parent = Path(tmp.name).resolve()
        self.out = self.parent / "snapshot"
        self.bq = FakeBq(es)

    def run_export(self, *extra, out=None, exports=es.EXPORTS, version="2026-10-07.1"):
        argv = ["--out", str(out or self.out), "--acled-access-date", "2026-10-01"]
        if version:
            argv += ["--snapshot-version", version]
        argv += list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = es.main(argv, runner=self.bq, exports=exports)
        return code, stdout.getvalue(), stderr.getvalue()

    def assertNothingWritten(self):
        self.assertFalse(self.out.exists(), "--out was created")
        self.assertEqual(sorted(p.name for p in self.parent.iterdir()), [], "files left beside --out")

    def assertStopped(self, fragment, *extra, **kwargs):
        code, _, stderr = self.run_export(*extra, **kwargs)
        self.assertEqual(code, 1, stderr)
        self.assertIn("STOPPED", stderr)
        self.assertIn(fragment, stderr)
        self.assertNothingWritten()
        return stderr


class TestCleanRun(ExportTestCase):
    def setUp(self):
        super().setUp()
        code, self.stdout, stderr = self.run_export()
        self.assertEqual(code, 0, stderr)
        self.manifest = json.loads((self.out / "MANIFEST.json").read_text(encoding="utf-8"))

    def read_rows(self, name):
        lines = (self.out / name).read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_writes_four_files_and_manifest(self):
        self.assertEqual({p.name for p in self.out.iterdir()}, EXPECTED_FILES | {"MANIFEST.json"})
        # The temporary build directory was moved, not left behind.
        self.assertEqual([p.name for p in self.parent.iterdir()], ["snapshot"])

    def test_manifest_uses_openapi_names(self):
        self.assertEqual(self.manifest["version"], "2026-10-07.1")
        self.assertTrue(self.manifest["exported_at"].endswith("Z"))
        self.assertEqual(
            set(self.manifest),
            {"version", "exported_at", "tables", "synthetic_audit", "finding_anchors", "attribution"},
        )
        for entry in self.manifest["tables"]:
            self.assertEqual(
                set(entry), {"file", "source_table", "sql", "row_count", "sha256", "exported_at"}
            )

    def test_manifest_sha256_counts_and_sql_match(self):
        self.assertEqual([t["file"] for t in self.manifest["tables"]], [e.file for e in es.EXPORTS])
        run_sql = [c["sql"] for c in self.bq.data_calls()]
        for entry, export in zip(self.manifest["tables"], es.EXPORTS):
            with self.subTest(file=entry["file"]):
                data = (self.out / entry["file"]).read_bytes()
                self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(entry["row_count"], len(data.decode("utf-8").splitlines()))
                self.assertEqual(entry["source_table"], export.source_table)
                self.assertEqual(entry["sql"], export.sql)
                self.assertIn(entry["sql"], run_sql)

    def test_row_counts(self):
        counts = {t["file"]: t["row_count"] for t in self.manifest["tables"]}
        self.assertEqual(counts["regime_weeks.ndjson"], 1523)
        self.assertEqual(counts["acled_signal_context.ndjson"], 17 * len(es.FINDING_ANCHORS))
        self.assertEqual(counts["ooni_weekly_signals.ndjson"], 550)
        self.assertEqual(counts["google_transparency_requests.ndjson"], 90)

    def test_values_are_typed(self):
        regime = self.read_rows("regime_weeks.ndjson")
        first = regime[0]
        self.assertEqual(list(first), [name for name, _ in es.REGIME_COLUMNS])
        self.assertIsNone(first["previous_regime"])  # key absent in bq output
        self.assertIs(first["transition_detected"], False)
        self.assertEqual(first["regime_duration_weeks"], 3)
        self.assertEqual(first["computed_at"], "2026-03-15T04:12:33.123456Z")
        self.assertEqual(first["week_start_date"], "1997-01-11")
        signal = self.read_rows("acled_signal_context.ndjson")[0]
        self.assertEqual(signal["violence_pressure_z"], -1.5)
        self.assertIsNone(signal["suppression_z"])
        self.assertEqual(list(signal), [name for name, _ in es.SIGNAL_COLUMNS])
        self.assertEqual(signal["total_events"], 7)
        self.assertIsInstance(self.read_rows("ooni_weekly_signals.ndjson")[0]["blocked_rate"], float)

    def test_synthetic_audit_anchors_and_attribution(self):
        audit = self.manifest["synthetic_audit"]
        self.assertEqual(audit["result"], "passed")
        self.assertEqual(audit["synthetic_flag_columns"], [])
        self.assertEqual(len(audit["tables_checked"]), 4)
        self.assertEqual(len(audit["sql"]), 3)  # one schema read per dataset
        anchors = self.manifest["finding_anchors"]
        self.assertEqual(anchors["anchors"], list(es.FINDING_ANCHORS))
        self.assertEqual((anchors["weeks_before"], anchors["weeks_after"]), (12, 4))
        attribution = self.manifest["attribution"]
        self.assertEqual(attribution["acled"]["access_date"], "2026-10-01")
        self.assertEqual(attribution["ooni"]["licence"], "CC BY-NC-SA 4.0")
        self.assertEqual(attribution["google_transparency"]["licence"], "Reuse terms not determined")
        self.assertEqual(
            attribution["google_transparency"]["manipulation"],
            "Filtered to Kenya. period_date derived by CLIO from the reporting period label.",
        )
        self.assertEqual(attribution["acled"]["files"], ["regime_weeks.ndjson", "acled_signal_context.ndjson"])

    def test_schema_reads_run_before_data_queries(self):
        kinds = ["schema" if "INFORMATION_SCHEMA" in c["sql"] else "data" for c in self.bq.calls]
        self.assertEqual(kinds, ["schema"] * 3 + ["data"] * 4)
        self.assertTrue(all(c["max_rows"] == es.MAX_ROWS for c in self.bq.calls))


class TestDefaults(ExportTestCase):
    def test_default_version_is_utc_date_plus_1(self):
        code, _, stderr = self.run_export(version=None)
        self.assertEqual(code, 0, stderr)
        manifest = json.loads((self.out / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], datetime.now(timezone.utc).date().isoformat() + ".1")

    def test_existing_empty_out_is_filled(self):
        self.out.mkdir()
        code, _, stderr = self.run_export()
        self.assertEqual(code, 0, stderr)
        self.assertIn("MANIFEST.json", {p.name for p in self.out.iterdir()})

    def test_bad_access_date_is_a_usage_error(self):
        for value in ["2026-13-01", "01-10-2026", (date.today() + timedelta(days=30)).isoformat()]:
            with self.subTest(value=value), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    es.main(["--out", str(self.out), "--acled-access-date", value], runner=self.bq)
                self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(self.bq.calls, [])


class TestSyntheticGate(ExportTestCase):
    def test_flag_column_stops_before_any_data_query(self):
        # Obviously fake flagged column, allowed in ops/tests fixtures only.
        self.bq.schema[OONI].append(("fixture_fake_is_synthetic", "BOOL"))
        stderr = self.assertStopped("synthetic gate")
        self.assertIn("features.ooni_weekly_signals.fixture_fake_is_synthetic", stderr)
        self.assertEqual(self.bq.data_calls(), [])

    def test_bare_is_synthetic_and_case(self):
        self.bq.schema[REGIME].append(("Is_Synthetic", "BOOL"))
        self.assertStopped("synthetic gate")

    def test_gate_runs_in_dry_run(self):
        self.bq.schema[GOOGLE].append(("fixture_fake_is_synthetic", "BOOL"))
        self.assertStopped("synthetic gate", "--dry-run")
        self.assertEqual(self.bq.data_calls(), [])


class TestSchemaCheck(ExportTestCase):
    def test_missing_expected_column(self):
        self.bq.schema[SIGNALS] = [c for c in self.bq.schema[SIGNALS] if c[0] != "suppression_z"]
        self.assertStopped("features.acled_pressure_signals.suppression_z is missing")
        self.assertEqual(self.bq.data_calls(), [])

    def test_unexpected_type(self):
        self.bq.schema[REGIME] = [
            (c, "DATETIME" if c == "computed_at" else t) for c, t in self.bq.schema[REGIME]
        ]
        self.assertStopped("computed_at is DATETIME, expected TIMESTAMP")

    def test_missing_table(self):
        del self.bq.schema[GOOGLE]
        self.assertStopped("schema read found no columns for: stg.google_transparency_requests")

    def test_denied_term_in_schema_results_is_not_a_failure(self):
        # Decision 2: the deny-list does not apply to INFORMATION_SCHEMA results.
        self.bq.schema[REGIME].append(("composite_pressure_score", "FLOAT64"))
        self.bq.schema[SIGNALS].append(("lumen_legal_pressure", "FLOAT64"))
        code, _, stderr = self.run_export()
        self.assertEqual(code, 0, stderr)


class TestDenyList(ExportTestCase):
    def test_each_term_in_pinned_sql(self):
        for term in es.DENY_TERMS:
            with self.subTest(term=term):
                self.bq.calls.clear()
                exports = tuple(
                    dataclasses.replace(e, sql=e.sql.replace("SELECT", f"SELECT {term.upper()}_x,", 1))
                    if e.file == "acled_signal_context.ndjson" else e
                    for e in es.EXPORTS
                )
                self.assertStopped(f"deny-list: the pinned SQL for acled_signal_context.ndjson contains {term!r}",
                                   exports=exports)
                self.assertEqual(self.bq.calls, [], "a query ran before the deny-list check")

    def test_each_term_in_returned_column(self):
        for term in es.DENY_TERMS:
            with self.subTest(term=term):
                self.bq = FakeBq(es)
                self.bq.data[OONI][5][f"Fixture_{term.title()}"] = "1"
                self.assertStopped(f"which contains {term!r}")


class TestShape(ExportTestCase):
    def test_quoted_column_list(self):
        # SELECT 'week_start_date, country, ...' returns one string per row.
        quoted = ", ".join(name for name, _ in es.REGIME_COLUMNS)
        self.bq.data[REGIME] = [{"f0_": quoted}] * 1523
        self.assertStopped("shape: regime_weeks.ndjson, row 1 has unexpected columns ['f0_']")

    def test_row_not_an_object(self):
        self.bq.raw[GOOGLE] = json.dumps(["just a string"])
        self.assertStopped("shape: google_transparency_requests.ndjson, row 1 is not an object")

    def test_missing_key_column(self):
        del self.bq.data[OONI][0]["week_start_date"]
        self.assertStopped("shape: ooni_weekly_signals.ndjson, row 1 has no week_start_date")

    def test_output_not_json(self):
        self.bq.raw[GOOGLE] = "Waiting on bqjob_r1 ... (0s) Current status: DONE"
        self.assertStopped("bq output is not JSON")

    def test_uncastable_value(self):
        self.bq.data[REGIME][10]["regime_duration_weeks"] = "three"
        self.assertStopped("type: regime_weeks.ndjson, row 11, column regime_duration_weeks")

    def test_truncation_at_max_rows(self):
        with mock.patch.object(es, "MAX_ROWS", 100):
            self.assertStopped("reached --max_rows=100")


class TestRegimeChecks(ExportTestCase):
    def regime_weeks(self):
        return self.bq.data[REGIME]

    def test_short_table(self):
        self.regime_weeks().pop()
        self.assertStopped("1522 rows, expected at least 1523")

    def test_non_saturday_week(self):
        row = self.regime_weeks()[100]
        row["week_start_date"] = (date.fromisoformat(row["week_start_date"]) + timedelta(days=1)).isoformat()
        self.assertStopped("week_start_date is not a Saturday")

    def test_gap(self):
        rows = self.regime_weeks()
        last = date.fromisoformat(rows[-1]["week_start_date"])
        extra = dict(rows[-1], week_start_date=(last + timedelta(weeks=1)).isoformat())
        rows.append(extra)
        removed = rows.pop(700)  # still 1523 rows, now with a one-week gap
        self.assertStopped("weeks are not consecutive")
        self.assertEqual(len(rows), 1523)
        self.assertTrue(removed)

    def test_duplicate(self):
        rows = self.regime_weeks()
        rows.insert(50, dict(rows[50]))
        self.assertStopped("duplicate week_start_date")


class TestWindowChecks(ExportTestCase):
    def test_window_with_16_rows(self):
        rows = self.bq.data[SIGNALS]
        rows[:] = [r for r in rows if r["week_start_date"] != "2024-06-22"]
        self.assertStopped("anchor 2024-06-22: 16 rows, expected exactly 17")

    def test_window_with_duplicate_instead_of_missing_week(self):
        rows = self.bq.data[SIGNALS]
        index = next(i for i, r in enumerate(rows) if r["week_start_date"] == "2008-01-19")
        rows[index] = dict(rows[index], week_start_date="2008-01-26")
        self.assertStopped("missing weeks: 2008-01-19")

    def test_signal_row_outside_windows(self):
        self.bq.data[SIGNALS].append(dict(self.bq.data[SIGNALS][0], week_start_date="2015-01-03"))
        self.assertStopped("rows outside every finding window: 2015-01-03")

    def test_window_sql_covers_every_anchor(self):
        for anchor in es.anchor_dates():
            weeks = es.window_weeks(anchor)
            self.assertEqual(len(weeks), 17)
            clause = f"BETWEEN DATE '{weeks[0]}' AND DATE '{weeks[-1]}'"
            self.assertIn(clause, es.SIGNAL_SQL)


class TestQueries(unittest.TestCase):
    def test_order_by_covers_every_selected_column(self):
        for export in es.EXPORTS:
            with self.subTest(file=export.file):
                order_by = export.sql.split("ORDER BY", 1)[1]
                keys = [k.strip() for k in order_by.split(",")]
                self.assertEqual(sorted(keys), sorted(name for name, _ in export.columns))

    def test_order_by_leading_keys(self):
        leading = {
            "regime_weeks.ndjson": ["week_start_date"],
            "acled_signal_context.ndjson": ["week_start_date"],
            "ooni_weekly_signals.ndjson": ["week_start_date", "test_name"],
            "google_transparency_requests.ndjson": ["period_date", "requestor", "product", "reason"],
        }
        for export in es.EXPORTS:
            with self.subTest(file=export.file):
                keys = [k.strip() for k in export.sql.split("ORDER BY", 1)[1].split(",")]
                self.assertEqual(keys[: len(leading[export.file])], leading[export.file])

    def test_event_table_is_not_exported(self):
        self.assertEqual([e.file for e in es.EXPORTS], [
            "regime_weeks.ndjson",
            "acled_signal_context.ndjson",
            "ooni_weekly_signals.ndjson",
            "google_transparency_requests.ndjson",
        ])
        for export in es.EXPORTS:
            self.assertNotIn("acled_conflict_events", export.sql)
            self.assertNotIn("sub_event_type", export.sql)
            # One-to-one ACLED event-type counts, removed from the signal context.
            for name in ["protest_events", "disorder_events", "disorder_fatalities",
                         "violence_events", "violence_fatalities", "suppression_events"]:
                self.assertNotIn(name, export.sql)


class TestOtherMinimums(ExportTestCase):
    def test_ooni_below_550(self):
        del self.bq.data[OONI][-1]
        self.assertStopped("check failed for ooni_weekly_signals.ndjson: 549 rows")

    def test_ooni_duplicate_week_and_test(self):
        rows = self.bq.data[OONI]
        rows[7] = dict(rows[7], test_name=rows[6]["test_name"])
        self.assertStopped("duplicate (week_start_date, test_name): (2023-06-03, signal)")

    def test_google_below_85(self):
        del self.bq.data[GOOGLE][84:]
        self.assertStopped("check failed for google_transparency_requests.ndjson: 84 rows")


class TestDryRun(ExportTestCase):
    def test_writes_nothing_and_prints_bytes(self):
        code, stdout, stderr = self.run_export("--dry-run")
        self.assertEqual(code, 0, stderr)
        self.assertNothingWritten()
        schema_calls = [c for c in self.bq.calls if "INFORMATION_SCHEMA" in c["sql"]]
        self.assertEqual(len(schema_calls), 3)
        self.assertTrue(all(not c["dry_run"] for c in schema_calls))
        data_calls = self.bq.data_calls()
        self.assertEqual(len(data_calls), 4)
        self.assertTrue(all(c["dry_run"] for c in data_calls))
        for name in EXPECTED_FILES:
            self.assertIn(f"{name}: would process {FAKE_BYTES} bytes", stdout)
        self.assertIn(f"Total: {4 * FAKE_BYTES} bytes", stdout)

    def test_dry_run_still_checks_out(self):
        self.out.mkdir()
        (self.out / "keep.txt").write_text("x")
        code, _, stderr = self.run_export("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("is not empty", stderr)
        self.assertEqual(self.bq.calls, [])

    def test_parse_dry_run_bytes_forms(self):
        self.assertEqual(es.parse_dry_run_bytes('{"statistics": {"query": {"totalBytesProcessed": "42"}}}'), 42)
        self.assertEqual(
            es.parse_dry_run_bytes(
                "Query successfully validated. Assuming the tables are not modified, "
                "running this query will process 1234 bytes of data."
            ),
            1234,
        )
        with self.assertRaises(es.ExportError):
            es.parse_dry_run_bytes("something else")


class TestOutDir(ExportTestCase):
    def make_repo(self, name):
        repo = self.parent / name
        (repo / ".git").mkdir(parents=True)
        return repo

    def test_refuses_inside_another_repository(self):
        repo = self.make_repo("other-repo")
        out = repo / "snapshot"
        code, _, stderr = self.run_export(out=out)
        self.assertEqual(code, 1)
        self.assertIn(f"is inside the git working tree {repo}", stderr)
        self.assertFalse(out.exists())
        self.assertEqual(self.bq.calls, [])

    def test_refuses_relative_out_when_cwd_is_another_repository(self):
        repo = self.make_repo("cwd-repo")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(repo)
        code, _, stderr = self.run_export(out=Path("snapshot"))
        self.assertEqual(code, 1)
        self.assertIn("is inside the git working tree", stderr)
        self.assertEqual(sorted(p.name for p in repo.iterdir()), [".git"])

    def test_refuses_non_empty_out(self):
        self.out.mkdir()
        (self.out / "old.ndjson").write_text("{}\n")
        code, _, stderr = self.run_export()
        self.assertEqual(code, 1)
        self.assertIn("exists and is not empty", stderr)
        self.assertEqual([p.name for p in self.out.iterdir()], ["old.ndjson"])
        self.assertEqual(self.bq.calls, [])

    def test_refuses_missing_parent(self):
        code, _, stderr = self.run_export(out=self.parent / "missing" / "snapshot")
        self.assertEqual(code, 1)
        self.assertIn("the parent of --out does not exist", stderr)

    def test_only_this_repos_data_snapshot_is_allowed(self):
        repo = self.make_repo("this-repo")
        (repo / "data").mkdir()
        allowed = repo / "data" / "snapshot"
        self.assertEqual(es.check_out_dir(allowed, repo_root=repo), allowed)
        self.assertFalse(allowed.exists(), "check_out_dir must not create anything")
        for refused in [repo / "data" / "other", repo / "data" / "snapshot" / "nested", repo / "snapshot"]:
            with self.subTest(out=refused):
                with self.assertRaises(es.ExportError):
                    es.check_out_dir(refused, repo_root=repo)
        with self.assertRaises(es.ExportError):
            es.check_out_dir(allowed, repo_root=None)

    def test_repo_root_is_this_checkout(self):
        self.assertEqual(es.REPO_ROOT, HERE.parent.parent)


class TestRunBq(unittest.TestCase):
    """run_bq itself, with subprocess.run patched; no bq is ever started."""

    def completed(self, returncode=0, stdout="[]", stderr=""):
        return mock.Mock(returncode=returncode, stdout=stdout, stderr=stderr)

    def test_argv(self):
        with mock.patch.object(es.subprocess, "run", return_value=self.completed()) as run:
            self.assertEqual(es.run_bq("SELECT 1"), "[]")
            es.run_bq("SELECT 2", dry_run=True)
        self.assertEqual(run.call_args_list[0].args[0], [
            "bq", "--quiet", "query", "--use_legacy_sql=false", "--format=json",
            "--max_rows=100000", "SELECT 1",
        ])
        self.assertEqual(run.call_args_list[1].args[0], [
            "bq", "--quiet", "query", "--use_legacy_sql=false", "--format=json",
            "--max_rows=100000", "--dry_run", "SELECT 2",
        ])

    def test_non_zero_exit(self):
        failed = self.completed(returncode=2, stdout="", stderr="Not found: Table x")
        with mock.patch.object(es.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(es.ExportError, "bq exited with status 2:\nNot found: Table x"):
                es.run_bq("SELECT 1")

    def test_bq_not_installed(self):
        with mock.patch.object(es.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(es.ExportError, "bq CLI was not found"):
                es.run_bq("SELECT 1")


class TestCastValue(unittest.TestCase):
    def test_accepted_forms(self):
        cases = [
            ("12", es.INT, 12), (12, es.INT, 12),
            ("0.5", es.FLOAT, 0.5), ("1e-3", es.FLOAT, 0.001), (2, es.FLOAT, 2.0),
            ("true", es.BOOL, True), ("FALSE", es.BOOL, False), (True, es.BOOL, True),
            ("2024-06-22", es.DATE, "2024-06-22"),
            ("2026-03-15 04:12:33 UTC", es.TIMESTAMP, "2026-03-15T04:12:33Z"),
            ("2026-03-15T04:12:33.5Z", es.TIMESTAMP, "2026-03-15T04:12:33.500000Z"),
            ("2026-03-15 04:12:33.1234567 UTC", es.TIMESTAMP, "2026-03-15T04:12:33.123456Z"),
            ("2026-03-15T07:12:33+03:00", es.TIMESTAMP, "2026-03-15T04:12:33Z"),
            ("1.7e9", es.TIMESTAMP, "2023-11-14T22:13:20Z"),
            (None, es.INT, None), ("x", es.STRING, "x"),
        ]
        for value, kind, expected in cases:
            with self.subTest(value=value, kind=kind):
                self.assertEqual(es.cast_value(value, kind), expected)

    def test_rejected_forms(self):
        cases = [
            ("1.5", es.INT), (True, es.INT), ("NaN", es.FLOAT), ("inf", es.FLOAT),
            ("yes", es.BOOL), ("2024-6-22", es.DATE), ("2024-02-30", es.DATE),
            ("not a time", es.TIMESTAMP), (3, es.STRING), ({"a": 1}, es.STRING),
        ]
        for value, kind in cases:
            with self.subTest(value=value, kind=kind):
                with self.assertRaises(es._CastError):
                    es.cast_value(value, kind)


if __name__ == "__main__":
    unittest.main()
