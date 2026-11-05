"""The production promotion trims whitespace around the sha input, then validates it.

Loads .github/workflows/deploy.yml and:
  - runs the `id: sha` step's script with bash, with SHA_INPUT set and GITHUB_ENV / GITHUB_OUTPUT
    pointing at temp files: surrounding spaces, tabs, CR and LF are trimmed and the trimmed value is
    written; anything else that is not a full 40-character lowercase SHA fails and writes nothing;
  - checks the structure: the job env has SHA_INPUT and no SHA, the `id: sha` step comes before
    checkout, checkout uses the step output, and no run script reads inputs.sha.

Needs PyYAML (CI installs it for this suite) and bash.

Run from the repository root:
    python3 -m unittest discover -s ops/tests -v
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "deploy.yml"
GOOD = "0123456789abcdef0123456789abcdef01234567"
BASH = shutil.which("bash") or "/bin/bash"


def load_job():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["promote-production"], workflow


def sha_step_index(steps):
    return next(i for i, step in enumerate(steps) if step.get("id") == "sha")


def run_sha_step(sha_input):
    """Run the `id: sha` script; return (exit code, GITHUB_ENV text, GITHUB_OUTPUT text, stdout)."""
    job, _ = load_job()
    script = job["steps"][sha_step_index(job["steps"])]["run"]
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / "env"
        out_file = Path(tmp) / "output"
        env_file.touch()
        out_file.touch()
        # The script comes from the committed workflow and the input from this file's constants.
        result = subprocess.run(  # noqa: S603
            [BASH, "-e", "-c", script],
            env={
                "PATH": "/usr/bin:/bin",
                "SHA_INPUT": sha_input,
                "GITHUB_ENV": str(env_file),
                "GITHUB_OUTPUT": str(out_file),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, env_file.read_text(), out_file.read_text(), result.stdout


class AcceptedAndTrimmed(unittest.TestCase):
    def assert_accepted(self, sha_input):
        code, env_text, out_text, _ = run_sha_step(sha_input)
        self.assertEqual(code, 0)
        self.assertEqual(env_text, f"SHA={GOOD}\n")
        self.assertEqual(out_text, f"sha={GOOD}\n")

    def test_exact_sha(self):
        self.assert_accepted(GOOD)

    def test_leading_spaces(self):
        self.assert_accepted("   " + GOOD)

    def test_trailing_newline(self):
        self.assert_accepted(GOOD + "\n")

    def test_tabs(self):
        self.assert_accepted("\t" + GOOD + "\t\t")

    def test_crlf(self):
        self.assert_accepted("\r\n" + GOOD + "\r\n")

    def test_mixed_surrounding_whitespace(self):
        self.assert_accepted(" \t\r\n " + GOOD + " \r\n\t ")


class Rejected(unittest.TestCase):
    def assert_rejected(self, sha_input):
        code, env_text, out_text, stdout = run_sha_step(sha_input)
        self.assertNotEqual(code, 0)
        self.assertEqual(env_text, "")
        self.assertEqual(out_text, "")
        self.assertIn("::error::", stdout)

    def test_empty(self):
        self.assert_rejected("")

    def test_whitespace_only(self):
        self.assert_rejected("  \t\r\n ")

    def test_39_characters(self):
        self.assert_rejected(GOOD[:-1])

    def test_41_characters(self):
        self.assert_rejected(GOOD + "0")

    def test_uppercase_hex(self):
        self.assert_rejected(GOOD.upper())

    def test_space_inside(self):
        self.assert_rejected(GOOD[:20] + " " + GOOD[21:])

    def test_newline_inside(self):
        self.assert_rejected(GOOD + "\nrest")

    def test_label_prefix(self):
        self.assert_rejected("SHA: " + GOOD)


class Structure(unittest.TestCase):
    def test_job_env_has_sha_input_and_no_sha(self):
        job, _ = load_job()
        self.assertIn("SHA_INPUT", job["env"])
        self.assertNotIn("SHA", job["env"])
        self.assertEqual(job["env"]["SHA_INPUT"], "${{ inputs.sha }}")

    def test_sha_step_comes_before_checkout(self):
        job, _ = load_job()
        steps = job["steps"]
        checkout = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/checkout@"))
        self.assertLess(sha_step_index(steps), checkout)

    def test_checkout_uses_the_trimmed_output(self):
        job, _ = load_job()
        checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["ref"], "${{ steps.sha.outputs.sha }}")

    def test_no_run_script_reads_inputs_sha(self):
        _, workflow = load_job()
        for name, job in workflow["jobs"].items():
            for step in job["steps"]:
                self.assertNotIn("inputs.sha", step.get("run", ""), f"{name}: {step.get('name')}")


if __name__ == "__main__":
    unittest.main()
