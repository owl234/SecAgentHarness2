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

"""File scanner, parser, and diff extractor for Harness² runs and artifacts."""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes] + b"\n\n...[truncated]..."
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _file_mtime_iso(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def infer_run_cell(runs_root: Path, run_id: str) -> dict[str, Any]:
    """Infer (bench, subset, substrate, k, seed, has_judged) from a run_id and its on-disk directory."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    has_judged = (run_dir / "judged.json").is_file() or (run_dir / "base_judged.json").is_file()
    base_id = _SWEEP_TS_SUFFIX.sub("", run_id)

    bench: str | None = None
    subset: str | None = None
    substrate: str | None = None
    k: int = 1
    seed: int | None = None

    # Check parent path if inside runs/<bench>/adapt/<run_id>
    try:
        rel_parts = run_dir.relative_to(runs_root).parts
        if len(rel_parts) >= 2 and rel_parts[0] in ("jb", "wb", "lab"):
            bench = rel_parts[0]
    except Exception:
        pass

    # Match <bench>[-<subset>]-<substrate>-(agg|seq)<k>[-s<seed>]
    m = re.match(
        r"^(?P<bprefix>jb|lab|wb(?:-(?:office|web|code))?|demo)-(?P<sub>oc|pi)-(?P<mode>agg|seq)(?P<k>\d+)(?:-s(?P<seed>\d+))?",
        base_id,
    )
    if m:
        bprefix = m.group("bprefix")
        if bprefix.startswith("wb-"):
            bench = "wb"
            subset = bprefix.split("-", 1)[1]
        elif bprefix in ("jb", "lab", "wb"):
            bench = bprefix
        substrate = m.group("sub")
        k = int(m.group("k") or 1)
        if m.group("seed"):
            seed = int(m.group("seed"))

    return {
        "bench": bench,
        "subset": subset,
        "substrate": substrate,
        "k": k,
        "seed": seed,
        "has_judged": has_judged,
    }


def list_runs(runs_root: Path) -> list[dict[str, Any]]:
    """Scan the runs root directory and identify all runs, demos, sweeps, and adapt benchmarks."""
    if not runs_root.is_dir():
        return []

    runs: list[dict[str, Any]] = []

    # 1. Check for demo runs (directories containing demo.json)
    for p in sorted(runs_root.iterdir()):
        if p.is_dir():
            demo_json = p / "demo.json"
            if demo_json.is_file():
                meta = _safe_read_json(demo_json) or {}
                tasks = meta.get("tasks", [])
                runs.append({
                    "id": p.name,
                    "name": f"本地演示: {p.name}",
                    "type": "demo",
                    "path": str(p.relative_to(runs_root)),
                    "task_count": meta.get("n_tasks", len(tasks)),
                    "completed_count": meta.get("done", sum(1 for t in tasks if t.get("status") == "ok")),
                    "failed_count": meta.get("failed", 0),
                    "execution_count": meta.get("execution_count", 0),
                    "editor_calls": meta.get("editor_calls", 0),
                    "updated_at": _file_mtime_iso(demo_json),
                    "domain": meta.get("domain", "accounting"),
                    "modes": ["agg", "seq"],
                    "bench": "demo",
                    "k": int(meta.get("k", 2)),
                    "has_judged": False,
                })

    # 2. Check for sweeps under _sweeps (top-level or per benchmark)
    sweep_files = list(runs_root.glob("_sweeps/*.json")) + list(runs_root.glob("*/_sweeps/*.json"))
    seen_sweeps: set[str] = set()
    for sw in sorted(sweep_files, key=lambda f: f.stat().st_mtime if f.exists() else 0, reverse=True):
        if sw.name in seen_sweeps:
            continue
        seen_sweeps.add(sw.name)
        meta = _safe_read_json(sw) or {}
        domain_reps = meta.get("domains", [])
        done = sum(int(d.get("done", 0)) for d in domain_reps)
        failed = sum(int(d.get("failed", 0)) for d in domain_reps)
        total = sum(len(d.get("tasks", [])) for d in domain_reps)
        cell = infer_run_cell(runs_root, sw.stem)
        runs.append({
            "id": sw.stem,
            "name": f"扫描: {sw.stem}",
            "type": "sweep",
            "path": str(sw.relative_to(runs_root)),
            "task_count": total or (done + failed),
            "completed_count": done,
            "failed_count": failed,
            "updated_at": _file_mtime_iso(sw),
            "modes": meta.get("modes", ["agg"]),
            **cell,
        })

    # 3. Check for adapt runs (e.g. runs/<bench>/adapt/<run_id>)
    seen_run_ids: set[str] = set()
    for adapt_dir in sorted(runs_root.glob("*/adapt/*")):
        if adapt_dir.is_dir() and not adapt_dir.name.startswith((".", "_")):
            run_id = adapt_dir.name
            seen_run_ids.add(run_id)
            cfg_path = adapt_dir / "config.json"
            cfg = _safe_read_json(cfg_path) or {}
            cfg_tasks = cfg.get("tasks", [])
            total_tasks = len(cfg_tasks)
            if not total_tasks:
                task_dirs = [d for d in adapt_dir.iterdir() if d.is_dir() and "__" in d.name]
                total_tasks = len(task_dirs) or 1

            task_summaries = list(adapt_dir.glob("*/summary.json"))
            done_count = 0
            for s in task_summaries:
                s_data = _safe_read_json(s)
                if s_data and s_data.get("status") in ("ok", "skipped"):
                    done_count += 1

            bench_name = adapt_dir.parent.parent.name
            cell = infer_run_cell(runs_root, run_id)
            runs.append({
                "id": run_id,
                "name": f"{run_id} ({bench_name.upper()})",
                "type": "adapt",
                "path": str(adapt_dir.relative_to(runs_root)),
                "task_count": total_tasks,
                "completed_count": done_count,
                "failed_count": max(0, len(task_summaries) - done_count),
                "updated_at": _file_mtime_iso(cfg_path) if cfg_path.is_file() else _file_mtime_iso(adapt_dir),
                "domain": cfg.get("domains", ["general"])[0] if cfg.get("domains") else "general",
                "modes": ["agg"],
                **cell,
            })

    # 4. Check for standalone namespaces (e.g. jb-oc-agg1, or demo runs inside demo/runs)
    for p in sorted(runs_root.iterdir()):
        if p.is_dir() and not p.name.startswith(("_", ".")):
            if (p / "demo.json").is_file() or p.name in seen_run_ids or p.name in ("lab", "jb", "wb"):
                continue
            task_summaries = list(p.glob("*/summary.json"))
            if task_summaries:
                ok_count = 0
                for s in task_summaries:
                    s_data = _safe_read_json(s)
                    if s_data and s_data.get("status") in ("ok", "skipped"):
                        ok_count += 1
                cell = infer_run_cell(runs_root, p.name)
                runs.append({
                    "id": p.name,
                    "name": p.name,
                    "type": "namespace",
                    "path": str(p.relative_to(runs_root)),
                    "task_count": len(task_summaries),
                    "completed_count": ok_count,
                    "failed_count": len(task_summaries) - ok_count,
                    "updated_at": _file_mtime_iso(p),
                    "modes": ["agg"],
                    **cell,
                })

    return runs


_SWEEP_TS_SUFFIX = re.compile(r"-\d{8}T\d{6}Z$")


def _resolve_run_dir(runs_root: Path, run_id: str) -> Path:
    resolved = _resolve_run_dir_exact(runs_root, run_id)
    if resolved.is_dir():
        return resolved
    # A sweep summary id (``<run_id>-<UTC timestamp>``) maps onto the adapt run it produced.
    base_id = _SWEEP_TS_SUFFIX.sub("", run_id)
    if base_id != run_id:
        base = _resolve_run_dir_exact(runs_root, base_id)
        if base.is_dir():
            return base
    return resolved


def _resolve_run_dir_exact(runs_root: Path, run_id: str) -> Path:
    target = runs_root / run_id
    if target.is_dir():
        return target
    # check inside demo/runs if user passed demo-oc-agg1
    for demo_p in runs_root.glob("*/runs/" + run_id):
        if demo_p.is_dir():
            return demo_p
    # check inside */adapt/<run_id> (e.g. runs/lab/adapt/lab-oc-agg1)
    for adapt_p in runs_root.glob("*/adapt/" + run_id):
        if adapt_p.is_dir():
            return adapt_p
    # check inside */results/*/<run_id>
    for res_p in runs_root.glob("*/results/*/" + run_id):
        if res_p.is_dir():
            return res_p
    return target


def get_tasks_for_run(runs_root: Path, run_id: str) -> list[dict[str, Any]]:
    """List all tasks and high-level progress within a run or demo."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    if not run_dir.is_dir():
        return []

    # If run_dir is a demo directory containing demo.json and runs/
    task_map: dict[str, dict[str, Any]] = {}

    summary_paths = list(run_dir.rglob("summary.json"))
    for sp in sorted(summary_paths):
        # sp parent is task_dir, parent of task_dir is namespace
        task_dir = sp.parent
        task_id = task_dir.name.replace("__", "/")
        summary = _safe_read_json(sp) or {}

        status = summary.get("status", "unknown")
        domain = summary.get("domain", "")
        k = summary.get("k", 1)
        modes = summary.get("modes", {})
        selections = summary.get("selections", {})
        base_runs = summary.get("base", [])

        # Calculate spend & attempts
        total_usd = 0.0
        total_attempts = 0
        stages_summary = []
        for m_name, m_val in modes.items():
            if isinstance(m_val, dict):
                for stg in m_val.get("stages", []):
                    total_usd += float(stg.get("usd", 0.0))
                    total_attempts += int(stg.get("attempts", 0))
                    stages_summary.append({
                        "label": stg.get("label"),
                        "dim": stg.get("dim"),
                        "mode": m_name,
                        "usd": stg.get("usd", 0.0),
                        "attempts": stg.get("attempts", 0),
                        "notes": stg.get("notes", ""),
                        "fell_back": stg.get("fell_back", False),
                    })

        task_entry = {
            "task_id": task_id,
            "domain": domain,
            "status": status,
            "k": k,
            "run_path": str(task_dir.relative_to(runs_root)),
            "modes": list(modes.keys()),
            "base_count": len(base_runs),
            "stages_count": len(stages_summary),
            "stages": stages_summary,
            "total_usd": total_usd,
            "selections": {
                m: {
                    "chosen_label": s.get("chosen_label"),
                    "chosen_is_base": s.get("chosen_is_base"),
                    "why": s.get("why"),
                    "has_experience": bool(s.get("experience")),
                }
                for m, s in selections.items()
            },
            "updated_at": _file_mtime_iso(sp),
        }
        task_map[task_id] = task_entry

    # In-progress detection for adapt runs:
    cfg_tasks = []
    cfg_path = run_dir / "config.json"
    if cfg_path.is_file():
        cfg = _safe_read_json(cfg_path) or {}
        cfg_tasks = cfg.get("tasks", [])

    candidate_task_dirs = [d for d in run_dir.iterdir() if d.is_dir() and "__" in d.name]
    candidate_task_ids: dict[str, Path] = {d.name.replace("__", "/"): d for d in candidate_task_dirs}
    for item in cfg_tasks:
        if isinstance(item, list) and len(item) == 2:
            candidate_task_ids.setdefault(item[1], run_dir / item[1].replace("/", "__"))
        elif isinstance(item, str):
            candidate_task_ids.setdefault(item, run_dir / item.replace("/", "__"))

    for task_id, t_dir in candidate_task_ids.items():
        if task_id in task_map:
            continue

        domain = task_id.split("/")[0] if "/" in task_id else ""
        res_dirs = list(runs_root.glob(f"*/results/*/{run_id}/{task_id}"))
        res_dir = res_dirs[0] if res_dirs else None

        stages_summary = []
        base_count = 0
        if res_dir and res_dir.is_dir():
            for sub in sorted(res_dir.iterdir()):
                if sub.is_dir():
                    s_name = sub.name
                    is_complete = (sub / ".adapt_complete").is_file() or (sub / "metrics.json").is_file()
                    is_active = (sub / "opencode_session.jsonl").is_file()
                    if s_name.startswith("base"):
                        base_count += 1
                        stg_status = "completed" if is_complete else ("running" if is_active else "pending")
                        stages_summary.append({
                            "label": s_name,
                            "dim": "BASE",
                            "mode": "agg",
                            "usd": 0.0,
                            "attempts": 1,
                            "notes": f"初始基线采样 ({stg_status})",
                            "fell_back": False,
                        })
                    elif s_name.startswith("inv") or s_name.startswith("dom"):
                        dim = "INV" if s_name.startswith("inv") else "DOM"
                        stg_status = "completed" if is_complete else ("running" if is_active else "pending")
                        stages_summary.append({
                            "label": s_name,
                            "dim": dim,
                            "mode": "agg",
                            "usd": 0.0,
                            "attempts": 1,
                            "notes": f"候选提议探测 {dim} ({stg_status})",
                            "fell_back": False,
                        })
                    elif s_name.startswith("agg"):
                        stg_status = "completed" if is_complete else ("running" if is_active else "pending")
                        stages_summary.append({
                            "label": s_name,
                            "dim": "COMPOSE",
                            "mode": "agg",
                            "usd": 0.0,
                            "attempts": 1,
                            "notes": f"融合终选运行 ({stg_status})",
                            "fell_back": False,
                        })

        task_entry = {
            "task_id": task_id,
            "domain": domain,
            "status": "in_progress",
            "k": 1,
            "run_path": str(t_dir.relative_to(runs_root)) if t_dir.exists() else str(run_dir.relative_to(runs_root)),
            "modes": ["agg"],
            "base_count": base_count,
            "stages_count": len(stages_summary),
            "stages": stages_summary,
            "total_usd": 0.0,
            "selections": {},
            "updated_at": _file_mtime_iso(res_dir) if res_dir and res_dir.exists() else _file_mtime_iso(run_dir),
        }
        task_map[task_id] = task_entry

    return list(task_map.values())


def get_task_detail(runs_root: Path, run_id: str, task_id: str) -> dict[str, Any] | None:
    """Retrieve full execution detail, pipeline tree, deliverables, and harness paths for a task."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    if not run_dir.is_dir():
        return None

    # locate the task directory (preferring directories with summary.json)
    safe_task_id = task_id.replace("/", "__")
    candidates = [d for d in run_dir.rglob(safe_task_id) if d.is_dir()]
    with_summary = [d for d in candidates if (d / "summary.json").is_file()]
    matched_dirs = with_summary if with_summary else candidates
    if not matched_dirs:
        for d in run_dir.rglob("*"):
            if d.is_dir() and d.name == safe_task_id:
                matched_dirs.append(d)

    if not matched_dirs:
        return None

    task_dir = matched_dirs[0]
    summary_path = task_dir / "summary.json"
    summary = _safe_read_json(summary_path) or {}

    # Extract stages, rollouts, harnesses
    harnesses_dir = task_dir / "harnesses"
    available_harnesses = []
    if harnesses_dir.is_dir():
        available_harnesses = sorted([p.name for p in harnesses_dir.iterdir() if p.is_dir()])

    # Look for execution artifacts: answer.txt, trajectory.md, deliverable docs
    rollout_artifacts: dict[str, dict[str, str]] = {}

    # Check for results directory across runs_root
    real_task_id = task_id.replace("__", "/")
    res_dirs = list(runs_root.glob(f"*/results/*/{run_id}/{real_task_id}"))
    if not res_dirs:
        res_dirs = list(runs_root.glob(f"*/results/*/{run_id}/{task_id}"))
    if not res_dirs:
        res_dirs = list(runs_root.glob(f"*/results/*/{run_id}/{safe_task_id}"))
    if res_dirs:
        for r_sub in res_dirs[0].iterdir():
            if r_sub.is_dir():
                rollout_artifacts[r_sub.name] = _read_run_artifacts(r_sub)

    modes_data = summary.get("modes", {})
    selections_data = summary.get("selections", {})

    for base_obj in summary.get("base", []):
        lbl = base_obj.get("label", "base1")
        r_dir = Path(base_obj.get("run_dir", ""))
        if lbl not in rollout_artifacts and r_dir.is_dir():
            rollout_artifacts[lbl] = _read_run_artifacts(r_dir)

    for m_name, sel in selections_data.items():
        r_dir = Path(sel.get("chosen_run_dir", ""))
        chosen_lbl = sel.get("chosen_label", "")
        if chosen_lbl and r_dir.is_dir() and chosen_lbl not in rollout_artifacts:
            rollout_artifacts[chosen_lbl] = _read_run_artifacts(r_dir)

    # Collect all stages info
    stages_info: dict[str, Any] = {}
    for m_name, m_val in modes_data.items():
        if isinstance(m_val, dict):
            for stg in m_val.get("stages", []):
                lbl = stg.get("label")
                if lbl:
                    stages_info[lbl] = dict(stg)
                    stages_info[lbl]["mode"] = m_name

    # If in-flight and stages_info is empty, populate from harnesses and rollout_artifacts
    if not stages_info:
        labels = set(available_harnesses) | set(rollout_artifacts.keys())
        for raw_lbl in sorted(labels):
            lbl = f"{raw_lbl}1" if raw_lbl in ("base", "inv", "dom", "agg") else raw_lbl
            if lbl.startswith("base"):
                stages_info[lbl] = {"label": lbl, "dim": "BASE", "mode": "agg", "usd": 0.0, "attempts": 1}
            elif lbl.startswith("inv"):
                stages_info[lbl] = {"label": lbl, "dim": "INV", "mode": "agg", "usd": 0.0, "attempts": 1}
            elif lbl.startswith("dom"):
                stages_info[lbl] = {"label": lbl, "dim": "DOM", "mode": "agg", "usd": 0.0, "attempts": 1}
            elif lbl.startswith("agg"):
                stages_info[lbl] = {"label": lbl, "dim": "COMPOSE", "mode": "agg", "usd": 0.0, "attempts": 1}

    # Look for run config
    run_config = _safe_read_json(task_dir.parent / "config.json") or {}

    # Build Pipeline DAG Structure for visual rendering with full blueprint & live status
    pipeline_graph = _build_pipeline_graph(
        summary, stages_info, rollout_artifacts, run_config=run_config, run_id=run_id
    )

    # Reflections & Experiences
    reflection_dir = task_dir / "reflection"
    reflection_data = {}
    if reflection_dir.is_dir():
        for item in reflection_dir.iterdir():
            if item.is_file():
                reflection_data[item.name] = _safe_read_text(item, max_bytes=200_000)
            elif item.is_dir() and (item / "adoption.json").is_file():
                adoption = _safe_read_json(item / "adoption.json")
                edits = _safe_read_text(item / "edits.md")
                reflection_data[item.name] = {
                    "adoption": adoption,
                    "edits": edits,
                }

    domain_val = summary.get("domain", "") or (task_id.split("/")[0] if "/" in task_id else "")
    status_val = summary.get("status", "") or ("in_progress" if not summary_path.is_file() else "unknown")

    return {
        "task_id": task_id,
        "domain": domain_val,
        "status": status_val,
        "k": summary.get("k", 1),
        "summary": summary,
        "available_harnesses": available_harnesses,
        "stages": stages_info,
        "rollouts": rollout_artifacts,
        "selections": selections_data,
        "pipeline_graph": pipeline_graph,
        "reflection": reflection_data,
    }


def _read_run_artifacts(r_dir: Path) -> dict[str, str]:
    if not r_dir.is_dir():
        return {}
    out: dict[str, str] = {}
    for f in r_dir.iterdir():
        if f.is_file():
            out[f.name] = _safe_read_text(f, max_bytes=200_000)
    out_dir = r_dir / "output"
    if out_dir.is_dir():
        for f in out_dir.iterdir():
            if f.is_file():
                out[f"output/{f.name}"] = _safe_read_text(f, max_bytes=200_000)
                if f.name.endswith(".md") or f.name.endswith(".txt"):
                    out["answer.txt"] = _safe_read_text(f, max_bytes=200_000)
                elif f.name.endswith(".docx"):
                    out.setdefault("answer.txt", f"已生成交付文档: output/{f.name} ({f.stat().st_size} 字节)")
    if (r_dir / "transcript.jsonl").is_file() and "trajectory.md" not in out:
        out["trajectory.md"] = f"完整会话记录文件: {r_dir / 'transcript.jsonl'}"
    return out


def _build_pipeline_graph(
    summary: dict[str, Any],
    stages_info: dict[str, Any],
    rollout_artifacts: dict[str, dict[str, str]],
    run_config: dict[str, Any] | None = None,
    run_id: str = "",
) -> dict[str, Any]:
    """Construct nodes and edges for DAG visualization with full blueprint & live statuses."""
    nodes = []
    edges = []
    run_config = run_config or {}

    # Extract k
    k = summary.get("k") or run_config.get("k") or 1
    if k == 1 and run_id:
        km = re.search(r"(?:agg|seq)(\d+)", run_id)
        if km:
            try:
                k = int(km.group(1))
            except ValueError:
                pass

    # Extract mode keys
    modes = summary.get("modes", {})
    selections = summary.get("selections", {})
    if modes:
        mode_keys = list(modes.keys())
    else:
        cfg_modes = run_config.get("mode") or []
        if any("seq" in m for m in cfg_modes) or "-seq" in run_id:
            mode_keys = ["seq"]
        else:
            mode_keys = ["agg"]

    # 1. Base Nodes
    base_labels = [b.get("label", f"base{i}") for i, b in enumerate(summary.get("base", []), 1)]
    if not base_labels:
        base_keys = sorted([k_name for k_name in stages_info.keys() if k_name.startswith("base")])
        base_labels = base_keys if base_keys else [f"base{i}" for i in range(1, k + 1)]

    base_nodes = []
    for b_lbl in base_labels:
        b_arts = rollout_artifacts.get(b_lbl, {})
        b_comp = bool(b_arts.get(".adapt_complete") or b_arts.get("metrics.json"))
        b_act = bool(b_arts.get("opencode_session.jsonl"))
        b_status = "completed" if b_comp else ("running" if (b_act or not rollout_artifacts) else "pending")
        b_num = "".join(filter(str.isdigit, b_lbl)) or "1"
        b_node = {
            "id": b_lbl,
            "label": f"初始基准-{b_num} ({b_lbl})",
            "type": "base",
            "status": b_status,
            "dim": "BASE",
            "deliverable": b_arts.get("answer.txt", ""),
            "has_trajectory": bool(b_arts.get("trajectory.md")),
        }
        base_nodes.append(b_node)
        nodes.append(b_node)

    all_bases_done = all(b["status"] == "completed" for b in base_nodes)

    # 2. Stage Nodes per Mode
    for mode in mode_keys:
        chosen_lbl = selections.get(mode, {}).get("chosen_label")

        if mode == "agg":
            branch_nodes = []
            m_stages = {stg.get("label"): stg for stg in (modes.get("agg", {}).get("stages") or []) if stg.get("label")}

            for r in range(1, k + 1):
                inv_lbl = f"inv{r}"
                dom_lbl = f"dom{r}"
                agg_lbl = f"agg{r}"

                inv_arts = rollout_artifacts.get(inv_lbl, {})
                inv_comp = bool(inv_arts.get(".adapt_complete") or inv_arts.get("metrics.json"))
                inv_act = bool(inv_arts.get("opencode_session.jsonl"))

                dom_arts = rollout_artifacts.get(dom_lbl, {})
                dom_comp = bool(dom_arts.get(".adapt_complete") or dom_arts.get("metrics.json"))
                dom_act = bool(dom_arts.get("opencode_session.jsonl"))

                agg_arts = rollout_artifacts.get(agg_lbl, {})
                agg_comp = bool(agg_arts.get(".adapt_complete") or agg_arts.get("metrics.json"))
                agg_act = bool(agg_arts.get("opencode_session.jsonl"))

                # Invariant candidate node
                inv_stg = m_stages.get(inv_lbl, {})
                if inv_stg:
                    inv_status = "failed" if inv_stg.get("fell_back") else "completed"
                elif inv_comp:
                    inv_status = "completed"
                elif inv_act or (all_bases_done and not agg_comp and not inv_comp):
                    inv_status = "running"
                else:
                    inv_status = "pending"

                nodes.append({
                    "id": inv_lbl,
                    "label": f"通用工程-{r} ({inv_lbl})",
                    "type": "candidate",
                    "dim": "INV",
                    "mode": "agg",
                    "status": inv_status,
                    "fell_back": inv_stg.get("fell_back", False),
                    "kept_base": inv_stg.get("kept_base", False),
                    "notes": inv_stg.get("notes", ""),
                    "error": inv_stg.get("error", ""),
                    "usd": inv_stg.get("usd", 0.0),
                    "attempts": inv_stg.get("attempts", 1),
                    "deliverable": inv_arts.get("answer.txt", ""),
                    "has_trajectory": bool(inv_arts.get("trajectory.md")),
                    "is_chosen": (inv_lbl == chosen_lbl),
                })
                edges.append({"source": base_labels[0], "target": inv_lbl, "label": "提议通用工程改进"})
                branch_nodes.append(inv_lbl)

                # Domain candidate node
                dom_stg = m_stages.get(dom_lbl, {})
                if dom_stg:
                    dom_status = "failed" if dom_stg.get("fell_back") else "completed"
                elif dom_comp:
                    dom_status = "completed"
                elif dom_act or (all_bases_done and not agg_comp and not dom_comp):
                    dom_status = "running"
                else:
                    dom_status = "pending"

                nodes.append({
                    "id": dom_lbl,
                    "label": f"业务领域-{r} ({dom_lbl})",
                    "type": "candidate",
                    "dim": "DOM",
                    "mode": "agg",
                    "status": dom_status,
                    "fell_back": dom_stg.get("fell_back", False),
                    "kept_base": dom_stg.get("kept_base", False),
                    "notes": dom_stg.get("notes", ""),
                    "error": dom_stg.get("error", ""),
                    "usd": dom_stg.get("usd", 0.0),
                    "attempts": dom_stg.get("attempts", 1),
                    "deliverable": dom_arts.get("answer.txt", ""),
                    "has_trajectory": bool(dom_arts.get("trajectory.md")),
                    "is_chosen": (dom_lbl == chosen_lbl),
                })
                edges.append({"source": base_labels[0], "target": dom_lbl, "label": "提议业务领域改进"})
                branch_nodes.append(dom_lbl)

                # Composed node
                agg_stg = m_stages.get(agg_lbl, {})
                if agg_stg:
                    agg_status = "failed" if agg_stg.get("fell_back") else "completed"
                elif agg_comp:
                    agg_status = "completed"
                elif agg_act or (inv_comp and dom_comp and not agg_comp):
                    agg_status = "running"
                else:
                    agg_status = "pending"

                nodes.append({
                    "id": agg_lbl,
                    "label": f"并行融合-{r} ({agg_lbl})",
                    "type": "composed",
                    "dim": "COMPOSE",
                    "mode": "agg",
                    "status": agg_status,
                    "fell_back": agg_stg.get("fell_back", False),
                    "kept_base": agg_stg.get("kept_base", False),
                    "notes": agg_stg.get("notes", ""),
                    "error": agg_stg.get("error", ""),
                    "usd": agg_stg.get("usd", 0.0),
                    "attempts": agg_stg.get("attempts", 1),
                    "deliverable": agg_arts.get("answer.txt", ""),
                    "has_trajectory": bool(agg_arts.get("trajectory.md")),
                    "is_chosen": (agg_lbl == chosen_lbl),
                })
                for branch in [inv_lbl, dom_lbl]:
                    edges.append({"source": branch, "target": agg_lbl, "label": "多路融合合成"})

        elif mode == "seq":
            prev_node = base_labels[0] if base_labels else None
            seq_mode_data = modes.get("seq", {})
            m_stages = seq_mode_data.get("stages", [])
            finals = seq_mode_data.get("finals", [])

            if m_stages:
                # Render exact stages recorded in sequential mode
                for stg in m_stages:
                    lbl = stg.get("label", "")
                    dim = stg.get("dim", "STEP")
                    r_arts = rollout_artifacts.get(lbl, {})
                    num = "".join(filter(str.isdigit, lbl)) or "1"
                    if lbl.startswith("inv"):
                        lbl_friendly = f"通用工程-{num} ({lbl})"
                    elif lbl.startswith("dom"):
                        lbl_friendly = f"业务领域-{num} ({lbl})"
                    elif lbl.startswith("c") or lbl.startswith("seq"):
                        lbl_friendly = f"序列精炼-{num} ({lbl})"
                    elif lbl.startswith("base"):
                        lbl_friendly = f"初始基准-{num} ({lbl})"
                    else:
                        lbl_friendly = f"{lbl} [{dim}]"

                    nodes.append({
                        "id": lbl,
                        "label": lbl_friendly,
                        "type": "sequential",
                        "dim": dim,
                        "mode": "seq",
                        "status": "failed" if stg.get("fell_back") else "completed",
                        "fell_back": stg.get("fell_back", False),
                        "kept_base": stg.get("kept_base", False),
                        "notes": stg.get("notes", ""),
                        "error": stg.get("error", ""),
                        "usd": stg.get("usd", 0.0),
                        "attempts": stg.get("attempts", 1),
                        "deliverable": r_arts.get("answer.txt", ""),
                        "has_trajectory": bool(r_arts.get("trajectory.md")),
                        "is_chosen": (lbl == chosen_lbl),
                    })
                    if prev_node:
                        edges.append({"source": prev_node, "target": lbl, "label": dim})
                    prev_node = lbl

                # Append final composite node (e.g., c1)
                for f_lbl in finals:
                    if any(n["id"] == f_lbl and n.get("mode") == "seq" for n in nodes):
                        continue
                    r_arts = rollout_artifacts.get(f_lbl, {})
                    c_num = "".join(filter(str.isdigit, f_lbl)) or "1"
                    f_title = f"序列精炼-{c_num} ({f_lbl})" if (f_lbl.startswith("c") or f_lbl.startswith("seq")) else f"{f_lbl} [终选]"
                    nodes.append({
                        "id": f_lbl,
                        "label": f_title,
                        "type": "sequential",
                        "dim": "COMPOSE",
                        "mode": "seq",
                        "status": "completed",
                        "fell_back": False,
                        "kept_base": False,
                        "notes": "",
                        "error": "",
                        "usd": 0.0,
                        "attempts": 1,
                        "deliverable": r_arts.get("answer.txt", ""),
                        "has_trajectory": bool(r_arts.get("trajectory.md")),
                        "is_chosen": (f_lbl == chosen_lbl),
                    })
                    if prev_node:
                        edges.append({"source": prev_node, "target": f_lbl, "label": "序列融合合成"})
                    prev_node = f_lbl

            else:
                # In-flight fallback skeleton
                for r in range(1, k + 1):
                    seq_lbl = f"seq{r}"
                    seq_arts = rollout_artifacts.get(seq_lbl, {})
                    seq_comp = bool(seq_arts.get(".adapt_complete") or seq_arts.get("metrics.json"))
                    seq_act = bool(seq_arts.get("opencode_session.jsonl"))

                    if seq_comp:
                        seq_status = "completed"
                    elif seq_act or (all_bases_done and not seq_comp):
                        seq_status = "running"
                    else:
                        seq_status = "pending"

                    nodes.append({
                        "id": seq_lbl,
                        "label": f"序列步进-{r} ({seq_lbl})",
                        "type": "sequential",
                        "dim": "SEQ",
                        "mode": "seq",
                        "status": seq_status,
                        "fell_back": False,
                        "kept_base": False,
                        "notes": "",
                        "error": "",
                        "usd": 0.0,
                        "attempts": 1,
                        "deliverable": seq_arts.get("answer.txt", ""),
                        "has_trajectory": bool(seq_arts.get("trajectory.md")),
                        "is_chosen": (seq_lbl == chosen_lbl),
                    })
                    if prev_node:
                        edges.append({"source": prev_node, "target": seq_lbl, "label": f"第 {r} 步"})
                    prev_node = seq_lbl

    return {"nodes": nodes, "edges": edges}


def _map_rel_path_to_category(path_str: str) -> str:
    norm = path_str.replace("\\", "/")
    if norm in ("systemprompt.md", "AGENTS.md"):
        return "c1"
    if norm == "guardrails.md" or norm.startswith("guardrails/"):
        return "c2"
    if norm == "LongTermMEMORY.md" or norm.startswith("memory/"):
        return "c3"
    if norm.startswith("tool_descriptions") or norm.startswith("tool_guidance"):
        return "c4"
    if norm.startswith("sub_agents"):
        return "c5"
    if norm.startswith(("skills", ".agents/skills", ".pi/skills")):
        return "c6"
    if norm.startswith("scripts"):
        return "c7"
    if norm.startswith(("plugin", ".pi/extensions")) or norm == ".pi/hooks.json":
        return "c8"
    if norm.startswith("mcp") or norm == ".mcp.json":
        return "c9"
    return ""


_PLACEHOLDER_READMES = frozenset({
    "scripts/README.md",
    "skills/README.md",
    "plugin/README.md",
    "plugins/README.md",
    "mcp/README.md",
    "sub_agents/README.md",
})


def _collect_category_files(raw_files: dict[str, str]) -> dict[str, dict[str, str]]:
    grouped: dict[str, dict[str, str]] = {f"c{i}": {} for i in range(1, 10)}
    for rel_path, content in sorted(raw_files.items()):
        norm = rel_path.replace("\\", "/")
        if norm in _PLACEHOLDER_READMES:
            continue
        cat = _map_rel_path_to_category(norm)
        if cat in grouped:
            grouped[cat][norm] = content
    return grouped


def get_harness_components(runs_root: Path, run_id: str, task_id: str, label: str) -> dict[str, Any]:
    """Retrieve all component files for a given harness label (base, inv1, agg1, etc.)."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    safe_task_id = task_id.replace("/", "__")
    matched_dirs = list(run_dir.rglob(safe_task_id))
    matched_dirs = [d for d in matched_dirs if (d / "harnesses" / label).is_dir()]
    if not matched_dirs:
        return {}

    task_dir = matched_dirs[0]
    target_harness = task_dir / "harnesses" / label

    components: dict[str, Any] = {
        "run_id": run_id,
        "task_id": task_id,
        "label": label,
        "systemprompt": "",
        "guardrails": "",
        "memory": "",
        "tool_guidance": "",
        "scripts": {},
        "skills": {},
        "subagents": {},
        "plugins": {},
        "mcp": {},
        "raw_files": {},
        "by_category": {},
    }

    # standard always-on
    components["systemprompt"] = _safe_read_text(target_harness / "systemprompt.md")
    components["guardrails"] = _safe_read_text(target_harness / "guardrails.md")
    components["memory"] = _safe_read_text(target_harness / "LongTermMEMORY.md")
    components["tool_guidance"] = _safe_read_text(target_harness / "tool_descriptions" / "tool_guidance.md")

    # scripts
    scripts_dir = target_harness / "scripts"
    if scripts_dir.is_dir():
        for sf in scripts_dir.iterdir():
            if sf.is_file():
                components["scripts"][sf.name] = _safe_read_text(sf)

    # skills
    skills_dir = target_harness / "skills"
    if skills_dir.is_dir():
        for sk in skills_dir.iterdir():
            if sk.is_dir():
                components["skills"][sk.name] = {
                    f.name: _safe_read_text(f) for f in sk.iterdir() if f.is_file()
                }

    # subagents
    subagents_dir = target_harness / "sub_agents"
    if subagents_dir.is_dir():
        for sa in subagents_dir.iterdir():
            if sa.is_dir():
                components["subagents"][sa.name] = {
                    f.name: _safe_read_text(f) for f in sa.iterdir() if f.is_file()
                }
            elif sa.is_file() and sa.name != "README.md":
                components["subagents"][sa.name] = _safe_read_text(sa)

    # plugins
    for pdir_name in ("plugins", "plugin"):
        pdir = target_harness / pdir_name
        if pdir.is_dir():
            for pf in pdir.iterdir():
                if pf.is_file() and pf.name != "README.md":
                    components["plugins"][pf.name] = _safe_read_text(pf)

    # mcp
    mcp_dir = target_harness / "mcp"
    if mcp_dir.is_dir():
        for mf in mcp_dir.iterdir():
            if mf.is_file():
                components["mcp"][mf.name] = _safe_read_text(mf)

    # all files flat map
    for f in target_harness.rglob("*"):
        if f.is_file():
            rel_name = str(f.relative_to(target_harness)).replace("\\", "/")
            components["raw_files"][rel_name] = _safe_read_text(f)

    # Compare against base harness if available
    base_raw_files: dict[str, str] = {}
    base_harness = task_dir / "harnesses" / "base"
    if label != "base" and base_harness.is_dir():
        for bf in base_harness.rglob("*"):
            if bf.is_file():
                rel_name = str(bf.relative_to(base_harness)).replace("\\", "/")
                base_raw_files[rel_name] = _safe_read_text(bf)
    else:
        base_raw_files = dict(components["raw_files"])

    cat_files_map = _collect_category_files(components["raw_files"])
    base_cat_files_map = _collect_category_files(base_raw_files)

    default_paths = {
        "c1": "systemprompt.md",
        "c2": "guardrails.md",
        "c3": "LongTermMEMORY.md",
        "c4": "tool_descriptions/tool_guidance.md",
        "c5": "sub_agents/auditor/AGENT.md",
        "c6": "skills/domain_sop/SKILL.md",
        "c7": "scripts/helper.py",
        "c8": "plugins/hook.ts",
        "c9": "mcp/servers.json",
    }

    for cat_code in (f"c{i}" for i in range(1, 10)):
        c_files = cat_files_map.get(cat_code, {})
        b_files = base_cat_files_map.get(cat_code, {})
        non_empty_files = {k: v for k, v in c_files.items() if v.strip()}
        primary_path = next(iter(non_empty_files.keys()), next(iter(c_files.keys()), default_paths[cat_code]))
        primary_content = c_files.get(primary_path, "")
        base_primary_content = b_files.get(primary_path, next(iter(b_files.values()), ""))
        char_count = sum(len(v) for v in c_files.values())
        diff_from_base = (label != "base") and (c_files != b_files)
        components["by_category"][cat_code] = {
            "category": cat_code,
            "exists": bool(non_empty_files),
            "file_count": len(non_empty_files),
            "char_count": char_count,
            "primary_path": primary_path,
            "primary_content": primary_content,
            "base_primary_content": base_primary_content,
            "files": c_files,
            "base_files": b_files,
            "diff_from_base": diff_from_base,
        }

    return components


def get_harness_diff(
    runs_root: Path, run_id: str, task_id: str, base_label: str = "base", compare_label: str = "agg1"
) -> dict[str, Any]:
    """Compute file-level unified diffs between two harness states with intent summaries."""
    c_base = get_harness_components(runs_root, run_id, task_id, base_label)
    c_comp = get_harness_components(runs_root, run_id, task_id, compare_label)

    base_files = c_base.get("raw_files", {})
    comp_files = c_comp.get("raw_files", {})

    all_keys = sorted(set(base_files.keys()) | set(comp_files.keys()))
    diffs = []

    components_summary = {
        "systemprompt": {"status": "unchanged", "label": "系统提示词", "changes": 0},
        "guardrails": {"status": "unchanged", "label": "安全护栏", "changes": 0},
        "memory": {"status": "unchanged", "label": "长期记忆", "changes": 0},
        "tools": {"status": "unchanged", "label": "工具指引", "changes": 0},
        "scripts": {"status": "unchanged", "label": "辅助脚本", "changes": 0},
        "skills": {"status": "unchanged", "label": "专业技能", "changes": 0},
        "subagents": {"status": "unchanged", "label": "子智能体", "changes": 0},
        "plugins": {"status": "unchanged", "label": "中间件插件", "changes": 0},
        "mcp": {"status": "unchanged", "label": "MCP 协议服务", "changes": 0},
    }

    def _map_comp(path_str: str) -> str:
        if path_str in ("systemprompt.md", "AGENTS.md"):
            return "systemprompt"
        if path_str == "guardrails.md":
            return "guardrails"
        if path_str == "LongTermMEMORY.md":
            return "memory"
        if path_str.startswith("tool_descriptions"):
            return "tools"
        if path_str.startswith("scripts"):
            return "scripts"
        if path_str.startswith(("skills", ".agents/skills", ".pi/skills")):
            return "skills"
        if path_str.startswith("sub_agents"):
            return "subagents"
        if path_str.startswith(("plugin", ".pi/extensions")) or path_str == ".pi/hooks.json":
            return "plugins"
        if path_str.startswith("mcp") or path_str == ".mcp.json":
            return "mcp"
        return ""

    for k in all_keys:
        old_txt = base_files.get(k, "")
        new_txt = comp_files.get(k, "")
        if old_txt == new_txt:
            continue

        status = "modified"
        if not old_txt and new_txt:
            status = "added"
        elif old_txt and not new_txt:
            status = "removed"

        old_lines = old_txt.splitlines(keepends=True)
        new_lines = new_txt.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{k}",
                tofile=f"b/{k}",
                n=3,
            )
        )

        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        comp_key = _map_comp(k)
        if comp_key in components_summary:
            components_summary[comp_key]["status"] = status
            components_summary[comp_key]["changes"] += additions + deletions

        diffs.append({
            "path": k,
            "component": comp_key,
            "status": status,
            "additions": additions,
            "deletions": deletions,
            "diff_text": "".join(diff_lines),
            "old_content": old_txt,
            "new_content": new_txt,
        })

    # Extract intent from summary.json if available
    run_dir = _resolve_run_dir(runs_root, run_id)
    safe_task_id = task_id.replace("/", "__")
    matched_dirs = list(run_dir.rglob(safe_task_id))
    intent_summary: list[str] = []

    if matched_dirs:
        summary_file = matched_dirs[0] / "summary.json"
        summary_data = _safe_read_json(summary_file) or {}

        # 1. Notes from the matching stage
        stage_notes = ""
        for m_val in summary_data.get("modes", {}).values():
            if isinstance(m_val, dict):
                for stg in m_val.get("stages", []):
                    if stg.get("label") == compare_label:
                        stage_notes = stg.get("notes", "").strip()
                        break
            if stage_notes:
                break
        if stage_notes:
            intent_summary.append(f"提议意图：{stage_notes}")

        # 2. Selection rationale if comparing against or within chosen
        for s_val in summary_data.get("selections", {}).values():
            if isinstance(s_val, dict) and s_val.get("chosen_label") == compare_label:
                why = s_val.get("why", "").strip()
                if why:
                    intent_summary.append(f"采纳原因：{why}")
                exp = s_val.get("experience", {})
                if exp.get("lesson"):
                    intent_summary.append(f"经验总结：{exp.get('lesson')}")

    # Fallback / synthetic bullet points if empty
    if not intent_summary:
        if not diffs:
            intent_summary.append("两阶段套件完全一致，未发生组件修改。")
        else:
            for d in diffs:
                c_name = components_summary.get(d.get("component", ""), {}).get("label", d["path"])
                act = "新增" if d["status"] == "added" else ("删除" if d["status"] == "removed" else "优化调整")
                intent_summary.append(f"{act}了{c_name}（{d['path']}），变动 {d['additions'] + d['deletions']} 行代码。")

    return {
        "task_id": task_id,
        "base_label": base_label,
        "compare_label": compare_label,
        "has_changes": len(diffs) > 0,
        "total_files_changed": len(diffs),
        "total_additions": sum(d["additions"] for d in diffs),
        "total_deletions": sum(d["deletions"] for d in diffs),
        "intent_summary": intent_summary,
        "components_summary": components_summary,
        "files": diffs,
    }


