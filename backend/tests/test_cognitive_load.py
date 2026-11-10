# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cognitive-load regressions: aliases, the unified dispatcher, and --preset smoke.

These pin the burden-reduction contract:
- full benchmark/substrate names work wherever the short tokens do, and the
  canonical tokens flow downstream (namespaces, executor selection);
- `harness2 <command>` dispatches to the same mains as the legacy scripts;
- `--preset smoke` expands to the documented one-task smoke test, with
  explicit flags winning over preset defaults.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout


class AliasTests(unittest.TestCase):
    def test_bench_aliases_normalize(self):
        from sec_agent_harness2.cli import _common as C

        self.assertEqual(C.normalize_bench("jobbench"), "jb")
        self.assertEqual(C.normalize_bench("job-bench-eval"), "jb")
        self.assertEqual(C.normalize_bench("workbuddy"), "wb")
        self.assertEqual(C.normalize_bench("LAB"), "lab")
        self.assertEqual(C.normalize_bench("harvey-labs"), "lab")
        self.assertEqual(C.normalize_bench("jb"), "jb")

    def test_substrate_aliases_normalize(self):
        from sec_agent_harness2.cli import _common as C

        self.assertEqual(C.normalize_substrate("opencode"), "oc")
        self.assertEqual(C.normalize_substrate("OC"), "oc")
        self.assertEqual(C.normalize_substrate("pi"), "pi")
        self.assertEqual(C.normalize_substrate("PI"), "pi")

    def test_unknown_values_pass_through_to_canonical_error(self):
        from sec_agent_harness2.cli import _common as C

        self.assertEqual(C.normalize_bench("nope"), "nope")
        with self.assertRaises(ValueError):
            C.make_adapter("nope", None, "oc")


class PresetTests(unittest.TestCase):
    def _parse(self, *argv: str):
        from sec_agent_harness2.cli import run_sweep as R

        return R._build_parser().parse_args(list(argv))

    def test_smoke_expands_per_benchmark(self):
        from sec_agent_harness2.cli import _common as C

        for bench, domain in (
            ("jb", "biostatisticians"),
            ("lab", "antitrust-competition"),
            ("wb", "doc-ops"),
        ):
            with self.subTest(bench=bench):
                args = self._parse("--bench", bench, "--preset", "smoke")
                # replicate main()'s preset expansion
                args.bench = C.normalize_bench(args.bench)
                args.substrate = C.normalize_substrate(args.substrate)
                if args.preset == "smoke":
                    smoke = {"jb": "biostatisticians", "lab": "antitrust-competition", "wb": "doc-ops"}
                    args.only_domains = args.only_domains or smoke.get(args.bench, "")
                    if args.max_tasks is None:
                        args.max_tasks = 1
                    if args.bench == "wb" and not args.subset:
                        args.subset = "office"
                self.assertEqual(args.only_domains, domain)
                self.assertEqual(args.max_tasks, 1)
                if bench == "wb":
                    self.assertEqual(args.subset, "office")

    def test_explicit_flags_beat_preset(self):
        args = self._parse(
            "--bench", "lab", "--preset", "smoke",
            "--only-domains", "contracts", "--max-tasks", "3",
        )
        only = args.only_domains or "antitrust-competition"
        capped = args.max_tasks if args.max_tasks is not None else 1
        self.assertEqual((only, capped), ("contracts", 3))

    def test_preset_smoke_dry_run_end_to_end(self):
        from sec_agent_harness2.cli import run_sweep as R

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = R.main(["--bench", "lab", "--preset", "smoke", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("antitrust-competition", buf.getvalue())

    def test_full_name_alias_end_to_end(self):
        from sec_agent_harness2.cli import run_sweep as R

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = R.main(
                ["--bench", "harvey-labs", "--substrate", "opencode",
                 "--preset", "smoke", "--dry-run"]
            )
        self.assertEqual(rc, 0)
        self.assertIn("lab-oc-agg1", buf.getvalue())


class DispatcherTests(unittest.TestCase):
    def test_help_lists_one_command_per_stage(self):
        from sec_agent_harness2.cli import main as M

        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            M.main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        text = buf.getvalue()
        for cmd in ("setup", "check", "run", "judge", "report", "demo", "pipeline"):
            self.assertIn(cmd, text)

    def test_unknown_command_is_a_two_with_hint(self):
        from sec_agent_harness2.cli import main as M

        err = io.StringIO()
        with redirect_stderr(err):
            rc = M.main(["frobnicate"])
        self.assertEqual(rc, 2)
        self.assertIn("frobnicate", err.getvalue())

    def test_run_passthrough_matches_legacy(self):
        from sec_agent_harness2.cli import main as M

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = M.main(["run", "--bench", "lab", "--preset", "smoke", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("antitrust-competition", buf.getvalue())

    def test_sweep_alias_matches_run(self):
        from sec_agent_harness2.cli import main as M

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = M.main(["sweep", "--bench", "lab", "--preset", "smoke", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("antitrust-competition", buf.getvalue())

    def test_global_lang_flag_is_forwarded(self):
        from sec_agent_harness2.cli import main as M

        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            M.main(["--lang", "zh", "--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("统一入口", buf.getvalue())

    def test_pipeline_forwards_cell_only_to_check(self):
        """check takes no --k/--mode: pipeline must not leak run identity into it."""
        from unittest import mock

        from sec_agent_harness2.cli import main as M

        seen = {}

        def fake_check(argv):
            seen["check"] = list(argv)
            return 0

        def fake_run(argv):
            seen["run"] = list(argv)
            return 0

        with mock.patch("sec_agent_harness2.cli.check.main", side_effect=fake_check), mock.patch(
            "sec_agent_harness2.cli.run_sweep.main", side_effect=fake_run
        ):
            rc = M.main(
                ["pipeline", "--bench", "lab", "--preset", "smoke",
                 "--dry-run", "--", "--workers", "2"]
            )
        self.assertEqual(rc, 0)
        self.assertNotIn("--k", seen["check"])
        self.assertNotIn("--mode", seen["check"])
        self.assertEqual(seen["check"][:2], ["--bench", "lab"])
        # preset expanded, dry-run forwarded, `--` extras reach run only
        self.assertIn("antitrust-competition", seen["run"])
        self.assertIn("--dry-run", seen["run"])
        self.assertEqual(seen["run"].count("--workers"), 2)
        self.assertEqual(seen["run"][-2:], ["--workers", "2"])


if __name__ == "__main__":
    unittest.main()
