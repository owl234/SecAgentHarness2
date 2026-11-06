#!/usr/bin/env python3
"""LAB runner for PiSubstrate (Pi Coding Agent CLI)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from external.tts_lab import config as lab_cfg

PI_ROOT_ENTRIES = ("AGENTS.md", ".pi", "scripts", "sub_agents", "mcp", ".mcp.json", "_pi_runtime")


def run_dir_for(run_id: str, *, results_root: Path) -> Path:
    """Resolve `run_id` inside `results_root`, preserving nested directories while preventing escape."""
    root = Path(results_root).resolve()
    target = (root / run_id).resolve()
    if root != target and root not in target.parents:
        sys.exit(f"refusing run_id outside results_root: {run_id!r}")
    return target


def _build_prompt(task_dir: Path, ws_dir: Path, out_dir: Path) -> str:
    task_json = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    instructions = str(task_json.get("instructions", "")).strip()
    deliverables = task_json.get("deliverables") or {}
    deliv_lines = [
        f"- `{name}`" + (f": {desc}" if desc and desc != name else "")
        for name, desc in deliverables.items()
    ]
    deliv_block = "\n".join(deliv_lines) if deliv_lines else "(see instructions)"
    return (
        f"You are completing a legal assignment in `{ws_dir}`.\n\n"
        f"- Source documents: `{ws_dir / 'documents'}` (read-only)\n"
        f"- Deliverable directory: `{out_dir}` (write every requested deliverable into `output/<filename>`)\n"
        f"- Helper scripts: `{ws_dir / 'scripts'}` (use `python3 scripts/read_doc.py <path>` for binary docs)\n\n"
        f"## Instructions\n\n{instructions}\n\n"
        f"## Requested Deliverables\n\n{deliv_block}\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one LAB task with Pi Coding Agent")
    p.add_argument("--task", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--model", default="gpt-5.4")
    p.add_argument("--reasoning-effort", default="high")
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--harness-dir", type=Path, required=True)
    args = p.parse_args(argv)

    repo_root = Path(getattr(lab_cfg, "REPO_ROOT", Path.cwd())).resolve()
    results_root = Path(
        os.environ.get("ADAPT_LABPI_RESULTS", str(repo_root / "results" / "pi"))
    ).resolve()
    scratch_root = Path(
        os.environ.get("ADAPT_LABPI_SCRATCH", str(tempfile.gettempdir()))
    ).resolve()
    scratch_root.mkdir(parents=True, exist_ok=True)

    run_dir = run_dir_for(args.run_id, results_root=results_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    out_dir = run_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    task_dir = repo_root / "tasks" / args.task
    if not (task_dir / "task.json").is_file():
        sys.exit(f"task.json not found at {task_dir / 'task.json'}")

    ws_dir = Path(tempfile.mkdtemp(prefix="lab_pi_ws_", dir=str(scratch_root)))
    try:
        docs_src = task_dir / "documents"
        if docs_src.is_dir():
            shutil.copytree(docs_src, ws_dir / "documents", dirs_exist_ok=True)
        else:
            (ws_dir / "documents").mkdir(parents=True, exist_ok=True)

        (ws_dir / "output").mkdir(parents=True, exist_ok=True)
        (ws_dir / "scripts").mkdir(parents=True, exist_ok=True)

        read_doc_src = repo_root / "opencode" / "scripts" / "read_doc.py"
        if read_doc_src.is_file():
            shutil.copy2(read_doc_src, ws_dir / "scripts" / "read_doc.py")

        if args.harness_dir and args.harness_dir.is_dir():
            for entry in PI_ROOT_ENTRIES:
                src = args.harness_dir / entry
                if not src.exists():
                    continue
                dst = ws_dir / entry
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

        pi_bin = os.environ.get("ADAPT_LABPI_BIN", "pi")
        model_raw = args.model or "gpt-5.4"
        if "/" in model_raw:
            provider, model_id = model_raw.split("/", 1)
        else:
            provider, model_id = "sec_agent_harness2", model_raw

        prompt = _build_prompt(task_dir, ws_dir, ws_dir / "output")
        cmd = [
            pi_bin,
            "-p",
            prompt,
            "--mode",
            "json",
            "--no-session",
            "--tools",
            "read,bash,edit,write,grep,find,ls",
            "--provider",
            provider,
            "--model",
            model_id,
            "--thinking",
            args.reasoning_effort or "high",
        ]
        bridge_ts = ws_dir / "_pi_runtime" / "harness2_bridge.ts"
        if bridge_ts.is_file():
            cmd.extend(["-e", str(bridge_ts)])

        env = {
            **os.environ,
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "SEC_AGENT_HARNESS2_PI_HARNESS_DIR": str(ws_dir),
            "SEC_AGENT_HARNESS2_PI_PROVIDER": provider,
            "SEC_AGENT_HARNESS2_PI_ACTIVE_MODEL": model_id,
        }

        session_file = run_dir / "pi_session.jsonl"
        t0 = time.monotonic()
        with open(session_file, "w", encoding="utf-8") as sf:
            proc = subprocess.run(
                cmd,
                cwd=str(ws_dir),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=sf,
                stderr=subprocess.PIPE,
                text=True,
                timeout=args.timeout,
                check=False,
            )
        wall_s = round(time.monotonic() - t0, 2)

        for prod in (ws_dir / "output").rglob("*"):
            if prod.is_file():
                rel = prod.relative_to(ws_dir / "output")
                dest = out_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prod, dest)

        has_events = False
        total_cost = 0.0
        if session_file.is_file():
            with open(session_file, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.lstrip().startswith("{"):
                        has_events = True
                        try:
                            ev = json.loads(line)
                            if ev.get("type") == "message_end":
                                c = (
                                    ((ev.get("message") or {}).get("usage") or {})
                                    .get("cost", {})
                                    .get("total")
                                )
                                if isinstance(c, (int, float)):
                                    total_cost += float(c)
                        except Exception:
                            pass

        if has_events:
            metrics = {
                "task": args.task,
                "run_id": args.run_id,
                "model": args.model,
                "returncode": proc.returncode,
                "wall_s": wall_s,
                "cost_usd": round(total_cost, 6),
            }
            (run_dir / "metrics.json").write_text(
                json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
            )
        return 0 if has_events else 1
    finally:
        shutil.rmtree(ws_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