def get_preflight_status(workspace_root: Path) -> dict[str, Any]:
    """Inspect environment prerequisites for user guidance and preflight checks."""
    sync_config_from_env()
    from .. import api, config

    docker_bin = shutil.which("docker")
    docker_available = False
    docker_msg = "未安装 Docker 命令行工具"
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "info"], capture_output=True, timeout=5)
            if res.returncode == 0:
                docker_available = True
                docker_msg = "Docker 守护进程运行正常（支持 WorkBuddy-Bench）"
            else:
                docker_msg = "Docker 已安装但守护进程未启动（启动 Docker 即可运行 WorkBuddy-Bench）"
        except Exception:
            docker_msg = "Docker 检查超时或失败"

    project = config.VERTEX_PROJECT
    solver_model = config.SOLVER_MODEL_OC or config.SOLVER_MODEL_PI
    judge_model = config.JUDGE_MODEL
    ep_oc = api.opencode()
    ep_pi = api.pi()
    has_unified = bool(config.API_BASE_URL and config.API_KEY)
    has_any_endpoint = bool(
        has_unified
        or (ep_oc and ep_oc.api_key)
        or (ep_pi and ep_pi.api_key)
        or os.environ.get("OPENAI_API_KEY")
    )

    has_credentials = bool(project or has_any_endpoint)
    if has_unified:
        cred_msg = (
            f"统一 API 已就绪 ({config.API_BASE_URL} · "
            f"Model: {config.API_MODEL or solver_model or '按基座指定'})"
        )
    elif has_credentials:
        cred_msg = (
            f"已就绪 (Endpoint/Project: {project or (ep_pi.base_url if ep_pi else (ep_oc.base_url if ep_oc else '已配置'))}, "
            f"Model: {solver_model or '已设置'})"
        )
    else:
        cred_msg = "未配置大模型凭据（免 API 的本地 Demo 模式完全可用，可即时体验）"

    deps = workspace_root / "dependencies"
    jb_ready = (deps / "job-bench-eval" / "dataset" / "main").is_dir()
    lab_ready = (deps / "harvey-labs" / "tasks").is_dir()
    wb_ready = (deps / "workbuddy-bench" / "datasets").is_dir()

    pandoc_ok = bool(shutil.which("pandoc"))
    pdftoppm_ok = bool(shutil.which("pdftoppm"))
    node_ok = bool(shutil.which("node"))

    return {
        "status": "ready" if has_credentials else "demo_ready",
        "has_credentials": has_credentials,
        "credentials": {
            "project": project or "",
            "solver_model": solver_model or "",
            "judge_model": judge_model or "",
            "message": cred_msg,
        },
        "docker": {
            "available": docker_available,
            "message": docker_msg,
        },
        "benchmarks": {
            "demo": {
                "available": True,
                "label": "本地离线 Demo",
                "status": "ready",
                "message": "开箱即用，免 API 凭据，内置确定性任务",
            },
            "jb": {
                "available": jb_ready and has_credentials,
                "label": "JobBench (jb)",
                "status": "ready" if (jb_ready and has_credentials) else ("need_credentials" if jb_ready else "not_installed"),
                "message": "已就绪" if (jb_ready and has_credentials) else ("需配置统一 API 或 .env 模型凭据" if jb_ready else "需运行 harness2-setup jb"),
            },
            "lab": {
                "available": lab_ready and has_credentials and pandoc_ok,
                "label": "LAB (lab)",
                "status": "ready" if (lab_ready and has_credentials and pandoc_ok) else ("need_credentials" if (lab_ready and pandoc_ok) else "not_installed"),
                "message": "已就绪" if (lab_ready and has_credentials and pandoc_ok) else ("需配置统一 API 或 .env 模型凭据" if (lab_ready and pandoc_ok) else "需运行 harness2-setup lab (依赖 Pandoc/Poppler)"),
            },
            "wb": {
                "available": wb_ready and docker_available and has_credentials,
                "label": "WorkBuddy-Bench (wb)",
                "status": "ready" if (wb_ready and docker_available and has_credentials) else ("need_credentials" if (wb_ready and docker_available) else "not_installed"),
                "message": "已就绪" if (wb_ready and docker_available and has_credentials) else ("需配置模型凭据" if (wb_ready and docker_available) else "需运行 harness2-setup wb 并启动 Docker"),
            },
        },
        "tools": {
            "pandoc": pandoc_ok,
            "poppler": pdftoppm_ok,
            "node": node_ok,
        },
    }


