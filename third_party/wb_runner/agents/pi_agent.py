"""Pi Coding Agent (`@mariozechner/pi-coding-agent`) adapter for WorkBuddy-Bench."""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

_OUTPUT_FILENAME = "pi-output.jsonl"
_STDERR_FILENAME = "pi-stderr.txt"
_CAPTURE_DIR = "/tmp/_pi_capture"


class PiAgent(BaseInstalledAgent):
    """Run Pi Coding Agent inside the container via a mounted `/opt/pi` distribution."""

    SUPPORTS_ATIF: bool = False

    def __init__(self, logs_dir: Path, *args: Any, **kwargs: Any) -> None:
        self._pi_version: str | None = kwargs.pop("PI_VERSION", None)
        self._pi_model = str(kwargs.pop("PI_MODEL", ""))
        effort = kwargs.pop("PI_EFFORT", None)
        model_params = kwargs.pop("model_params", None) or {}
        if effort is None:
            extra_body = model_params.get("extra_body") or {}
            effort = extra_body.get("reasoning_effort")
        self._effort: str | None = str(effort) if effort else None
        self._agent_env: dict[str, str] = dict(kwargs.pop("extra_env", None) or {})
        kwargs.pop("connection", None)
        kwargs.pop("mount_path", None)
        kwargs.pop("instance_id", None)
        kwargs.pop("WB_HARNESS_WS", None)
        super().__init__(logs_dir, *args, version=self._pi_version, **kwargs)

    @staticmethod
    def name() -> str:
        return "pi"

    def _get_env(self, key: str, default: str = "") -> str:
        if key == "PI_MODEL" and self._pi_model:
            return self._pi_model
        if key == "PI_EFFORT" and self._effort:
            return self._effort
        val = self._agent_env.get(key)
        if val is not None:
            return val
        return os.environ.get(key, default)

    @property
    def _install_agent_template_path(self) -> Path:
        return Path(__file__).parent / "install-pi.sh.j2"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.exec(command=f"mkdir -p {_CAPTURE_DIR}")
        probe = await environment.exec(command="test -x /opt/pi/node_modules/.bin/pi")
        if probe.return_code != 0:
            raise RuntimeError(
                "No executable /opt/pi/node_modules/.bin/pi inside container. "
                "Bind-mount dependencies/pi at /opt/pi via environment_override.mounts."
            )

        base_url = self._get_env("PI_BASE_URL") or self._get_env("SEC_AGENT_HARNESS2_API_BASE_URL")
        api_key = self._get_env("PI_API_KEY") or self._get_env("SEC_AGENT_HARNESS2_API_KEY") or "dummy-key"
        protocol = self._get_env("PI_PROTOCOL") or "openai-chat"
        raw_model = self._get_env("PI_MODEL") or self.model_name or "gpt-5.4"
        bare_model = raw_model.split("/", 1)[-1] if "/" in raw_model else raw_model

        api_map = {
            "openai-chat": "openai-completions",
            "openai-responses": "openai-responses",
            "anthropic": "anthropic-messages",
        }
        pi_api = api_map.get(protocol, "openai-completions")
        if base_url:
            models_doc = {
                "providers": {
                    "sec_agent_harness2": {
                        "baseUrl": base_url,
                        "apiKey": api_key,
                        "api": pi_api,
                        "models": [
                            {
                                "id": bare_model,
                                "name": bare_model,
                                "reasoning": True,
                                "input": ["text", "image"],
                                "contextWindow": 200000,
                                "maxTokens": 64000,
                            }
                        ],
                    }
                }
            }
            payload = shlex.quote(json.dumps(models_doc, indent=2))
            await environment.exec(
                command=f"mkdir -p /root/.pi/agent && printf '%s\\n' {payload} > /root/.pi/agent/models.json"
            )

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        escaped = shlex.quote(instruction)
        raw_model = self._get_env("PI_MODEL") or self.model_name or "gpt-5.4"
        if "/" in raw_model:
            provider, bare_model = raw_model.split("/", 1)
        else:
            provider, bare_model = "sec_agent_harness2", raw_model
        effort = self._get_env("PI_EFFORT") or "high"

        env: dict[str, str] = {
            "PI_CODING_AGENT_DIR": "/root/.pi/agent",
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "SEC_AGENT_HARNESS2_PI_PROVIDER": provider,
            "SEC_AGENT_HARNESS2_PI_ACTIVE_MODEL": bare_model,
        }

        run_cmd = (
            f"mkdir -p {_CAPTURE_DIR}; "
            'BRIDGE_FLAG=""; '
            'if [ -f "./_pi_runtime/harness2_bridge.ts" ]; then BRIDGE_FLAG="-e ./_pi_runtime/harness2_bridge.ts"; fi; '
            f"/opt/pi/node_modules/.bin/pi -p {escaped} "
            "--mode json --no-session "
            "--tools read,bash,edit,write,grep,find,ls "
            f"--provider {shlex.quote(provider)} "
            f"--model {shlex.quote(bare_model)} "
            f"--thinking {shlex.quote(effort)} "
            "$BRIDGE_FLAG "
            f">{_CAPTURE_DIR}/{_OUTPUT_FILENAME} "
            f"2>{_CAPTURE_DIR}/{_STDERR_FILENAME}; "
            "rc=$?; "
            f"cp -f {_CAPTURE_DIR}/{_OUTPUT_FILENAME} /logs/agent/{_OUTPUT_FILENAME} 2>/dev/null || true; "
            f"cp -f {_CAPTURE_DIR}/{_STDERR_FILENAME} /logs/agent/{_STDERR_FILENAME} 2>/dev/null || true; "
            "exit $rc"
        )
        return [ExecInput(command=run_cmd, env=env)]

    def populate_context_post_run(self, context: AgentContext) -> None:
        return None
