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

"""Background task execution runner, process manager, and SSE log broadcaster."""

from __future__ import annotations

import asyncio
import os
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

STEP_NODES = [
    {"index": 0, "nodeId": "s1-task-in", "stage": 1, "title": "任务规格与隔离接入"},
    {"index": 1, "nodeId": "s1-prior-lib", "stage": 1, "title": "领域经验库先验"},
    {"index": 2, "nodeId": "s1-base-roll", "stage": 1, "title": "基线探针试跑"},
    {"index": 3, "nodeId": "s2-context-build", "stage": 2, "title": "对比证据包组装"},
    {"index": 4, "nodeId": "s2-inv-levers", "stage": 2, "title": "通用工程杠杆 (INV)"},
    {"index": 5, "nodeId": "s2-dom-levers", "stage": 2, "title": "业务领域杠杆 (DOM)"},
    {"index": 6, "nodeId": "s2-validation-gate", "stage": 2, "title": "SurfaceSpec 规范检验"},
    {"index": 7, "nodeId": "s2-probe-exec", "stage": 2, "title": "沙箱并发探针试跑"},
    {"index": 8, "nodeId": "s3-compose-choice", "stage": 3, "title": "组合合成与模式分支"},
    {"index": 9, "nodeId": "s4-blind-judge", "stage": 4, "title": "零标注无监督盲审"},
    {"index": 10, "nodeId": "s5-reflector", "stage": 5, "title": "经验反思提炼"},
    {"index": 11, "nodeId": "s5-update-lib", "stage": 5, "title": "沉淀领域经验库闭环"},
]


def detect_lifecycle_step(line: str) -> int | None:
    """Identify stage transition step (0..11) from log stream."""
    line_lower = line.lower()
    if "[lifecycle:" in line_lower:
        for s in STEP_NODES:
            if s["nodeId"].lower() in line_lower or f":{s['index']}]" in line_lower:
                return s["index"]

    if any(k in line_lower for k in ("index.md", "update_library", "persisting", "沉淀", "已写入经验库")):
        return 11
    if any(k in line_lower for k in ("reflector", "reflecting", "cue", "lesson", "反思提炼")):
        return 10
    if any(k in line_lower for k in ("chosen_label", "selection", "blind judge", "盲选", "裁决")):
        return 9
    if any(k in line_lower for k in ("compose", "composition", "agg", "seq", "合成", "精炼")):
        return 8
    if any(k in line_lower for k in ("_roll_many", "probe rollout", "rolling candidates", "并发探针")):
        return 7
    if any(k in line_lower for k in ("surfacespec", "validation", "validate", "规范网关", "语法校验")):
        return 6
    if any(k in line_lower for k in ("dom", "skill", "script", "subagent", "领域杠杆")):
        return 5
    if any(k in line_lower for k in ("inv", "prompt", "guardrail", "tool contract", "工程杠杆")):
        return 4
    if any(k in line_lower for k in ("contrastive evidence", "context.build", "差异切片", "证据包")):
        return 3
    if any(k in line_lower for k in ("_roll_bases", "baseline probe", "base rollout", "基线探针")):
        return 2
    if any(k in line_lower for k in ("library prior", "prior domain", "冷启动先验", "加载经验库")):
        return 1
    if any(k in line_lower for k in ("taskspec", "spec seam", "started", "任务启动", "规格接入")):
        return 0
    return None