def get_library_index(runs_root: Path, run_id: str) -> list[dict[str, Any]]:
    """Extract cumulative continual learning experiences from the library directory."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    lib_roots = list(run_dir.rglob("library"))
    if not lib_roots:
        lib_cand = run_dir.parent.parent / "library"
        if lib_cand.is_dir():
            lib_roots = [lib_cand]
        else:
            lib_roots = list(runs_root.glob("*/library"))
    if not lib_roots:
        return []

    entries: list[dict[str, Any]] = []

    for lr in lib_roots:
        # Search for EXPERIENCE.md
        exp_files = list(lr.rglob("EXPERIENCE.md"))
        for ef in sorted(exp_files):
            task_name = ef.parent.name
            domain_name = ef.parent.parent.parent.name if len(ef.parents) >= 3 else "default"
            content = _safe_read_text(ef)

            cue_m = re.search(r"^\s*-\s*\*{0,2}cue\*{0,2}:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
            lesson_m = re.search(r"^\s*-\s*\*{0,2}lesson\*{0,2}:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
            conf_m = re.search(r"^\s*-\s*\*{0,2}confidence\*{0,2}:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)

            cue = cue_m.group(1).strip() if cue_m else ""
            lesson = lesson_m.group(1).strip() if lesson_m else ""
            conf = conf_m.group(1).strip() if conf_m else ""

            # Deduplicate by task_id and cue
            if not any(e["task_id"] == task_name and e["cue"] == cue for e in entries):
                entries.append({
                    "task_id": task_name,
                    "domain": domain_name,
                    "path": str(ef.relative_to(runs_root)),
                    "raw_text": content,
                    "cue": cue,
                    "lesson": lesson,
                    "confidence": conf,
                })

    return entries


def get_benchmark_report(runs_root: Path, run_id: str) -> dict[str, Any]:
    """Load judged.json and base_judged.json if present, calculating metrics."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    judged_path = run_dir / "judged.json"
    base_judged_path = run_dir / "base_judged.json"

    judged_rows = _safe_read_json(judged_path) or []
    base_rows = _safe_read_json(base_judged_path) or []

    # Calculate summary metrics
    if not isinstance(judged_rows, list):
        judged_rows = []
    if not isinstance(base_rows, list):
        base_rows = []

    def _calc_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
        graded = [r for r in rows if r.get("n_criteria", 0) > 0]
        n_graded = len(graded)
        if not n_graded:
            return {"count": len(rows), "graded": 0, "avg_score": 0.0, "all_pass_rate": 0.0}

        avg_score = (
            sum(float(r.get("n_passed", 0)) / float(r.get("n_criteria", 1)) for r in graded)
            / n_graded
            * 100.0
        )
        all_pass_count = sum(1 for r in graded if r.get("all_pass"))
        return {
            "count": len(rows),
            "graded": n_graded,
            "avg_score": round(avg_score, 2),
            "all_pass_rate": round(all_pass_count / n_graded * 100.0, 2),
            "all_pass_count": all_pass_count,
        }

    return {
        "run_id": run_id,
        "has_judged": bool(judged_rows),
        "has_base_judged": bool(base_rows),
        "adapted_stats": _calc_stats(judged_rows),
        "base_stats": _calc_stats(base_rows),
        "judged_rows": judged_rows,
        "base_rows": base_rows,
    }


