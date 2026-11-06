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

"""FastAPI server providing REST APIs, SSE event streams, and static SPA serving."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import api
from . import scanner
from .runner import ExecutionManager


class ComponentCreateRequest(BaseModel):
    id: str | None = None
    name: str = Field(..., description="Component unique name")
    category: str = Field(..., description="c1..c8")
    label: str = Field(..., description="Human-readable title")
    description: str = Field(default="", description="Detailed summary")
    path: str | None = Field(default=None, description="Relative destination file path")
    content: str = Field(default="", description="Main file body")
    extra_files: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ComponentApplyRequest(BaseModel):
    run_id: str
    task_id: str
    label: str = Field(default="agg1")
    component: ComponentCreateRequest


class ExecutorConfigRequest(BaseModel):
    executor_id: str
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    protocol: str | None = None
    effort: str | None = None
    container_url: str | None = None
    improver_model: str | None = None
    judge_model: str | None = None
    judge_base_url: str | None = None
    judge_api_key: str | None = None
    vertex_project: str | None = None
    vertex_location: str | None = None
    persist_dotenv: bool = True
    # Legacy compatibility fields
    thinking_budget: int | None = None
    cli_path: str | None = None
    endpoint: str | None = None


class ExecutorProbeRequest(BaseModel):
    target: str = Field(default="unified", description="unified | claude | oc | cx | vertex")
    base_url: str | None = None
    api_key: str | None = None
    protocol: str | None = None
    model: str | None = None


class ExecutorModelsRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    protocol: str | None = None


class BridgeControlRequest(BaseModel):
    upstream: str | None = None
    api_key: str | None = None
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=0)
    auto_bind_codex: bool = Field(default=True)


class BridgeReprobeRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None


class DemoLaunchRequest(BaseModel):
    output: str = Field(default="runs/demo", description="Output directory 输出目录")
    k: int = Field(default=2, ge=1, description="Budget scale k 递归预算")
    mode: str = Field(default="both", description="parallel | sequential | both 递归模式")


class SweepLaunchRequest(BaseModel):
    bench: str = Field(default="jb", description="jb | wb | lab 基准")
    subset: str | None = Field(default=None, description="office | web | code (仅 wb 必填)")
    substrate: str = Field(default="oc", description="oc | cx | claude | pi 执行基座")
    k: int = Field(default=1, ge=1)
    modes: str = Field(default="parallel,sequential")
    split: str = Field(default="all")
    workers: int = Field(default=1, ge=1)
    max_tasks: int | None = Field(default=None)
    only_domains: str | None = Field(default=None)
    seed: int | None = Field(default=None)
    dry_run: bool = Field(default=False)
    model: str | None = Field(default=None)
    effort: str | None = Field(default=None)
    claude_model: str | None = Field(default=None)
    claude_thinking_budget: int | None = Field(default=None)
    claude_api_key: str | None = Field(default=None)


class JudgeLaunchRequest(BaseModel):
    run_id: str | None = Field(default=None, description="Optional run_id to infer bench/substrate/k")
    bench: str | None = Field(default=None, description="jb | wb | lab 基准")
    subset: str | None = Field(default=None, description="office | web | code (仅 wb 必填)")
    substrate: str | None = Field(default=None, description="oc | cx | claude | pi 执行基座")
    k: int | None = Field(default=None, ge=1)
    modes: str = Field(default="parallel,sequential")
    seed: int | None = Field(default=None)
    bases: bool = Field(default=False, description="是否对基线 base 进行打分 (base_judged.json)")


def create_app(workspace_root: Path, runs_root: Path | None = None) -> FastAPI:
    if runs_root is None:
        runs_root = workspace_root / "runs"

    app = FastAPI(
        title="Harness² 可视化控制台",
        description="交互式可视化控制台与提议–探测–组合递归流水线探索器",
        version="0.1.0",
    )

    # CORS support for Vite dev server (e.g. localhost:5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    runner = ExecutionManager(workspace_root)

    # -----------------------------
    # Execution & System APIs
    # -----------------------------
    @app.get("/api/status")
    async def get_system_status():
        return {
            "status": runner.get_status(),
            "workspace_root": str(workspace_root),
            "runs_root": str(runs_root),
        }

    @app.get("/api/preflight")
    async def get_preflight():
        return scanner.get_preflight_status(workspace_root)

    @app.get("/api/logs")
    async def get_logs(limit: int = 500):
        return {"logs": runner.get_logs(limit)}

    @app.get("/api/events")
    async def event_stream():
        async def _generator():
            async for item in runner.subscribe():
                event_name = item.get("event", "message")
                data_str = json.dumps(item.get("data", {}))
                yield f"event: {event_name}\ndata: {data_str}\n\n"

        return StreamingResponse(
            _generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/execute/demo")
    async def launch_demo(req: DemoLaunchRequest):
        args = [
            "-m",
            "sec_agent_harness2.cli.demo",
            "--output",
            req.output,
            "--k",
            str(req.k),
            "--mode",
            req.mode,
        ]
        job = await runner.start_job("demo", args)
        return {"status": "started", "job": job}

    @app.post("/api/execute/sweep")
    async def launch_sweep(req: SweepLaunchRequest):
        substrate_val = req.substrate
        modes_val = "parallel,sequential" if req.modes == "both" else req.modes
        args = [
            "-m",
            "sec_agent_harness2.cli.run_sweep",
            "--bench",
            req.bench,
            "--substrate",
            substrate_val,
            "--k",
            str(req.k),
            "--modes",
            modes_val,
            "--split",
            req.split,
            "--workers",
            str(req.workers),
        ]
        if req.bench == "wb":
            args.extend(["--subset", req.subset or "office"])
        elif req.subset:
            args.extend(["--subset", req.subset])
        if req.max_tasks is not None:
            args.extend(["--max-tasks", str(req.max_tasks)])
        if req.only_domains and req.only_domains.strip():
            args.extend(["--only-domains", req.only_domains.strip()])
        if req.seed is not None:
            args.extend(["--seed", str(req.seed)])
        if req.dry_run:
            args.append("--dry-run")

        extra_env: dict[str, str] = {}
        eff_model = (req.model or req.claude_model or "").strip()
        if req.claude_api_key:
            extra_env["ANTHROPIC_API_KEY"] = req.claude_api_key
        if eff_model:
            if substrate_val == "claude":
                extra_env["SEC_AGENT_HARNESS2_CLAUDE_MODEL"] = eff_model
            elif substrate_val == "oc":
                extra_env["SEC_AGENT_HARNESS2_SOLVER_MODEL"] = eff_model
            elif substrate_val == "cx":
                extra_env["SEC_AGENT_HARNESS2_CODEX_MODEL"] = eff_model
            elif substrate_val == "pi":
                extra_env["SEC_AGENT_HARNESS2_PI_MODEL"] = eff_model
        if req.effort:
            if substrate_val == "pi":
                extra_env["SEC_AGENT_HARNESS2_PI_EFFORT"] = req.effort
            else:
                extra_env["SEC_AGENT_HARNESS2_CLAUDE_EFFORT"] = req.effort
        if substrate_val in ("claude", "pi"):
            extra_env["SEC_AGENT_HARNESS2_DEFAULT_EXECUTOR"] = substrate_val

        job = await runner.start_job("sweep", args, extra_env=extra_env)
        return {"status": "started", "job": job}

    @app.post("/api/execute/judge")
    async def launch_judge(req: JudgeLaunchRequest):
        bench = req.bench
        subset = req.subset
        substrate = req.substrate
        k = req.k
        seed = req.seed

        if req.run_id:
            inferred = scanner.infer_run_cell(runs_root, req.run_id)
            if inferred.get("bench") == "demo" or req.run_id.startswith("demo"):
                raise HTTPException(
                    status_code=400,
                    detail="本地离线 Demo 采用确定性验证闭环，无需调用外部 Judge 模型打分；仅 jb/wb/lab 基准运行支持 Judge 评测判分。",
                )
            bench = bench or inferred.get("bench")
            subset = subset or inferred.get("subset")
            substrate = substrate or inferred.get("substrate")
            k = k or inferred.get("k") or 1
            if seed is None:
                seed = inferred.get("seed")

        if not bench or bench not in ("jb", "wb", "lab"):
            raise HTTPException(
                status_code=400,
                detail="无法确定目标评测基准 (jb | wb | lab)，请显式选择基准或选定有效的基准 Run。",
            )
        substrate_val = substrate or "oc"
        k_val = k or 1
        modes_val = "parallel,sequential" if req.modes == "both" else req.modes

        args = [
            "-m",
            "sec_agent_harness2.cli.judge",
            "--bench",
            bench,
            "--substrate",
            substrate_val,
            "--k",
            str(k_val),
            "--modes",
            modes_val,
        ]
        if bench == "wb":
            args.extend(["--subset", subset or "office"])
        elif subset:
            args.extend(["--subset", subset])
        if seed is not None:
            args.extend(["--seed", str(seed)])
        if req.bases:
            args.append("--bases")

        job = await runner.start_job("judge", args)
        return {"status": "started", "job": job}

    @app.post("/api/execute/stop")
    async def stop_execution():
        res = await runner.stop_job()
        return res

    # -----------------------------
    # Harness Component Studio APIs (c1..c8)
    # -----------------------------
    @app.get("/api/components")
    async def list_components():
        components = scanner.list_custom_components(workspace_root)
        return {"components": components}

    @app.get("/api/components/templates")
    async def get_component_templates():
        return {"templates": scanner.PRESET_COMPONENT_TEMPLATES}

    @app.post("/api/components")
    async def create_or_update_component(req: ComponentCreateRequest):
        try:
            saved = scanner.save_custom_component(workspace_root, req.model_dump())
            return {"status": "success", "component": saved}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/components/{comp_id}")
    async def delete_component(comp_id: str):
        ok = scanner.delete_custom_component(workspace_root, comp_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"未找到组件 {comp_id}")
        return {"status": "deleted", "id": comp_id}

    @app.post("/api/components/apply")
    async def apply_component(req: ComponentApplyRequest):
        try:
            result = scanner.apply_component_to_run(
                runs_root=runs_root,
                run_id=req.run_id,
                task_id=req.task_id,
                label=req.label,
                comp_data=req.component.model_dump(),
            )
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"装配组件失败: {exc}")

    # -----------------------------
    # Executor & Engine Management APIs (Unified API, Claude, OpenCode, Codex, Vertex)
    # -----------------------------
    @app.get("/api/executors")
    async def get_executors():
        return scanner.get_executors_status(workspace_root, runner.get_bridge_info())

    @app.post("/api/executors/config")
    async def update_executor_config(req: ExecutorConfigRequest):
        updates: dict[str, str | None] = {}
        eff_base = req.base_url if req.base_url is not None else req.endpoint

        if req.executor_id == "unified":
            if eff_base is not None:
                updates["SEC_AGENT_HARNESS2_API_BASE_URL"] = eff_base.strip()
            if req.api_key:
                updates["SEC_AGENT_HARNESS2_API_KEY"] = req.api_key.strip()
            if req.model is not None:
                cleaned_model = req.model.strip()
                bare_model = (
                    cleaned_model[len("sec_agent_harness2/") :]
                    if cleaned_model.startswith("sec_agent_harness2/")
                    else cleaned_model
                )
                updates["SEC_AGENT_HARNESS2_API_MODEL"] = bare_model
                # Automatically synchronize and align API_MODEL across all substrates
                oc_effective_base = eff_base or os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", "")
                oc_model = (
                    f"sec_agent_harness2/{bare_model}"
                    if (bare_model and oc_effective_base)
                    else bare_model
                )
                updates["SEC_AGENT_HARNESS2_SOLVER_MODEL"] = oc_model
                updates["SEC_AGENT_HARNESS2_CODEX_MODEL"] = bare_model
                updates["SEC_AGENT_HARNESS2_CLAUDE_MODEL"] = bare_model
                updates["SEC_AGENT_HARNESS2_PI_MODEL"] = bare_model
                updates["SEC_AGENT_HARNESS2_IMPROVER_MODEL"] = oc_model
                if req.judge_model is not None and req.judge_model.strip():
                    j_clean = req.judge_model.strip()
                    if j_clean.startswith("sec_agent_harness2/"):
                        j_clean = j_clean[len("sec_agent_harness2/") :]
                    updates["SEC_AGENT_HARNESS2_JUDGE_MODEL"] = j_clean
                else:
                    updates["SEC_AGENT_HARNESS2_JUDGE_MODEL"] = bare_model
            elif req.judge_model is not None:
                j_clean = req.judge_model.strip()
                if j_clean.startswith("sec_agent_harness2/"):
                    j_clean = j_clean[len("sec_agent_harness2/") :]
                updates["SEC_AGENT_HARNESS2_JUDGE_MODEL"] = j_clean

            if req.judge_base_url is not None:
                j_base = req.judge_base_url.strip()
                updates["SEC_AGENT_HARNESS2_JUDGE_BASE_URL"] = j_base
                if not j_base:
                    # Clear judge api key if custom base url is cleared
                    updates["SEC_AGENT_HARNESS2_JUDGE_API_KEY"] = ""
            if req.judge_api_key:
                updates["SEC_AGENT_HARNESS2_JUDGE_API_KEY"] = req.judge_api_key.strip()
            if req.protocol is not None:
                proto = req.protocol.strip()
                updates["SEC_AGENT_HARNESS2_API_PROTOCOL"] = proto
                updates["SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL"] = proto
                updates["SEC_AGENT_HARNESS2_PI_PROTOCOL"] = proto
            if req.effort is not None:
                updates["SEC_AGENT_HARNESS2_CLAUDE_EFFORT"] = req.effort.strip()
                updates["SEC_AGENT_HARNESS2_PI_EFFORT"] = req.effort.strip()
        elif req.executor_id == "claude":
            if eff_base is not None:
                updates["SEC_AGENT_HARNESS2_CLAUDE_BASE_URL"] = eff_base
            if req.api_key:
                updates["SEC_AGENT_HARNESS2_CLAUDE_API_KEY"] = req.api_key
                if not eff_base and not os.environ.get("SEC_AGENT_HARNESS2_CLAUDE_BASE_URL"):
                    updates["ANTHROPIC_API_KEY"] = req.api_key
            if req.model is not None:
                updates["SEC_AGENT_HARNESS2_CLAUDE_MODEL"] = req.model
            if req.protocol is not None:
                updates["SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL"] = req.protocol
            if req.effort is not None:
                updates["SEC_AGENT_HARNESS2_CLAUDE_EFFORT"] = req.effort
            if req.cli_path is not None:
                updates["SEC_AGENT_HARNESS2_CLAWGOD_PATH"] = req.cli_path
        elif req.executor_id == "oc":
            if eff_base is not None:
                updates["SEC_AGENT_HARNESS2_OPENCODE_BASE_URL"] = eff_base
            if req.api_key:
                updates["SEC_AGENT_HARNESS2_OPENCODE_API_KEY"] = req.api_key
            if req.model is not None:
                updates["SEC_AGENT_HARNESS2_SOLVER_MODEL"] = req.model
            if req.protocol is not None:
                updates["SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL"] = req.protocol
        elif req.executor_id == "cx":
            if eff_base is not None:
                updates["SEC_AGENT_HARNESS2_CODEX_BASE_URL"] = eff_base
            if req.container_url is not None:
                updates["SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL"] = req.container_url
            if req.api_key:
                updates["SEC_AGENT_HARNESS2_CODEX_API_KEY"] = req.api_key
            if req.model is not None:
                updates["SEC_AGENT_HARNESS2_CODEX_MODEL"] = req.model
        elif req.executor_id == "pi":
            if eff_base is not None:
                updates["SEC_AGENT_HARNESS2_PI_BASE_URL"] = eff_base
            if req.api_key:
                updates["SEC_AGENT_HARNESS2_PI_API_KEY"] = req.api_key
            if req.model is not None:
                updates["SEC_AGENT_HARNESS2_PI_MODEL"] = req.model
            if req.protocol is not None:
                updates["SEC_AGENT_HARNESS2_PI_PROTOCOL"] = req.protocol
            if req.effort is not None:
                updates["SEC_AGENT_HARNESS2_PI_EFFORT"] = req.effort
            if req.cli_path is not None:
                updates["SEC_AGENT_HARNESS2_PI_BIN"] = req.cli_path
        elif req.executor_id == "vertex":
            if req.improver_model is not None:
                updates["SEC_AGENT_HARNESS2_IMPROVER_MODEL"] = req.improver_model
            if req.judge_model is not None:
                updates["SEC_AGENT_HARNESS2_JUDGE_MODEL"] = req.judge_model
            elif req.model is not None:
                updates["SEC_AGENT_HARNESS2_JUDGE_MODEL"] = req.model
            if req.judge_base_url is not None:
                updates["SEC_AGENT_HARNESS2_JUDGE_BASE_URL"] = req.judge_base_url
            elif eff_base is not None:
                updates["SEC_AGENT_HARNESS2_JUDGE_BASE_URL"] = eff_base
            if req.judge_api_key:
                updates["SEC_AGENT_HARNESS2_JUDGE_API_KEY"] = req.judge_api_key
            elif req.api_key:
                updates["SEC_AGENT_HARNESS2_JUDGE_API_KEY"] = req.api_key
            if req.vertex_project is not None:
                updates["GOOGLE_CLOUD_PROJECT"] = req.vertex_project
            if req.vertex_location is not None:
                updates["GOOGLE_CLOUD_LOCATION"] = req.vertex_location

        persisted = scanner.persist_env_updates(
            workspace_root, updates, write_dotenv=req.persist_dotenv
        )
        return {
            "status": "updated",
            "applied": persisted,
            "executors": scanner.get_executors_status(workspace_root, runner.get_bridge_info()),
        }

    @app.post("/api/executors/test")
    async def test_executor_endpoint(req: ExecutorProbeRequest):
        return scanner.probe_executor_endpoint(
            workspace_root,
            req.target,
            base_url=req.base_url,
            api_key=req.api_key,
            protocol=req.protocol,
            model=req.model,
        )

    @app.post("/api/executors/models")
    async def get_executor_models(req: ExecutorModelsRequest):
        return scanner.fetch_endpoint_models(
            base_url=req.base_url,
            api_key=req.api_key,
            protocol=req.protocol,
            workspace_root=workspace_root,
        )

    @app.post("/api/executors/bridge/start")
    async def start_responses_bridge(req: BridgeControlRequest):
        scanner.sync_config_from_env()
        upstream = (req.upstream or os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", "")).strip()
        api_key = (req.api_key or os.environ.get("SEC_AGENT_HARNESS2_API_KEY", "")).strip()
        if not upstream:
            raise HTTPException(
                status_code=400,
                detail="启动 Responses 转换桥需要上游 Chat Completions 地址 (upstream 或 SEC_AGENT_HARNESS2_API_BASE_URL)",
            )
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="启动 Responses 转换桥需要上游 API Key (api_key 或 SEC_AGENT_HARNESS2_API_KEY)",
            )
        try:
            meta = await runner.start_bridge(
                upstream, api_key, host=req.host or "0.0.0.0", port=req.port
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"启动转换桥失败: {exc}")

        if req.auto_bind_codex and meta.get("settings"):
            settings = meta["settings"]
            updates: dict[str, str | None] = {
                "SEC_AGENT_HARNESS2_CODEX_BASE_URL": settings.get("SEC_AGENT_HARNESS2_CODEX_BASE_URL"),
                "SEC_AGENT_HARNESS2_CODEX_API_KEY": settings.get("SEC_AGENT_HARNESS2_CODEX_API_KEY"),
            }
            if settings.get("SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL"):
                updates["SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL"] = settings["SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL"]
            scanner.persist_env_updates(workspace_root, updates, write_dotenv=True)

        return {
            "status": "started",
            "bridge": meta,
            "executors": scanner.get_executors_status(workspace_root, runner.get_bridge_info()),
        }

    @app.post("/api/executors/bridge/stop")
    async def stop_responses_bridge():
        res = await runner.stop_bridge()
        return {
            "status": "stopped",
            "result": res,
            "executors": scanner.get_executors_status(workspace_root, runner.get_bridge_info()),
        }

    @app.get("/api/executor/codex-bridge/status")
    @app.get("/api/executors/bridge/status")
    async def get_codex_bridge_status():
        scanner.sync_config_from_env()
        return scanner.get_bridge_status(workspace_root, runner.get_bridge_info())

    @app.post("/api/executor/codex-bridge/reprobe")
    @app.get("/api/executor/codex-bridge/reprobe")
    @app.post("/api/executors/bridge/reprobe")
    async def reprobe_codex_bridge(req: BridgeReprobeRequest | None = None):
        scanner.sync_config_from_env()
        from .. import install

        base_url = ((req.base_url if req else None) or os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL", "")).strip()
        api_key = ((req.api_key if req else None) or os.environ.get("SEC_AGENT_HARNESS2_API_KEY", "")).strip()
        if not base_url:
            raise HTTPException(status_code=400, detail="未配置基础地址 (Base URL)")

        probe_res = api.probe_upstream_responses_capability(base_url, api_key)
        bridge_json = workspace_root / "dependencies" / "codex" / "responses-bridge.json"
        saved = scanner._safe_read_json(bridge_json) or {}
        saved["wire_mode"] = probe_res.get("wire_mode", "bridge")
        if "port" not in saved:
            saved["port"] = 8765
        if "key" not in saved:
            import secrets

            saved["key"] = secrets.token_urlsafe(24)
        saved["host"] = saved.get("host", "0.0.0.0")
        bridge_json.parent.mkdir(parents=True, exist_ok=True)
        bridge_json.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        bridge_json.chmod(0o600)

        target_codex_home = workspace_root / "dependencies" / "codex" / "home"
        try:
            install.configure_codex(dry_run=False, home_dir=target_codex_home)
        except Exception:
            pass

        return {
            "probe": probe_res,
            "bridge": scanner.get_bridge_status(workspace_root, runner.get_bridge_info()),
            "executors": scanner.get_executors_status(workspace_root, runner.get_bridge_info()),
        }

    # -----------------------------
    # Runs, Tasks & Artifacts APIs
    # -----------------------------
    @app.get("/api/runs")
    async def list_all_runs():
        runs = scanner.list_runs(runs_root)
        return {"runs": runs}

    @app.get("/api/runs/{run_id}/tasks")
    async def get_run_tasks(run_id: str):
        tasks = scanner.get_tasks_for_run(runs_root, run_id)
        return {"run_id": run_id, "tasks": tasks}

    @app.get("/api/runs/{run_id}/tasks/{task_id:path}/diff")
    async def get_diff(
        run_id: str,
        task_id: str,
        base: str = Query("base", description="Base harness label 基准套件标签"),
        compare: str = Query("agg1", description="Compare harness label 对比套件标签"),
    ):
        diff_res = scanner.get_harness_diff(runs_root, run_id, task_id, base, compare)
        return diff_res

    @app.get("/api/runs/{run_id}/tasks/{task_id:path}/harnesses/{label}")
    async def get_task_harness(run_id: str, task_id: str, label: str):
        components = scanner.get_harness_components(runs_root, run_id, task_id, label)
        if not components:
            raise HTTPException(
                status_code=404, detail=f"未找到任务 {task_id} 的套件标签 {label}"
            )
        return components

    @app.get("/api/runs/{run_id}/tasks/{task_id:path}")
    async def get_task_detail(run_id: str, task_id: str):
        detail = scanner.get_task_detail(runs_root, run_id, task_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"在运行 {run_id} 中未找到任务 {task_id}")
        return detail

    @app.get("/api/runs/{run_id}/library")
    async def get_library(run_id: str):
        entries = scanner.get_library_index(runs_root, run_id)
        return {"run_id": run_id, "entries": entries}

    @app.get("/api/runs/{run_id}/benchmark")
    async def get_benchmark(run_id: str):
        report = scanner.get_benchmark_report(runs_root, run_id)
        return report

    # -----------------------------
    # Static SPA serving
    # -----------------------------
    candidate_dirs = [
        workspace_root / "frontend" / "dist",
        Path(__file__).resolve().parents[3] / "frontend" / "dist",
        Path(__file__).parent / "static",
    ]
    static_dir = next(
        (d for d in candidate_dirs if d.is_dir() and (d / "index.html").is_file()),
        candidate_dirs[0],
    )
    if static_dir.is_dir() and (static_dir / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("assets/"):
                target = static_dir / full_path
                if target.is_file():
                    return FileResponse(target)
                raise HTTPException(status_code=404, detail="Asset not found")

            target = static_dir / full_path
            if target.is_file() and full_path != "":
                return FileResponse(target)

            return FileResponse(
                static_dir / "index.html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
    else:
        @app.get("/", response_class=HTMLResponse)
        async def serve_missing_frontend():
            return HTMLResponse(
                content=(
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    "<title>Harness² 控制台</title></head>"
                    "<body style='font-family:system-ui;padding:2rem;max-width:640px;margin:0 auto'>"
                    "<h2>Harness² 可视化控制台 — 前端尚未构建</h2>"
                    "<p>前端静态资源尚未构建（<code>frontend/dist/</code> 缺失）。请在项目根目录执行：</p>"
                    "<pre style='background:#f1f5f9;padding:1rem;border-radius:8px'>"
                    "cd frontend &amp;&amp; npm install &amp;&amp; npm run build\n"
                    "# 或直接执行: make dev</pre>"
                    "</body></html>"
                ),
                status_code=200,
            )

    return app
