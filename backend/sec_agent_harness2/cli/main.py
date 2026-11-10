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

"""Unified dispatcher: one `harness2` entry for the whole lifecycle.

Why this exists: the package historically exposed 8 top-level scripts
(`harness2`, `harness2-setup`, `harness2-check`, `harness2-judge`,
`harness2-report`, `harness2-demo`, `harness2-bridge`, `harness2-ui`), each
with its own flag spelling (`benchmark` vs `--bench`, `--mode` vs `--modes`).
New users had to memorize which script took which flags and retype the same
run identity (`--bench/--k/--mode/--substrate/--seed`) on every step.

The dispatcher keeps every legacy script working (thin shims stay in place)
and adds one discoverable surface:

    harness2 run --bench lab --k 1 --mode parallel          # sweep (alias: sweep)
    harness2 judge --bench lab --k 1 --mode parallel        # grade selections
    harness2 report --bench lab --k 1                       # render cached scores
    harness2 setup lab                                      # install a benchmark
    harness2 check --bench lab                              # offline preflight
    harness2 demo                                           # zero-credential smoke test
    harness2 pipeline --bench lab --k 1 --mode parallel \\  # check→run→judge→report
        --only-domains antitrust-competition --max-tasks 1
    harness2 ui | harness2 bridge ...                        # passthrough tools

Selected commands forward unknown flags to the underlying module, so every
flag documented on the legacy scripts keeps working here.
"""

from __future__ import annotations

import argparse
import sys

from .. import i18n as I18N

_COMMANDS = (
    "setup",
    "check",
    "run",
    "sweep",
    "judge",
    "report",
    "demo",
    "pipeline",
    "ui",
)


def _build_parser(lang: str | None = None) -> argparse.ArgumentParser:
    lang = lang or I18N.get_lang()
    p = argparse.ArgumentParser(
        prog="harness2",
        description=I18N.t("cli.desc", lang),
    )
    p.add_argument("--lang", default=None, choices=("en", "zh"), help=I18N.t("cell.lang", lang))
    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    for name in _COMMANDS:
        key = f"cli.cmd_{name.replace('-', '_')}"
        help_text = I18N.t(key, lang)
        if help_text == key:
            help_text = name
        sub.add_parser(name, help=help_text, add_help=False)
    return p


def _passthrough(argv: list[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _run_pipeline(argv: list[str]) -> int:
    """check → run → judge → report, reusing one parsed identity.

    The pipeline parses only the shared identity + smoke-test flags, then
    replays them to each stage. Stage-specific flags (e.g. --workers for run,
    --bases for judge) pass through via `-- <extra args>` splitting:
    everything after `--` is forwarded to the run stage only.
    """
    from . import _common as C
    from . import check as check_mod
    from . import judge as judge_mod
    from . import report as report_mod
    from . import run_sweep as run_mod

    if "--" in argv:
        cut = argv.index("--")
        own, run_extra = argv[:cut], argv[cut + 1 :]
    else:
        own, run_extra = argv, []
    p = argparse.ArgumentParser(prog="harness2 pipeline")
    C.add_cell_args(p)
    C.add_run_identity_args(p)
    p.add_argument("--split", choices=("all", "train", "test"), default="all")
    p.add_argument("--preset", choices=("smoke",), default=None)
    p.add_argument("--only-domains", default="")
    p.add_argument("--max-tasks", type=int, default=None)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-judge", action="store_true")
    args, _ = p.parse_known_args(own)
    if args.preset == "smoke":
        _smoke = {"jb": "biostatisticians", "lab": "antitrust-competition", "wb": "doc-ops"}
        args.only_domains = args.only_domains or _smoke.get(args.bench, "")
        if args.max_tasks is None:
            args.max_tasks = 1
        if args.bench == "wb" and not args.subset:
            args.subset = "office"
    cell = ["--bench", args.bench]
    if args.subset:
        cell += ["--subset", args.subset]
    cell += ["--substrate", args.substrate]
    base = cell + ["--k", str(args.k), "--mode", args.modes]
    if args.seed is not None:
        base += ["--seed", str(args.seed)]

    lang = I18N.get_lang()
    print(I18N.t("cli.pipeline_check", lang), flush=True)
    if check_mod.main(cell) != 0:
        return 1
    run_argv = base + [
        "--split",
        args.split,
        "--only-domains",
        args.only_domains,
        "--workers",
        str(args.workers),
    ]
    if args.max_tasks is not None:
        run_argv += ["--max-tasks", str(args.max_tasks)]
    if args.dry_run:
        run_argv += ["--dry-run"]
    run_argv += run_extra
    print(I18N.t("cli.pipeline_run", lang), flush=True)
    if run_mod.main(run_argv) != 0:
        return 1
    if args.dry_run or args.skip_judge:
        return 0
    print(I18N.t("cli.pipeline_judge", lang), flush=True)
    judged = judge_mod.main(base)
    print(I18N.t("cli.pipeline_report", lang), flush=True)
    reported = report_mod.main(base)
    return judged or reported


def main(argv: list[str] | None = None) -> int:
    args = _passthrough(argv)
    # Split a leading `harness2 [--lang L] COMMAND ...` so the global flag is
    # honoured without being mistaken for the subcommand.
    lang = None
    rest_args = list(args)
    if len(rest_args) >= 2 and rest_args[0] == "--lang":
        lang, rest_args = rest_args[1], rest_args[2:]
    elif any(a.startswith("--lang=") for a in rest_args[:1]):
        lang = rest_args[0].split("=", 1)[1]
        rest_args = rest_args[1:]
    if not rest_args or rest_args[0] in ("-h", "--help"):
        _build_parser(lang).parse_args(
            ["--lang", lang, "--help"] if lang else (["--help"] if not rest_args else rest_args)
        )
        return 0
    cmd, rest = rest_args[0], rest_args[1:]
    cmd = cmd.replace("_", "-")
    if lang is not None and "--lang" not in rest:
        # Forward the global language to the subcommand, which owns --lang.
        rest = ["--lang", lang, *rest]
    if cmd not in _COMMANDS:
        print(I18N.t("cli.unknown", I18N.get_lang(), v=cmd, opts=", ".join(_COMMANDS)), file=sys.stderr)
        return 2
    if cmd == "pipeline":
        if rest[:1] in (["-h"], ["--help"]):
            print(I18N.t("cli.pipeline_help", I18N.get_lang()))
            return 0
        return _run_pipeline(rest)
    if cmd in ("run", "sweep"):
        from . import run_sweep as run_mod

        return run_mod.main(rest)
    if cmd == "judge":
        from . import judge as judge_mod

        return judge_mod.main(rest)
    if cmd == "report":
        from . import report as report_mod

        return report_mod.main(rest)
    if cmd == "setup":
        from . import setup as setup_mod

        return setup_mod.main(rest)
    if cmd == "check":
        from . import check as check_mod

        return check_mod.main(rest)
    if cmd == "demo":
        from . import demo as demo_mod

        return demo_mod.main(rest)
    if cmd == "ui":
        from . import ui as ui_mod

        return ui_mod.main(rest)
    print(I18N.t("cli.unknown", I18N.get_lang(), v=cmd, opts=", ".join(_COMMANDS)), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