# =====================================================================
# Preset Component Templates & Custom Component Manager (c1..c8)
# =====================================================================

PRESET_COMPONENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tpl_c1_autonomous_engineer",
        "category": "c1",
        "type": "c1_prompt",
        "name": "autonomous_engineer_prompt",
        "label": "自主专家工程师系统提示词",
        "path": "systemprompt.md",
        "description": "设定高鲁棒性自主编码与故障排查专家设定，规范第一性原理推演与自检公理。",
        "tags": ["c1", "系统提示词", "工程规范", "第一性原理"],
        "content": (
            "# 专家自主执行智能体\n\n"
            "你是一个具备高级问题解决与递归优化能力的自主智能体。\n"
            "在执行任何代码分析、测试编写或系统修改前，请务必遵守以下操作公理：\n\n"
            "## 1. 核心工作哲学\n"
            "- **第一性原理溯源**：切忌主观臆测与黑盒试错。优先阅读源代码、抽象语法树 (AST) 与底层配置，查明故障本原机制。\n"
            "- **环境不变性保证**：执行修改前先验证当前基准测试；修改后必须执行全量回归验证，确保无意外负向回归。\n"
            "- **原子化增量提交**：每个改动必须保持单一职责，并附带针对性的检验断言。\n\n"
            "## 2. 行为准则\n"
            "- 每次开始任务时，必须先列举候选方案并自评估潜在边界破坏风险。\n"
            "- 输出内容保持工程化高密度，去除无价值的套话与寒暄。\n"
        ),
    },
    {
        "id": "tpl_c2_production_guard",
        "category": "c2",
        "type": "c2_guardrail",
        "name": "production_safety_guard",
        "label": "生产环境安全护栏与危险命令拦截",
        "path": "guardrails.md",
        "description": "防御性安全屏障，禁止非授权破坏性文件删除、未受控提权以及敏感凭据泄漏。",
        "tags": ["c2", "安全护栏", "安全防御", "合规审查"],
        "content": (
            "# 操作安全护栏与边界拦截规范\n\n"
            "在执行任意系统调用、文件操作及外部网络请求时，强制遵守以下红线：\n\n"
            "## 1. 禁止执行的危险操作\n"
            "- **严禁破坏性删除**：禁止执行 `rm -rf /`、清空根目录或删除未受管控的父级工作区。\n"
            "- **严禁硬编码敏感凭据**：任何私钥、API Key、Session Token 严禁明文写入文件或日志。\n"
            "- **严禁非受限网络外连**：不得向非授信第三方域名发送内部数据包。\n\n"
            "## 2. 文件变更校验\n"
            "- 每次写文件操作必须限制在当前任务约定的 Staging 目录或工作空间内。\n"
            "- 关键配置文件修改必须保留带时间戳的 `.bak` 备份文件。\n"
        ),
    },
    {
        "id": "tpl_c3_incremental_ledger",
        "category": "c3",
        "type": "c3_memory",
        "name": "incremental_task_ledger",
        "label": "跨阶段长效运行记忆账本",
        "path": "LongTermMEMORY.md",
        "description": "记录跨轮次提炼的关键坑点、库版本兼容性备忘与高频有效策略，避免重复犯错。",
        "tags": ["c3", "长期记忆", "经验复用", "增量账本"],
        "content": (
            "# 跨阶段长效运行记忆账本\n\n"
            "## 已验证有效的策略模式\n"
            "1. 涉及金融会计金额计算时，始终采用 `Decimal` 或整型分计量，严禁浮点数直接累加导致舍入偏差。\n"
            "2. 涉及异步并发流处理时，优先使用有界缓冲队列并配备连接重连熔断器。\n\n"
            "## 常见踩坑与回归防范\n"
            "- 部分历史测试依赖静态测试夹具，若增删依赖库需确保与全局锁文件（如 uv.lock / package-lock.json）保持哈希一致。\n"
        ),
    },
    {
        "id": "tpl_c4_structured_json",
        "category": "c4",
        "type": "c4_tool",
        "name": "structured_tool_protocol",
        "label": "结构化工具调用协议与容错指引",
        "path": "tool_descriptions/tool_guidance.md",
        "description": "规范智能体工具调用的参数类型约束、错误处理逻辑与输出契约。",
        "tags": ["c4", "工具指引", "协议规范", "接口契约"],
        "content": (
            "# 工具调用协议与异常重试指引\n\n"
            "## 参数调用约定\n"
            "- **严格类型校验**：传递给计算工具的数值参数必须与文档声明的类型一致（禁止传递字符串形式的浮点数）。\n"
            "- **幂等性保障**：外部 API 调用必须传递唯一 `idempotency_key`，避免网络超时重试导致重复提交。\n\n"
            "## 异常响应解析\n"
            "- 当工具返回状态码非 200 时，必须首先打印详细返回报文并检查必填字段缺失，而非盲目重新发送相同载荷。\n"
        ),
    },
    {
        "id": "tpl_c5_arch_reviewer",
        "category": "c5",
        "type": "c5_subagent",
        "name": "arch_reviewer",
        "label": "架构审查与代码重构专员",
        "path": "sub_agents/arch_reviewer/AGENT.md",
        "description": "专用于在主智能体合成后进行独立 AST 语法扫描与设计模式合规性审查的委托代理。",
        "tags": ["c5", "子智能体", "代码审查", "架构设计"],
        "content": (
            "---\n"
            "name: arch_reviewer\n"
            "description: 专门负责代码结构合理性审查与设计模式合规检测的轻量级审查员子智能体。\n"
            "tools: [read_file, run_command]\n"
            "---\n\n"
            "# 架构审查子智能体\n\n"
            "你的唯一目标是协助主智能体审阅新提交或合成的代码补丁，评估其架构健壮度。\n\n"
            "## 审查维度\n"
            "1. **模块高内聚低耦合**：是否存在不合理的跨层循环引用？\n"
            "2. **错误处理完备性**：是否有裸露的 `except: pass` 或静默忽略异常？\n"
            "3. **接口扩展性**：未来新增执行器或组件时是否容易横向扩展？\n\n"
            "输出结构化审查报告，包含：\n"
            "- [P0/P1 风险项]\n"
            "- [重构建议]\n"
            "- [通过/驳回裁定]\n"
        ),
    },
    {
        "id": "tpl_c6_data_cleaner",
        "category": "c6",
        "type": "c6_skill",
        "name": "data_cleaner",
        "label": "复杂数据清洗与数值对齐技能",
        "path": "skills/data_cleaner/SKILL.md",
        "description": "提供标准数据清洗流程手册及自动化 Python 清洗脚本，包含字段归一化与校验。",
        "tags": ["c6", "专业技能", "数据清洗", "自动化流程"],
        "content": (
            "---\n"
            "name: data_cleaner\n"
            "description: 对含格式噪点的交易流水和结构化账单执行清洗、补齐与校验。\n"
            "---\n\n"
            "# 交易流水数据清洗指南\n\n"
            "当面对未知来源的 CSV / JSON / Excel 账目数据时，按此技能手册执行标准化：\n\n"
            "## 步骤流程\n"
            "1. 运行 `scripts/clean_data.py --input <path>` 执行首轮格式规范化。\n"
            "2. 检查日期字段是否符合 ISO 8601 格式 (`YYYY-MM-DD`)。\n"
            "3. 对缺失或格式畸变的金额项记录到异常告警队列，并使用默认基线策略补齐。\n"
        ),
        "extra_files": {
            "skills/data_cleaner/scripts/clean_data.py": (
                '"""Automated data cleaner utility."""\n'
                "import csv\n"
                "import sys\n"
                "from decimal import Decimal\n\n"
                "def clean_row(row):\n"
                "    cleaned = dict(row)\n"
                '    if "amount" in cleaned:\n'
                '        raw = cleaned["amount"].replace("$", "").replace(",", "").strip()\n'
                '        cleaned["amount"] = str(Decimal(raw)) if raw else "0.00"\n'
                "    return cleaned\n\n"
                'if __name__ == "__main__":\n'
                '    print("清洗工具已就绪。")\n'
            )
        },
    },
    {
        "id": "tpl_c7_validate_schema",
        "category": "c7",
        "type": "c7_script",
        "name": "validate_schema",
        "label": "JSON Schema 快速语法校验脚本",
        "path": "scripts/validate_schema.py",
        "description": "独立运行的 Python 校验脚本，验证中间产物与配置文件的完整性。",
        "tags": ["c7", "辅助脚本", "Python", "语法校验"],
        "content": (
            '"""Validate JSON payload against schema definitions."""\n'
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            "def validate(file_path: str) -> bool:\n"
            "    path = Path(file_path)\n"
            "    if not path.is_file():\n"
            '        print(f"未找到文件: {file_path}", file=sys.stderr)\n'
            "        return False\n"
            "    try:\n"
            '        data = json.loads(path.read_text(encoding="utf-8"))\n'
            '        print(f"校验通过: {path.name} 共加载 {len(data)} 个条目。")\n'
            "        return True\n"
            "    except Exception as e:\n"
            '        print(f"校验失败: {e}", file=sys.stderr)\n'
            "        return False\n\n"
            'if __name__ == "__main__":\n'
            "    if len(sys.argv) > 1:\n"
            "        validate(sys.argv[1])\n"
            "    else:\n"
            '        print("用法: python3 scripts/validate_schema.py <path>")\n'
        ),
    },
    {
        "id": "tpl_c8_execution_auditor",
        "category": "c8",
        "type": "c8_hook",
        "name": "execution_auditor",
        "label": "运行时执行审计与耗时监控钩子",
        "path": "plugins/execution_auditor.ts",
        "description": "在智能体每次工具调用前后拦截执行上下文，记录调用耗时与入参快照。",
        "tags": ["c8", "拦截钩子", "事件拦截", "性能审计"],
        "content": (
            "/**\n"
            " * 运行时执行审计与耗时监控钩子\n"
            " */\n"
            "export async function beforeToolCall(toolName: string, args: Record<string, any>) {\n"
            "  console.log(`[审计] 准备执行工具: ${toolName}`);\n"
            "  return { startTimestamp: Date.now() };\n"
            "}\n\n"
            "export async function afterToolCall(toolName: string, result: any, context: { startTimestamp: number }) {\n"
            "  const duration = Date.now() - context.startTimestamp;\n"
            "  console.log(`[审计] 工具 ${toolName} 执行完毕，耗时 ${duration}ms`);\n"
            "}\n"
        ),
    },
    {
        "id": "tpl_c9_sec_recon_mcp",
        "category": "c9",
        "type": "c9_mcp",
        "name": "sec_recon_mcp",
        "label": "网安资产测绘与协议分析 MCP 服务",
        "path": "mcp/servers.json",
        "description": "提供跨轮次有状态资产指纹缓存、CVE 规则检索与结构化协议解析的 MCP 服务配置及内置服务脚本。",
        "tags": ["c9", "MCP", "网络安全", "有状态工具", "协议服务"],
        "content": (
            "{\n"
            '  "mcpServers": {\n'
            '    "sec_recon": {\n'
            '      "command": "python3",\n'
            '      "args": ["mcp/sec_recon_mcp.py"],\n'
            '      "env": {\n'
            '        "PYTHONUNBUFFERED": "1"\n'
            "      }\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
        "extra_files": {
            "mcp/sec_recon_mcp.py": (
                '"""Lightweight stdio MCP server for stateful security asset recon & CVE indexing."""\n'
                "import json\n"
                "import sys\n\n"
                "SESSION_ASSETS: dict[str, dict] = {}\n\n"
                "TOOLS = [\n"
                "    {\n"
                '        "name": "record_asset_fingerprint",\n'
                '        "description": "Persist discovered service banner and ports in stateful session cache.",\n'
                '        "inputSchema": {\n'
                '            "type": "object",\n'
                '            "properties": {\n'
                '                "target": {"type": "string"},\n'
                '                "service": {"type": "string"},\n'
                '                "ports": {"type": "array", "items": {"type": "integer"}},\n'
                "            },\n"
                '            "required": ["target", "service"],\n'
                "        },\n"
                "    },\n"
                "    {\n"
                '        "name": "list_session_assets",\n'
                '        "description": "Return all fingerprinted targets accumulated across agent turns.",\n'
                '        "inputSchema": {"type": "object", "properties": {}},\n'
                "    },\n"
                "]\n\n"
                "def handle_request(req: dict) -> dict | None:\n"
                '    method = req.get("method", "")\n'
                '    req_id = req.get("id")\n'
                '    if method == "initialize":\n'
                "        return {\n"
                '            "jsonrpc": "2.0",\n'
                '            "id": req_id,\n'
                '            "result": {\n'
                '                "protocolVersion": "2024-11-05",\n'
                '                "capabilities": {"tools": {}},\n'
                '                "serverInfo": {"name": "sec_recon", "version": "1.0.0"},\n'
                "            },\n"
                "        }\n"
                '    if method == "tools/list":\n'
                '        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}\n'
                '    if method == "tools/call":\n'
                '        params = req.get("params") or {}\n'
                '        name = params.get("name")\n'
                '        args = params.get("arguments") or {}\n'
                '        if name == "record_asset_fingerprint":\n'
                '            target = str(args.get("target", "unknown"))\n'
                "            SESSION_ASSETS[target] = args\n"
                "            text = json.dumps({\"status\": \"recorded\", \"total\": len(SESSION_ASSETS)})\n"
                "        else:\n"
                "            text = json.dumps(SESSION_ASSETS, ensure_ascii=False)\n"
                "        return {\n"
                '            "jsonrpc": "2.0",\n'
                '            "id": req_id,\n'
                '            "result": {"content": [{"type": "text", "text": text}]},\n'
                "        }\n"
                "    return None\n\n"
                'if __name__ == "__main__":\n'
                "    for line in sys.stdin:\n"
                "        line = line.strip()\n"
                "        if not line:\n"
                "            continue\n"
                "        try:\n"
                "            resp = handle_request(json.loads(line))\n"
                "            if resp is not None:\n"
                "                sys.stdout.write(json.dumps(resp) + \"\\n\")\n"
                "                sys.stdout.flush()\n"
                "        except Exception:\n"
                "            pass\n"
            )
        },
    },
]