class ExecutionManager:
    """Manages active CLI runs, capturing stdout/stderr and broadcasting events."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.process: asyncio.subprocess.Process | None = None
        self.current_job: dict[str, Any] | None = None
        self.logs: deque[str] = deque(maxlen=4000)
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self.bridge_process: asyncio.subprocess.Process | None = None
        self.bridge_meta: dict[str, Any] = {}

    def get_status(self) -> dict[str, Any]:
        if self.current_job is None:
            return {"status": "idle", "job": None, "recent_logs_count": len(self.logs)}
        return {
            "status": self.current_job.get("status", "idle"),
            "job": self.current_job,
            "recent_logs_count": len(self.logs),
        }

    def get_logs(self, limit: int = 500) -> list[str]:
        logs_list = list(self.logs)
        return logs_list[-limit:]

    async def subscribe(self) -> AsyncGenerator[dict[str, Any], None]:
        """Subscribe to live execution events and log output."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self.subscribers.add(queue)
        try:
            # Send initial state
            yield {
                "event": "init",
                "data": {
                    "status": self.current_job.get("status") if self.current_job else "idle",
                    "job": self.current_job,
                    "logs": self.get_logs(100),
                },
            }
            while True:
                msg = await queue.get()
                yield msg
        finally:
            self.subscribers.discard(queue)

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Send event payload to all connected SSE clients."""
        msg = {"event": event_type, "data": data}
        dead_queues = set()
        for q in self.subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass
            except Exception:
                dead_queues.add(q)
        self.subscribers.difference_update(dead_queues)

    async def start_job(
        self, job_type: str, args: list[str], extra_env: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Spawn a new background CLI run."""
        async with self._lock:
            if self.process is not None and self.process.returncode is None:
                raise RuntimeError("当前已有任务正在运行，请先终止后再启动新任务。")

            job_id = f"{job_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self.logs.clear()

            # Resolve python binary from current venv if possible
            py_bin = sys.executable

            cmd = [py_bin] + args

            env_vars = os.environ.copy()
            if extra_env:
                env_vars.update(extra_env)

            self.current_job = {
                "job_id": job_id,
                "job_type": job_type,
                "command": cmd,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "exit_code": None,
            }

            try:
                self.process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.workspace_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env_vars,
                )
            except Exception as exc:
                self.current_job["status"] = "failed"
                self.current_job["error"] = str(exc)
                await self.broadcast("status", self.current_job)
                raise

            # Launch output reading task
            asyncio.create_task(self._watch_process(self.process, self.current_job))

            await self.broadcast("start", self.current_job)
            return self.current_job

    async def _watch_process(
        self, proc: asyncio.subprocess.Process, job: dict[str, Any]
    ) -> None:
        assert proc.stdout is not None
        current_step: int = 0
        job["current_step_index"] = 0
        job["current_node_id"] = STEP_NODES[0]["nodeId"]

        # Initial step 0 broadcast: Task Inflow & Coldstart
        await self.broadcast("stage_step", {
            "stepIndex": 0,
            "nodeId": STEP_NODES[0]["nodeId"],
            "stage": STEP_NODES[0]["stage"],
            "status": "active",
            "title": STEP_NODES[0]["title"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip()
            self.logs.append(line)
            await self.broadcast("log", {"line": line, "timestamp": datetime.now(timezone.utc).isoformat()})

            detected = detect_lifecycle_step(line)
            if detected is not None and detected > current_step:
                current_step = detected
                job["current_step_index"] = current_step
                job["current_node_id"] = STEP_NODES[current_step]["nodeId"]
                await self.broadcast("stage_step", {
                    "stepIndex": current_step,
                    "nodeId": STEP_NODES[current_step]["nodeId"],
                    "stage": STEP_NODES[current_step]["stage"],
                    "status": "active",
                    "title": STEP_NODES[current_step]["title"],
                    "line": line,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        exit_code = await proc.wait()
        job["exit_code"] = exit_code
        job["finished_at"] = datetime.now(timezone.utc).isoformat()
        job["status"] = "completed" if exit_code == 0 else "failed"

        if exit_code == 0:
            job["current_step_index"] = 11
            job["current_node_id"] = STEP_NODES[11]["nodeId"]
            await self.broadcast("stage_step", {
                "stepIndex": 11,
                "nodeId": STEP_NODES[11]["nodeId"],
                "stage": STEP_NODES[11]["stage"],
                "status": "completed",
                "title": STEP_NODES[11]["title"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        await self.broadcast("finish", job)
        await self.broadcast("refresh", {"timestamp": datetime.now(timezone.utc).isoformat()})

    async def stop_job(self) -> dict[str, Any]:
        """Terminate the running job."""
        async with self._lock:
            if self.process is None or self.process.returncode is not None:
                return {"message": "当前没有正在运行的任务。"}

            try:
                self.process.terminate()
                await asyncio.sleep(0.5)
                if self.process.returncode is None:
                    self.process.kill()
            except ProcessLookupError:
                pass

            if self.current_job:
                self.current_job["status"] = "terminated"
                self.current_job["finished_at"] = datetime.now(timezone.utc).isoformat()
                await self.broadcast("terminate", self.current_job)

            return {"message": "任务已成功终止。"}

    def get_bridge_info(self) -> dict[str, Any]:
        return {"running": False}

    async def start_bridge(
        self,
        upstream: str,
        api_key: str,
        *,
        host: str = "0.0.0.0",
        port: int = 0,
    ) -> dict[str, Any]:
        raise RuntimeError("Responses bridge has been removed in dual-substrate architecture.")

    async def stop_bridge(self) -> dict[str, Any]:
        return {"stopped": False, "message": "Responses 转换桥已移除。"}
