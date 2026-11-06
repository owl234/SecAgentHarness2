"""PiAgent subclass that materializes a harness workspace (`pi_root`) into the container."""

from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path
from typing import Any

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

try:
    from workbuddy_bench.agents.pi_agent import PiAgent
except ImportError:
    from agents.pi_agent import PiAgent

_HARNESS_ENTRIES = (
    "AGENTS.md",
    ".pi",
    "scripts",
    "sub_agents",
    "mcp",
    ".mcp.json",
    "_pi_runtime",
)


class PiHarnessAgent(PiAgent):
    """PiAgent + host harness workspace overlay via `WB_HARNESS_WS`."""

    def __init__(self, logs_dir: Path, *args: Any, **kwargs: Any) -> None:
        ws = kwargs.pop("WB_HARNESS_WS", None)
        self._harness_ws: Path | None = Path(ws) if ws else None
        super().__init__(logs_dir, *args, **kwargs)

    @staticmethod
    def name() -> str:
        return "pi-harness"

    def _harness_payload(self) -> tuple[bytes, int]:
        """gzip tar of the pi_root entries in the workspace (host side)."""
        ws = self._harness_ws
        if ws is None or not ws.is_dir():
            return b"", 0
        payload = io.BytesIO()
        n = 0
        with tarfile.open(fileobj=payload, mode="w:gz") as tar:
            for entry in _HARNESS_ENTRIES:
                src = ws / entry
                if src.is_file():
                    tar.add(src, arcname=entry)
                    n += 1
                elif src.is_dir():
                    for p in sorted(src.rglob("*")):
                        if p.is_file():
                            tar.add(p, arcname=f"{entry}/{p.relative_to(src)}")
                            n += 1
        return payload.getvalue(), n

    async def _materialize_harness(self, environment: BaseEnvironment) -> None:
        """Install the harness at workspace root and commit it pre-agent to protect diff evaluation."""
        ws = self._harness_ws
        if ws is None or not ws.is_dir():
            return
        blob_bytes, n = self._harness_payload()
        if n == 0:
            return
        blob = base64.b64encode(blob_bytes).decode()
        cmd = (
            "cd /workspace && "
            f"echo {blob} | base64 -d | tar -xzf - -C /workspace && "
            "chmod +x /workspace/scripts/*.py /workspace/scripts/*.sh 2>/dev/null || true; "
            "if git rev-parse --git-dir >/dev/null 2>&1; then "
            "git add -A && "
            "{ git diff --cached --quiet || "
            "git -c user.email=harness@bench -c user.name=harness "
            'commit -q -m "harness install (pre-agent)"; }; '
            "fi"
        )
        await environment.exec(command=cmd)

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        if self._harness_ws is not None:
            await self._materialize_harness(environment)
        elif self._get_env("WB_HARNESS_WS"):
            self._harness_ws = Path(self._get_env("WB_HARNESS_WS"))
            await self._materialize_harness(environment)
        await super().run(instruction, environment, context)