def get_custom_components_dir(workspace_root: Path) -> Path:
    d = workspace_root / "custom_components"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_custom_components(workspace_root: Path) -> list[dict[str, Any]]:
    """List all user-created and preset Harness components."""
    comp_dir = get_custom_components_dir(workspace_root)
    index_file = comp_dir / "components.json"
    custom_list: list[dict[str, Any]] = []

    if index_file.is_file():
        custom_list = _safe_read_json(index_file) or []

    # Map presets and custom items
    results: list[dict[str, Any]] = []

    # Add presets with preset marker
    for p in PRESET_COMPONENT_TEMPLATES:
        item = dict(p)
        item["source"] = "preset"
        item["updated_at"] = "2026-10-20T00:00:00Z"
        results.append(item)

    # Add user custom items
    for c in custom_list:
        item = dict(c)
        item["source"] = "custom"
        results.append(item)

    return results


def save_custom_component(workspace_root: Path, comp_data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a custom harness component."""
    comp_dir = get_custom_components_dir(workspace_root)
    index_file = comp_dir / "components.json"
    custom_list: list[dict[str, Any]] = []
    if index_file.is_file():
        custom_list = _safe_read_json(index_file) or []

    comp_id = comp_data.get("id") or f"custom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    category = comp_data.get("category", "c6")
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", comp_data.get("name", "custom_comp")).lower()

    # Determine default path based on category if omitted
    path = comp_data.get("path")
    if not path:
        if category == "c1":
            path = "systemprompt.md"
        elif category == "c2":
            path = "guardrails.md"
        elif category == "c3":
            path = "LongTermMEMORY.md"
        elif category == "c4":
            path = "tool_descriptions/tool_guidance.md"
        elif category == "c5":
            path = f"sub_agents/{name}/AGENT.md"
        elif category == "c6":
            path = f"skills/{name}/SKILL.md"
        elif category == "c7":
            path = f"scripts/{name}.py"
        elif category == "c8":
            path = f"plugins/{name}.ts"
        elif category == "c9":
            path = "mcp/servers.json"
        else:
            path = f"components/{name}.txt"

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "id": comp_id,
        "name": name,
        "category": category,
        "type": comp_data.get("type", f"{category}_custom"),
        "label": comp_data.get("label", name),
        "path": path,
        "description": comp_data.get("description", ""),
        "tags": comp_data.get("tags", [category, "Custom"]),
        "content": comp_data.get("content", ""),
        "extra_files": comp_data.get("extra_files", {}),
        "updated_at": now_iso,
        "source": "custom",
    }

    # Upsert
    existing_idx = next((i for i, c in enumerate(custom_list) if c.get("id") == comp_id), -1)
    if existing_idx >= 0:
        custom_list[existing_idx] = record
    else:
        custom_list.insert(0, record)

    index_file.write_text(json.dumps(custom_list, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def delete_custom_component(workspace_root: Path, comp_id: str) -> bool:
    """Delete a custom component by ID."""
    comp_dir = get_custom_components_dir(workspace_root)
    index_file = comp_dir / "components.json"
    if not index_file.is_file():
        return False
    custom_list = _safe_read_json(index_file) or []
    initial_len = len(custom_list)
    custom_list = [c for c in custom_list if c.get("id") != comp_id]
    if len(custom_list) < initial_len:
        index_file.write_text(json.dumps(custom_list, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    return False


def apply_component_to_run(
    runs_root: Path, run_id: str, task_id: str, label: str, comp_data: dict[str, Any]
) -> dict[str, Any]:
    """Inject a component directly into a specific task's harness directory."""
    run_dir = _resolve_run_dir(runs_root, run_id)
    safe_task_id = task_id.replace("/", "__")
    matched_dirs = list(run_dir.rglob(safe_task_id))
    matched_dirs = [d for d in matched_dirs if (d / "harnesses" / label).is_dir()]
    if not matched_dirs:
        raise ValueError(f"Harness destination not found for {task_id} @ {label}")

    target_harness = matched_dirs[0] / "harnesses" / label

    path = comp_data.get("path")
    if not path:
        raise ValueError("Component path is required for injection.")

    out_file = target_harness / path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(comp_data.get("content", ""), encoding="utf-8")

    # Extra files if any (e.g. scripts for skill)
    extra_files = comp_data.get("extra_files", {})
    for extra_path, content in extra_files.items():
        ep = target_harness / extra_path
        ep.parent.mkdir(parents=True, exist_ok=True)
        ep.write_text(content, encoding="utf-8")

    return {
        "status": "applied",
        "task_id": task_id,
        "label": label,
        "written_file": str(out_file.relative_to(target_harness)),
        "extra_files_written": list(extra_files.keys()),
    }


def _mask_secret(val: str) -> str:
    """Return a masked preview of a secret key without exposing raw credentials."""
    s = (val or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "****"
    return f"{s[:4]}...{s[-4:]}"


def sync_config_from_env() -> None:
    """Refresh module-level derived settings on `harness2.config` from `os.environ`."""
    from .. import config

    config.VERTEX_PROJECT = config.env(
        "GOOGLE_CLOUD_PROJECT", config.env("SEC_AGENT_HARNESS2_VERTEX_PROJECT", "")
    )
    config.VERTEX_REGION = config.env("GOOGLE_CLOUD_LOCATION", "global")
    config.API_BASE_URL = config.env("SEC_AGENT_HARNESS2_API_BASE_URL", "")
    config.API_KEY = config.env("SEC_AGENT_HARNESS2_API_KEY", "")
    config.API_MODEL = config.env("SEC_AGENT_HARNESS2_API_MODEL", "")
    config.SOLVER_MODEL_OC = config._solver_model_oc()
    config.SOLVER_MODEL_PI = config._solver_model_pi()
    config.IMPROVER_MODEL = config.env("SEC_AGENT_HARNESS2_IMPROVER_MODEL", config.SOLVER_MODEL_OC)
    config.JUDGE_MODEL = config.env("SEC_AGENT_HARNESS2_JUDGE_MODEL", config.API_MODEL)
    config.PROPOSER_MODEL_BY_CHANNEL = {
        "opencode": config.IMPROVER_MODEL,
        "pi": config.IMPROVER_MODEL,
    }
    vertex_host = (
        "aiplatform.googleapis.com"
        if config.VERTEX_REGION == "global"
        else f"{config.VERTEX_REGION}-aiplatform.googleapis.com"
    )
    config.VERTEX_OPENAI_URL = (
        f"https://{vertex_host}/v1/projects/{config.VERTEX_PROJECT}"
        f"/locations/{config.VERTEX_REGION}/endpoints/openapi"
    )
    config.JB_JUDGE_API_BASE = config.env(
        "SEC_AGENT_HARNESS2_JUDGE_BASE_URL",
        (config.VERTEX_OPENAI_URL if config.VERTEX_PROJECT else "") or config.API_BASE_URL,
    )
    config.JB_JUDGE_API_KEY = config.env(
        "SEC_AGENT_HARNESS2_JUDGE_API_KEY",
        config.API_KEY if not config.VERTEX_PROJECT else "",
    )
    config.LAB_JUDGE_MODEL = (
        "vertex/" + config.JUDGE_MODEL
        if config.JUDGE_MODEL.startswith("gemini")
        else config.JUDGE_MODEL
    )
    config.JB_JUDGE_MODEL = (
        "google/" + config.JUDGE_MODEL
        if config.JUDGE_MODEL.startswith("gemini") and not config.env("SEC_AGENT_HARNESS2_JUDGE_BASE_URL")
        else config.JUDGE_MODEL
    )


def persist_env_updates(
    workspace_root: Path,
    updates: dict[str, str | None],
    *,
    write_dotenv: bool = True,
) -> dict[str, Any]:
    """Update `os.environ`, persist changes to `.env` (preserving comments), and sync derived files."""
    from .. import api, install

    applied: dict[str, str] = {}
    for key, val in updates.items():
        if val is None:
            continue
        cleaned = str(val).strip()
        if cleaned:
            os.environ[key] = cleaned
        else:
            os.environ.pop(key, None)
        applied[key] = cleaned

    dotenv_path = workspace_root / ".env"
    example_path = workspace_root / ".env.example"
    if write_dotenv and applied:
        if dotenv_path.is_file():
            raw_text = dotenv_path.read_text(encoding="utf-8")
        elif example_path.is_file():
            raw_text = example_path.read_text(encoding="utf-8")
        else:
            raw_text = "# Harness2 environment configuration\n"

        lines = raw_text.splitlines()
        remaining = dict(applied)

        # Pass 1: Update active KEY=... lines in place
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            body = stripped[len("export ") :].lstrip() if stripped.startswith("export ") else stripped
            k, _, _ = body.partition("=")
            k = k.strip()
            if k in remaining:
                new_val = remaining.pop(k)
                lines[idx] = f"{k}={new_val}"

        # Pass 2: Replace commented template lines `# KEY=...` in place
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            m = re.match(r"^#\s*([A-Z0-9_]+)\s*=.*$", stripped)
            if m and m.group(1) in remaining:
                k = m.group(1)
                new_val = remaining.pop(k)
                if new_val:
                    lines[idx] = f"{k}={new_val}"
                else:
                    lines[idx] = f"# {k}="

        # Pass 3: Append any remaining non-empty keys
        appended = [f"{k}={v}" for k, v in remaining.items() if v]
        if appended:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(appended)

        dotenv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sync_config_from_env()

    synced_files: list[str] = []
    if write_dotenv and applied and dotenv_path.is_file():
        synced_files.append(".env")

    # Sync derived files when operating on the repository workspace:
    # Pi models.json when Pi endpoint is present
    pi_agent_dir = workspace_root / "dependencies" / "pi" / "agent"
    ep_pi = api.pi()
    if ep_pi is not None and (pi_agent_dir.is_dir() or (workspace_root / "dependencies").is_dir()):
        try:
            install.configure_pi(dry_run=False, agent_dir=pi_agent_dir)
            mf = pi_agent_dir / "models.json"
            if mf.is_file():
                try:
                    synced_files.append(str(mf.relative_to(workspace_root)))
                except ValueError:
                    synced_files.append("dependencies/pi/agent/models.json")
        except Exception:
            pass

    return {"applied_keys": list(applied.keys()), "synced_files": synced_files}


def get_bridge_status(workspace_root: Path, managed_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check whether the local Responses Bridge is running and return its connection details."""
    return {
        "running": False,
        "port": 0,
        "host": "127.0.0.1",
        "upstream": os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", ""),
        "wire_mode": "direct",
        "local_url": "",
        "container_url": "",
        "auth_enabled": False,
        "key_configured": False,
        "local_key": "",
        "local_key_masked": "",
        "managed": False,
    }


def probe_executor_endpoint(
    workspace_root: Path,
    target: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    protocol: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Test live connectivity to an API endpoint for Unified API or a specific substrate."""
    import time
    import urllib.error
    import urllib.request

    from .. import api, config

    sync_config_from_env()

    ep: api.Endpoint | None = None
    if target == "oc":
        ep = api.opencode()
        default_proto = "openai-chat"
        default_model = config.SOLVER_MODEL_OC
    elif target == "pi":
        ep = api.pi()
        default_proto = "openai-chat"
        default_model = config.SOLVER_MODEL_PI
    elif target == "vertex":
        default_proto = "openai-chat"
        default_model = config.JUDGE_MODEL or "gemini-2.5-pro"
        ep = api.Endpoint(
            base_url=config.JB_JUDGE_API_BASE,
            api_key=config.JB_JUDGE_API_KEY,
            protocol="openai-chat",
            model=default_model,
        ) if config.JB_JUDGE_API_BASE else None
    else:
        # unified
        default_proto = os.environ.get("SEC_AGENT_HARNESS2_API_PROTOCOL") or "openai-chat"
        default_model = config.API_MODEL
        ep = (
            api.Endpoint(
                base_url=config.API_BASE_URL,
                api_key=config.API_KEY,
                protocol=default_proto,
                model=default_model,
            )
            if config.API_BASE_URL
            else None
        )

    eff_url = (base_url if base_url is not None else (ep.base_url if ep else "")).strip()
    eff_key = (api_key if api_key is not None and api_key.strip() else (ep.api_key if ep else "")).strip()
    if not eff_key and target == "pi":
        eff_key = (
            os.environ.get("SEC_AGENT_HARNESS2_PI_API_KEY")
            or os.environ.get("OPENAI_API_KEY", "")
        ).strip()
    eff_proto = (protocol if protocol else (ep.protocol if ep else default_proto)).strip() or default_proto
    eff_model = (model if model else (ep.model if ep else default_model)).strip() or default_model

    if not eff_url:
        return {
            "ok": False,
            "target": target,
            "endpoint": "",
            "protocol": eff_proto,
            "status_code": None,
            "latency_ms": 0,
            "message": "未配置 API 基础地址 (Base URL)，请先填写端点地址",
        }

    t0 = time.perf_counter()
    clean_base = eff_url.rstrip("/")

    def _do_req(url: str, method: str = "GET", body: dict | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
        hdrs = {"User-Agent": "Harness2-Preflight/0.1", "Accept": "application/json"}
        if headers:
            hdrs.update(headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                return resp.status, resp.read(500).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read(500).decode("utf-8", errors="replace")
            except Exception:
                pass
            return e.code, err_body

    auth_headers: dict[str, str] = {}
    if eff_key:
        auth_headers["Authorization"] = f"Bearer {eff_key}"
        auth_headers["x-api-key"] = eff_key
    if eff_proto == "anthropic":
        auth_headers["anthropic-version"] = "2023-06-01"

    try:
        models_url = clean_base + ("/models" if clean_base.endswith("/v1") else "/v1/models")
        code, snippet = _do_req(models_url, "GET", headers=auth_headers)
        # If /models is not implemented on a proxy (404/405), fall back to protocol-specific endpoint probe
        if code in (404, 405):
            bare_model = eff_model.removeprefix("sec_agent_harness2/") if eff_model else "gpt-4o"
            if eff_proto == "anthropic":
                msg_url = clean_base + ("/messages" if clean_base.endswith("/v1") else "/v1/messages")
                code, snippet = _do_req(
                    msg_url,
                    "POST",
                    body={
                        "model": bare_model or "gpt-4o",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    headers=auth_headers,
                )
            elif eff_proto == "openai-responses":
                resp_url = clean_base + ("/responses" if clean_base.endswith("/v1") else "/v1/responses")
                code, snippet = _do_req(
                    resp_url,
                    "POST",
                    body={"model": bare_model, "input": "ping", "max_output_tokens": 16},
                    headers=auth_headers,
                )
            else:
                chat_url = clean_base + ("/chat/completions" if clean_base.endswith("/v1") else "/v1/chat/completions")
                code, snippet = _do_req(
                    chat_url,
                    "POST",
                    body={
                        "model": bare_model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    headers=auth_headers,
                )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        ok = 200 <= code < 300
        if ok:
            msg = f"端点连通正常 (HTTP {code}, {latency_ms}ms) · 协议 {eff_proto}"
        elif code in (401, 403):
            msg = f"网络可达但鉴权被拒 (HTTP {code}, {latency_ms}ms)：请检查 API Key / Auth Token"
        else:
            short = snippet.strip().replace("\n", " ")[:120]
            msg = f"端点返回异常状态 HTTP {code} ({latency_ms}ms){': ' + short if short else ''}"
        return {
            "ok": ok,
            "target": target,
            "endpoint": eff_url,
            "protocol": eff_proto,
            "status_code": code,
            "latency_ms": latency_ms,
            "message": msg,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "target": target,
            "endpoint": eff_url,
            "protocol": eff_proto,
            "status_code": None,
            "latency_ms": latency_ms,
            "message": f"无法连接到端点 {eff_url}: {type(exc).__name__}: {exc}",
        }


def fetch_endpoint_models(
    base_url: str | None = None,
    api_key: str | None = None,
    protocol: str | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """Query an API endpoint for available models via /v1/models or /models.

    Supports both OpenAI format (`data[].id`) and Anthropic format (`data[].id`).
    Returns dict:
        ok: bool
        models: list[str] (deduplicated & sorted)
        latency_ms: int
        message: str
    """
    import json
    import time
    import urllib.error
    import urllib.request

    from .. import config

    sync_config_from_env()

    eff_url = (
        base_url
        if base_url is not None and base_url.strip()
        else (config.API_BASE_URL or os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", ""))
    ).strip()

    eff_key = (
        api_key
        if api_key is not None and api_key.strip()
        else (config.API_KEY or os.environ.get("SEC_AGENT_HARNESS2_API_KEY", ""))
    ).strip()

    eff_proto = (
        protocol
        if protocol is not None and protocol.strip()
        else os.environ.get("SEC_AGENT_HARNESS2_API_PROTOCOL", "openai-chat")
    ).strip()

    if not eff_url:
        return {
            "ok": False,
            "models": [],
            "latency_ms": 0,
            "message": "未配置 API 基础地址 (Base URL)，请先填写端点地址",
        }

    clean_base = eff_url.rstrip("/")
    for suffix in ("/chat/completions", "/messages", "/responses"):
        if clean_base.endswith(suffix):
            clean_base = clean_base[: -len(suffix)]
            break

    if clean_base.endswith("/models"):
        candidate_urls = [clean_base]
    elif clean_base.endswith("/v1"):
        candidate_urls = [f"{clean_base}/models", f"{clean_base[:-3]}/models"]
    else:
        candidate_urls = [f"{clean_base}/v1/models", f"{clean_base}/models"]

    auth_headers: dict[str, str] = {
        "User-Agent": "SecAgentHarness2-ModelScanner/0.1",
        "Accept": "application/json",
    }
    if eff_key:
        auth_headers["Authorization"] = f"Bearer {eff_key}"
        auth_headers["x-api-key"] = eff_key

    if eff_proto == "anthropic" or "anthropic" in clean_base.lower():
        auth_headers["anthropic-version"] = "2023-06-01"

    t0 = time.perf_counter()
    last_err_msg = ""
    last_status_code = None

    for idx, target_url in enumerate(candidate_urls):
        req = urllib.request.Request(target_url, headers=auth_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                code = resp.status
                raw = resp.read(5 * 1024 * 1024).decode("utf-8", errors="replace")
                latency_ms = int((time.perf_counter() - t0) * 1000)

                try:
                    payload = json.loads(raw)
                except Exception as json_err:
                    return {
                        "ok": False,
                        "models": [],
                        "latency_ms": latency_ms,
                        "message": f"端点返回非合法 JSON 数据 (HTTP {code}): {json_err}",
                    }

                items = []
                if isinstance(payload, dict):
                    if isinstance(payload.get("data"), list):
                        items = payload["data"]
                    elif isinstance(payload.get("models"), list):
                        items = payload["models"]
                    elif isinstance(payload.get("model_list"), list):
                        items = payload["model_list"]
                    elif isinstance(payload.get("result"), list):
                        items = payload["result"]
                    elif isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("models"), list):
                        items = payload["data"]["models"]
                elif isinstance(payload, list):
                    items = payload

                extracted: set[str] = set()
                for item in items:
                    if isinstance(item, dict):
                        m_id = item.get("id") or item.get("name") or item.get("model")
                        if m_id and isinstance(m_id, str):
                            extracted.add(m_id.strip())
                    elif isinstance(item, str) and item.strip():
                        extracted.add(item.strip())

                models = sorted(list(extracted), key=lambda x: (x.lower(), x))

                if models:
                    return {
                        "ok": True,
                        "models": models,
                        "latency_ms": latency_ms,
                        "message": f"成功获取 {len(models)} 个可用模型 ({latency_ms}ms)",
                    }
                else:
                    return {
                        "ok": True,
                        "models": [],
                        "latency_ms": latency_ms,
                        "message": f"端点响应成功 (HTTP {code}, {latency_ms}ms)，但未包含模型列表",
                    }
        except urllib.error.HTTPError as e:
            last_status_code = e.code
            err_body = ""
            try:
                err_body = e.read(500).decode("utf-8", errors="replace")
            except Exception:
                pass

            if e.code in (400, 404, 405) and idx + 1 < len(candidate_urls):
                continue

            latency_ms = int((time.perf_counter() - t0) * 1000)
            if e.code in (401, 403):
                msg = f"网络可达但鉴权被拒 (HTTP {e.code}, {latency_ms}ms): 请检查 API Key 是否有效"
            elif e.code in (404, 405):
                msg = f"端点未提供 /models 模型枚举接口 (HTTP {e.code}, {latency_ms}ms)，您仍可手动在输入框中直接输入模型名称。"
            else:
                short = err_body.strip().replace("\n", " ")[:120]
                msg = f"端点返回状态 HTTP {e.code} ({latency_ms}ms){': ' + short if short else ''}"
            return {
                "ok": False,
                "models": [],
                "latency_ms": latency_ms,
                "message": msg,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "ok": False,
                "models": [],
                "latency_ms": latency_ms,
                "message": f"连接端点失败: {type(exc).__name__}: {exc}",
            }

    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "ok": False,
        "models": [],
        "latency_ms": latency_ms,
        "message": last_err_msg or f"未能获取模型 (HTTP {last_status_code or 'unknown'})",
    }


def _safe_rel(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def get_executors_status(
    workspace_root: Path, managed_bridge: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Inspect and return detailed ground-truth status of Unified API and all supported executors."""
    sync_config_from_env()
    from .. import api, config

    # 0. Unified API & Bridge inspection
    unified_base_url = os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", "")
    unified_key = os.environ.get("SEC_AGENT_HARNESS2_API_KEY", "")
    unified_model = (
        os.environ.get("SEC_AGENT_HARNESS2_API_MODEL", "")
        or config.API_MODEL
        or (config.SOLVER_MODEL_OC.removeprefix("sec_agent_harness2/") if config.SOLVER_MODEL_OC else "")
    )
    unified_protocol = os.environ.get("SEC_AGENT_HARNESS2_API_PROTOCOL", "")
    bridge_info = get_bridge_status(workspace_root, managed_bridge)

    # 1. OpenCode (oc) Substrate inspection
    opencode_dir = workspace_root / "dependencies" / "opencode"
    oc_entry = opencode_dir / "packages" / "cli" / "src" / "index.ts"
    bun_bin_path = config.BUN if config.BUN.is_file() else Path(shutil.which("bun") or "")
    bun_ok = bool(bun_bin_path and bun_bin_path.is_file())
    oc_cli_ok = oc_entry.is_file() and bun_ok
    ep_oc = api.opencode()
    vertex_project = config.VERTEX_PROJECT
    vertex_region = config.VERTEX_REGION
    oc_has_key = bool((ep_oc and ep_oc.api_key) or vertex_project or os.environ.get("OPENAI_API_KEY"))
    oc_model = config.SOLVER_MODEL_OC
    oc_model_override = os.environ.get("SEC_AGENT_HARNESS2_SOLVER_MODEL", "")
    oc_base_override = os.environ.get("SEC_AGENT_HARNESS2_OPENCODE_BASE_URL", "")
    oc_proto_override = os.environ.get("SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL", "")
    oc_effective_proto = ep_oc.protocol if ep_oc else (oc_proto_override or "openai-chat")
    oc_using_unified = bool(unified_base_url and not oc_base_override)

    if oc_cli_ok and oc_has_key and oc_model:
        oc_status = "ready"
        oc_msg = (
            f"OpenCode 源码与 Bun 已就绪 · 模型 {oc_model} · "
            f"{'复用统一 API (provider: harness2)' if oc_using_unified else (ep_oc.base_url if ep_oc else f'Vertex AI ({vertex_project})')}"
        )
    elif not oc_cli_ok:
        oc_status = "missing_deps"
        oc_msg = "未完成 dependencies/opencode 与 Bun 初始化（请运行 harness2 setup <bench>）"
    else:
        oc_status = "needs_config"
        oc_msg = "OpenCode 运行时已就绪，需配置统一 API 或 SEC_AGENT_HARNESS2_SOLVER_MODEL"

    # 2. Pi Coding Agent (pi) Substrate inspection
    from ..substrate.pi import find_pi_binary

    pi_bin_path = find_pi_binary()
    pi_cli_ok = pi_bin_path.is_file() and os.access(pi_bin_path, os.X_OK)
    pi_bin = str(pi_bin_path) if pi_cli_ok else ""
    ep_pi = api.pi()
    pi_raw_key = os.environ.get("SEC_AGENT_HARNESS2_PI_API_KEY", "")
    pi_has_key = bool((ep_pi and ep_pi.api_key) or pi_raw_key or os.environ.get("OPENAI_API_KEY"))
    pi_model = config.SOLVER_MODEL_PI
    pi_model_override = os.environ.get("SEC_AGENT_HARNESS2_PI_MODEL", "")
    pi_effort = os.environ.get("SEC_AGENT_HARNESS2_PI_EFFORT", "high") or "high"
    pi_base_override = os.environ.get("SEC_AGENT_HARNESS2_PI_BASE_URL", "")
    pi_proto_override = os.environ.get("SEC_AGENT_HARNESS2_PI_PROTOCOL", "")
    pi_effective_proto = ep_pi.protocol if ep_pi else (pi_proto_override or "openai-chat")
    pi_using_unified = bool(unified_base_url and not pi_base_override)

    if pi_cli_ok and pi_has_key:
        pi_status = "ready"
        pi_msg = (
            f"Pi Coding Agent {config.PI_VERSION} 已就绪 · 协议 {pi_effective_proto} · "
            f"{'复用统一 API' if pi_using_unified else (ep_pi.base_url if ep_pi else '默认端点')}"
        )
    elif not pi_cli_ok:
        pi_status = "missing_deps"
        pi_msg = (
            f"未安装 Pi Coding Agent CLI 运行时 ({_safe_rel(config.PI_BIN, workspace_root)})；"
            "请运行 harness2 setup <bench> --substrate pi"
        )
    else:
        pi_status = "needs_config"
        pi_msg = "Pi CLI 已就绪，待配置统一 API (SEC_AGENT_HARNESS2_API_*) 或 SEC_AGENT_HARNESS2_PI_*"

    # 3. Improver, Judge & Vertex AI inspection
    improver_override = os.environ.get("SEC_AGENT_HARNESS2_IMPROVER_MODEL", "")
    judge_model = config.JUDGE_MODEL
    judge_base_override = os.environ.get("SEC_AGENT_HARNESS2_JUDGE_BASE_URL", "")
    judge_key_raw = os.environ.get("SEC_AGENT_HARNESS2_JUDGE_API_KEY", "")
    vertex_ready = bool(vertex_project or (judge_model and judge_base_override) or unified_base_url)
    vertex_status = "ready" if vertex_ready else "needs_config"
    if vertex_project:
        vertex_msg = f"GCP Project: {vertex_project} ({vertex_region}) · 改进器: {config.IMPROVER_MODEL or '未指定'} · 裁判: {judge_model or '未指定'}"
    elif judge_base_override or unified_base_url:
        vertex_msg = f"使用自定义/统一 API 驱动改进器与裁判 · 改进器: {config.IMPROVER_MODEL or '未指定'} · 裁判: {judge_model or '未指定'}"
    else:
        vertex_msg = "未设置 GOOGLE_CLOUD_PROJECT 或独立裁判端点 (SEC_AGENT_HARNESS2_JUDGE_*)"

    return {
        "active_executor": os.environ.get(
            "SEC_AGENT_HARNESS2_DEFAULT_EXECUTOR",
            "pi" if (pi_cli_ok and pi_has_key) else "oc",
        ),
        "unified_config": {
            "base_url": unified_base_url,
            "api_key_configured": bool(unified_key.strip()),
            "api_key_masked": _mask_secret(unified_key),
            "model": unified_model,
            "protocol": unified_protocol,
            "improver_model": improver_override,
            "effective_improver_model": config.IMPROVER_MODEL,
            "judge_model": judge_model,
            "judge_base_url": judge_base_override,
            "judge_api_key_configured": bool(judge_key_raw.strip()),
            "judge_api_key_masked": _mask_secret(judge_key_raw),
            "vertex_project": vertex_project,
            "vertex_location": vertex_region,
        },
        "bridge": bridge_info,
        "executors": [
            {
                "id": "oc",
                "name": "OpenCode (oc)",
                "title": f"OpenCode 原生执行基座 (v{config.WB_OC_HARNESS_VER})",
                "category": "substrate",
                "status": oc_status,
                "status_message": oc_msg,
                "cli_available": oc_cli_ok,
                "cli_path": str(bun_bin_path) if bun_ok else "",
                "api_key_configured": oc_has_key,
                "api_key_masked": _mask_secret(os.environ.get("SEC_AGENT_HARNESS2_OPENCODE_API_KEY") or (ep_oc.api_key if ep_oc else "")),
                "current_model": oc_model,
                "model_override": oc_model_override,
                "base_url": oc_base_override,
                "effective_base_url": ep_oc.base_url if ep_oc else (f"google-vertex ({vertex_project})" if vertex_project else ""),
                "protocol": oc_effective_proto,
                "protocol_override": oc_proto_override,
                "using_unified": oc_using_unified,
                "resolved_endpoint": api.describe(ep_oc),
                "supported_models": [
                    "google-vertex/gemini-2.5-pro",
                    "google-vertex/gemini-2.5-flash",
                    "openai/gpt-4o",
                ],
                "capabilities": [
                    "三种安装模式 (workspace_agents_md / home_dir_jinja / workspace_config)",
                    "自动注入 OPENCODE_CONFIG_CONTENT 统一 API Provider 块",
                    "原生支持 TypeScript 插件 (plugin/*.ts) 与子智能体",
                ],
            },
            {
                "id": "pi",
                "name": "Pi Coding Agent (pi)",
                "title": f"Pi Coding Agent 执行基座 (@earendil-works/pi-coding-agent@{config.PI_VERSION})",
                "category": "substrate",
                "status": pi_status,
                "status_message": pi_msg,
                "cli_available": pi_cli_ok,
                "cli_path": pi_bin,
                "api_key_configured": pi_has_key,
                "api_key_masked": _mask_secret(pi_raw_key or (ep_pi.api_key if ep_pi else "")),
                "current_model": pi_model,
                "model_override": pi_model_override,
                "effort": pi_effort,
                "base_url": pi_base_override,
                "effective_base_url": ep_pi.base_url if ep_pi else "",
                "protocol": pi_effective_proto,
                "protocol_override": pi_proto_override,
                "using_unified": pi_using_unified,
                "resolved_endpoint": api.describe(ep_pi),
                "supported_models": [
                    "gpt-5.4",
                    "gpt-4o",
                    "gemini-2.5-pro",
                ],
                "capabilities": [
                    "零膨胀极简基线与进程内 TS 扩展 (.pi/extensions/*.ts)",
                    "双轨兼容 .pi/hooks.json 声明式钩子与 .pi/skills 技能表面",
                    "原生支持 openai-completions, openai-responses, anthropic-messages 多协议",
                    "运行时 -e 扩展桥接零污染支持子智能体 (c5) 与 MCP (c9)",
                ],
            },
            {
                "id": "vertex",
                "name": "改进器与裁判",
                "title": "提议改进器、双盲裁判与 Vertex AI 配置",
                "category": "cloud",
                "status": vertex_status,
                "status_message": vertex_msg,
                "cli_available": bool(shutil.which("gcloud")),
                "cli_path": shutil.which("gcloud") or "",
                "api_key_configured": vertex_ready,
                "api_key_masked": _mask_secret(judge_key_raw),
                "current_model": judge_model or config.IMPROVER_MODEL or "gemini-2.5-pro",
                "improver_model": improver_override,
                "effective_improver_model": config.IMPROVER_MODEL,
                "judge_model": judge_model,
                "judge_base_url": judge_base_override,
                "effective_judge_base_url": config.JB_JUDGE_API_BASE,
                "vertex_project": vertex_project,
                "vertex_location": vertex_region,
                "supported_models": [
                    "gemini-2.5-pro",
                    "gemini-2.5-flash",
                    "gpt-4o",
                ],
                "capabilities": [
                    "Proposer / Selector 演进通道模型独立配置 (SEC_AGENT_HARNESS2_IMPROVER_MODEL)",
                    "支持外部 OpenAI 兼容裁判端点 (SEC_AGENT_HARNESS2_JUDGE_BASE_URL / API_KEY)",
                    "支持 Google Cloud Vertex AI ADC 统一认证",
                ],
            },
        ],
    }

