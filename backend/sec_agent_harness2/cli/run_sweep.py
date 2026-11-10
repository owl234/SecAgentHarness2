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

"""Run one adaptation sweep: every task of a split, domains parallel, tasks in stream order.

Thin argparse over core.schedule.run_sweep. Costs money when run for real: each task is
R=4k task-executor rollouts and P=3k improver sessions. `--dry-run` prints the exact
(domain, task) stream and namespaces without creating a Proposer, touching a substrate or
validating a model setting.

A real run checks the judge before the first rollout, because the namespace records the
judge model and `harness2-judge` refuses to grade it under a different one: discovering a
missing judge after the sweep means paying for the sweep twice. The check is offline — a
judge model must be named and a benchmark that grades in its own environment must have it
installed — so it catches an unset or unbuilt judge, not one an account cannot serve.

    python3 -m sec_agent_harness2.cli.run_sweep --bench jb --substrate oc --k 2 --split all
    python3 -m sec_agent_harness2.cli.run_sweep --bench wb --subset web --substrate cx \\
        --k 1 --split all --seed 7 --modes parallel --max-tasks 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from .. import i18n as I18N
from ..core import schedule
from ..core.proposer import Proposer
from . import _common as C


def _build_parser() -> argparse.ArgumentParser:
    lang = I18N.get_lang()
    p = argparse.ArgumentParser(
        prog="sec_agent_harness2.cli.run_sweep", description=I18N.t("sweep.desc", lang), formatter_class=C.HelpFormatter
    )
    C.add_cell_args(p.add_argument_group(I18N.t("sweep.group_cell", lang)))
    C.add_run_identity_args(p.add_argument_group(I18N.t("sweep.group_identity", lang)))
    g = p.add_argument_group(I18N.t("sweep.group_control", lang))
    g.add_argument("--lang", default=None, choices=("en", "zh"), help=I18N.t("cell.lang", lang))
    g.add_argument(
        "--preset",
        choices=("smoke",),
        default=None,
        help=I18N.t("sweep.preset", lang),
    )
    g.add_argument("--split", choices=("all", "train", "test"), default="all")
    g.add_argument("--split-file", type=Path, help=I18N.t("sweep.split_file", lang))
    g.add_argument("--workers", type=int, default=1, help=I18N.t("sweep.workers", lang))
    g.add_argument(
        "--only-domains", default="", help=I18N.t("sweep.only_domains", lang)
    )
    g.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help=I18N.t("sweep.max_tasks", lang),
    )
    g.add_argument(
        "--dry-run",
        action="store_true",
        help=I18N.t("sweep.dry_run", lang),
    )
    return p


def _csv(raw: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in raw.split(",") if s.strip())


def _stream_for(adapter, args) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    by_domain = schedule.task_stream(
        adapter,
        split=args.split,
        seed=args.seed,
        only_domains=_csv(args.only_domains),
        max_tasks=args.max_tasks,
    )
    return by_domain, [(domain, task) for domain, tasks in by_domain.items() for task in tasks]


def _print_stream(adapter, args, modes) -> int:
    by_domain, stream = _stream_for(adapter, args)
    print(
        f"# {adapter.spec.name}-{adapter.substrate.name} split={args.split} "
        f"seed={args.seed} k={args.k} modes={','.join(C.mode_label(m) for m in modes)}"
    )
    for m in modes:
        namespace = schedule.ns(
            adapter.spec.name, adapter.substrate.name, m, args.k, seed=args.seed
        )
        print(f"#   namespace[{C.mode_label(m)}]: {namespace}")
    print(
        f"#   summaries under: {C.runs_root_for(adapter)}/"
        f"{C.summary_namespace(adapter, args.k, seed=args.seed)}"
    )
    print(f"#   library root:    {C.library_root_for(adapter, args.k, seed=args.seed)}")
    print(f"#   domains parallel: {args.workers}")
    for i, (domain, task) in enumerate(stream, 1):
        print(f"{i:>4}  {domain:<40} {task}")
    lang = I18N.resolve_lang(args)
    print(I18N.t("sweep.domains_of_split", lang))
    for d, tasks in by_domain.items():
        print(f"{len(tasks):>4}  {d}")
    cap = f", max {args.max_tasks} per domain" if args.max_tasks is not None else ""
    print(
        f"# {len(stream)} tasks over {len(by_domain)} domains "
        f"(domains parallel, tasks within a domain sequential{cap})"
    )
    return 0 if stream else 1


def main(argv: list[str] | None = None) -> int:
    """Parse, then run `_main`, printing a misconfiguration as one remediation line."""
    args = _build_parser().parse_args(argv)
    # Aliases (jobbench/opencode/...) are accepted at the CLI surface but the
    # canonical short tokens flow downstream: namespaces, libraries, and the
    # executor/model selection in _check_identity all key on them.
    args.bench = C.normalize_bench(args.bench)
    args.substrate = C.normalize_substrate(args.substrate)
    if args.preset == "smoke":
        # The documented one-task smoke test, as a single memorable flag.
        # Benchmarks restrict to one known domain so --max-tasks 1 is enough;
        # wb additionally defaults its required --subset (explicit wins).
        _smoke = {"jb": "biostatisticians", "lab": "antitrust-competition", "wb": "doc-ops"}
        args.only_domains = args.only_domains or _smoke.get(args.bench, "")
        if args.max_tasks is None:
            args.max_tasks = 1
        if args.bench == "wb" and not args.subset:
            args.subset = "office"
    try:
        return _main(args)
    except (config.ConfigError, RuntimeError, ValueError, FileNotFoundError) as e:
        _l = I18N.get_lang()
        print(I18N.t("sweep.err_prefix", _l, e=e), file=sys.stderr)
        return 1


def _main(args: argparse.Namespace) -> int:
    lang = I18N.resolve_lang(args)
    if args.k < 1 or args.workers < 1:
        raise ValueError(I18N.t("sweep.err_k_workers", lang))
    modes = C.parse_modes(args.modes)

    if args.dry_run:
        return _print_stream(
            C.make_adapter(args.bench, args.subset, args.substrate, args.split_file), args, modes
        )

    adapter = C.make_adapter(args.bench, args.subset, args.substrate, args.split_file)
    _stream_for(adapter, args)
    from ..preflight import require_ready

    require_ready(adapter, judge=True)

    runs_root = C.runs_root_for(adapter)
    library_root = C.library_root_for(adapter, args.k, seed=args.seed)
    summary_ns = C.summary_namespace(adapter, args.k, seed=args.seed)
    _check_identity(adapter, args, runs_root / summary_ns)
    prop = Proposer(adapter.spec.channels["proposer"], audit_dir=runs_root / "_audit" / summary_ns)

    only = _csv(args.only_domains)
    lanes = args.workers
    lang = I18N.resolve_lang(args)
    print(
        I18N.t("sweep.start", lang, ns=summary_ns, lanes=lanes),
        flush=True,
    )
    rep = schedule.run_sweep(
        args.k,
        adapter=adapter,
        prop=prop,
        runs_root=runs_root,
        library_root=library_root,
        split=args.split,
        modes=modes,
        seed=args.seed,
        tag="",
        domain_parallel=lanes,
        only_domains=only,
        max_tasks=args.max_tasks,
        pool_policy="finals",
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rec = runs_root / "_sweeps" / f"{summary_ns}-{stamp}.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")

    done = sum(int(d.get("done", 0)) for d in rep["domains"])
    failed = sum(int(d.get("failed", 0)) for d in rep["domains"])
    dead = [d["domain"] for d in rep["domains"] if d.get("error")]
    if not rep["domains"]:
        lang = I18N.resolve_lang(args)
        print(
            "\n" + I18N.t("sweep.zero_tasks", lang, ns=summary_ns, split=args.split, only=only, max=args.max_tasks),
        )
        print(I18N.t("sweep.record", lang, rec=rec))
        return 1
    lang = I18N.resolve_lang(args)
    print(
        "\n" + I18N.t("sweep.done", lang, ns=summary_ns, done=done, failed=failed, ndead=len(dead), died=(': ' + ', '.join(dead) if dead else '')),
    )
    lang = I18N.resolve_lang(args)
    print(I18N.t("sweep.record", lang, rec=rec))
    lang = I18N.resolve_lang(args)
    print(
        I18N.t("sweep.next", lang) + f"   python3 -m sec_agent_harness2.cli.judge --bench {args.bench}"
        + (f" --subset {args.subset}" if args.subset else "")
        + f" --substrate {args.substrate} --k {args.k}"
        + (f" --seed {args.seed}" if args.seed is not None else "")
        + f" --modes {args.modes}"
    )

    if dead:
        return 1
    return 2 if failed else 0


def _check_identity(adapter, args, namespace_dir: Path) -> None:
    """Prevent a resumed run or library from silently mixing models or task partitions."""
    executor_map = {
        "oc": config.SOLVER_MODEL_OC,
        "pi": config.SOLVER_MODEL_PI,
    }
    identity = {
        "method_version": config.METHOD_VERSION,
        "executor": executor_map.get(args.substrate, config.SOLVER_MODEL_OC),
        "improver": config.IMPROVER_MODEL,
        "judge": config.JUDGE_MODEL,
        "project": config.VERTEX_PROJECT,
        "location": config.VERTEX_REGION,
        "judge_endpoint": config.JB_JUDGE_API_BASE,
        "endpoint": "",
        "split": args.split,
        "tasks": _stream_for(adapter, args)[1],
        "max_tasks": args.max_tasks,
        "domains": sorted(_csv(args.only_domains)),
        "seed": args.seed,
    }
    namespace_dir.mkdir(parents=True, exist_ok=True)
    path = namespace_dir / "config.json"
    if path.is_file():
        if json.loads(path.read_text()) != json.loads(json.dumps(identity)):
            raise ValueError(
                I18N.t("sweep.err_identity")
            )
    else:
        path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
