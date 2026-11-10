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

"""One API endpoint and key, adapted to each substrate's wire protocol.

The two CLIs (OpenCode and Pi) do not speak the same protocol, so a single
`SEC_AGENT_HARNESS2_API_BASE_URL` / `SEC_AGENT_HARNESS2_API_KEY` pair is translated per substrate:

    oc      openai-chat        OpenAI-compatible provider block in opencode.json
    pi      multi-protocol     openai-completions, openai-responses, anthropic-messages

Per-substrate variables win over the shared pair.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

# Importing config runs load_dotenv(); api must not resolve an endpoint before that,
# or .env values are invisible and the host's ANTHROPIC_* leak through instead.
from . import config  # noqa: F401

PROTOCOLS = ("anthropic", "openai-chat", "openai-responses")

OPENCODE_PROVIDER = "sec_agent_harness2"


@dataclass(frozen=True)
class Endpoint:
    """A resolved endpoint: where to send requests, with what key, speaking what."""

    base_url: str
    api_key: str
    protocol: str
    model: str = ""

    def __bool__(self) -> bool:
        return bool(self.base_url)

    @property
    def is_anthropic_native(self) -> bool:
        """True when the key goes to Anthropic itself rather than a compatible proxy."""
        return "anthropic.com" in self.base_url


def _first(*names: str) -> str:
    """The first non-empty environment value among `names`."""
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _protocol(substrate_var: str, default: str) -> str:
    value = _first(substrate_var, "SEC_AGENT_HARNESS2_API_PROTOCOL") or default
    if value not in PROTOCOLS:
        raise ValueError(
            f"{substrate_var} is {value!r}; expected one of {', '.join(PROTOCOLS)}"
        )
    return value


def _shared() -> tuple[str, str, str]:
    return (
        _first("SEC_AGENT_HARNESS2_API_BASE_URL"),
        _first("SEC_AGENT_HARNESS2_API_KEY"),
        _first("SEC_AGENT_HARNESS2_API_MODEL"),
    )


def opencode() -> Endpoint | None:
    """OpenCode: any OpenAI-compatible endpoint via a generated provider block."""
    shared_url, shared_key, shared_model = _shared()
    url = _first("SEC_AGENT_HARNESS2_OPENCODE_BASE_URL") or shared_url
    if not url:
        return None
    return Endpoint(
        base_url=url,
        api_key=_first("SEC_AGENT_HARNESS2_OPENCODE_API_KEY") or shared_key,
        protocol=_protocol("SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL", "openai-chat"),
        model=_first("SEC_AGENT_HARNESS2_SOLVER_MODEL") or shared_model,
    )


PI_PROVIDER = "sec_agent_harness2"


def pi(for_container: bool = False) -> Endpoint | None:
    """Pi Coding Agent: natively supports openai-completions, openai-responses, and anthropic-messages."""
    shared_url, shared_key, shared_model = _shared()
    url = _first("SEC_AGENT_HARNESS2_PI_BASE_URL") or shared_url
    if not url:
        return None
    if for_container:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.hostname in ("127.0.0.1", "localhost", "0.0.0.0"):
            port_str = f":{parsed.port}" if parsed.port else ""
            netloc = f"host.docker.internal{port_str}"
            url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return Endpoint(
        base_url=url,
        api_key=_first("SEC_AGENT_HARNESS2_PI_API_KEY") or shared_key,
        protocol=_protocol("SEC_AGENT_HARNESS2_PI_PROTOCOL", "openai-chat"),
        model=_first("SEC_AGENT_HARNESS2_PI_MODEL") or shared_model,
    )


def pi_models_json(endpoint: Endpoint, extra_models: list[str] | tuple[str, ...] = ()) -> str:
    """`$PI_CODING_AGENT_DIR/models.json` for Pi Coding Agent (`@mariozechner/pi-coding-agent`).

    Note: Pi's `ModelRegistry` strictly validates camelCase `baseUrl` (not `baseURL`).
    """
    api_map = {
        "openai-chat": "openai-completions",
        "openai-responses": "openai-responses",
        "anthropic": "anthropic-messages",
    }
    pi_api = api_map.get(endpoint.protocol, "openai-completions")
    raw_models: list[str] = []
    if endpoint.model:
        raw_models.append(endpoint.model)
    raw_models.extend(m for m in extra_models if m)
    seen: set[str] = set()
    models_list: list[dict] = []
    for raw in raw_models:
        bare = raw.split("/", 1)[-1] if "/" in raw else raw
        bare = bare.strip()
        if not bare or bare in seen:
            continue
        seen.add(bare)
        models_list.append(
            {
                "id": bare,
                "name": bare,
                "reasoning": True,
                "input": ["text", "image"],
                "contextWindow": 200000,
                "maxTokens": 64000,
            }
        )
    if not models_list:
        models_list.append(
            {
                "id": "default",
                "name": "default",
                "reasoning": True,
                "input": ["text", "image"],
                "contextWindow": 200000,
                "maxTokens": 64000,
            }
        )
    payload = {
        "providers": {
            PI_PROVIDER: {
                "baseUrl": endpoint.base_url,
                "apiKey": endpoint.api_key or "dummy-key",
                "api": pi_api,
                "models": models_list,
            }
        }
    }
    return json.dumps(payload, indent=2) + "\n"


def pi_env(
    endpoint: Endpoint,
    env: dict[str, str],
    *,
    agent_dir: object | None = None,
    extra_models: list[str] | tuple[str, ...] = (),
) -> dict[str, str]:
    """Write `models.json` to `agent_dir` (or `config.PI_AGENT_DIR`) and wire Pi env vars."""
    from pathlib import Path

    target_dir = Path(agent_dir) if agent_dir is not None else config.PI_AGENT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    models_file = target_dir / "models.json"
    models_file.write_text(pi_models_json(endpoint, extra_models=extra_models), encoding="utf-8")
    try:
        models_file.chmod(0o600)
    except OSError:
        pass
    env.setdefault("PI_CODING_AGENT_DIR", str(target_dir))
    env.setdefault("PI_OFFLINE", "1")
    env.setdefault("PI_SKIP_VERSION_CHECK", "1")
    env.setdefault("PI_TELEMETRY", "0")
    if endpoint.base_url:
        env["PI_BASE_URL"] = endpoint.base_url
    if endpoint.api_key:
        env["PI_API_KEY"] = endpoint.api_key
    if endpoint.model:
        env["PI_MODEL"] = endpoint.model
    return env


def opencode_env(endpoint: Endpoint, env: dict[str, str]) -> dict[str, str]:
    """Add the provider block OpenCode needs to reach a shared endpoint.

    OpenCode resolves `sec_agent_harness2/<model>` from configuration, not from the environment,
    so without this the CLI fails with `Model not found` before it ever calls out.
    A caller that already set OPENCODE_CONFIG_CONTENT keeps its own.
    """
    env.setdefault("OPENCODE_CONFIG_CONTENT", opencode_config(endpoint))
    return env


def opencode_config(endpoint: Endpoint) -> str:
    """`OPENCODE_CONFIG_CONTENT` JSON: a provider block merged after every file config."""
    if endpoint.protocol == "anthropic":
        npm = "@ai-sdk/anthropic"
    else:
        npm = "@ai-sdk/openai-compatible"
    model = endpoint.model.split("/", 1)[-1].split("#", 1)[0] if endpoint.model else ""
    block: dict = {
        "provider": {
            OPENCODE_PROVIDER: {
                "npm": npm,
                "name": "Harness2 API",
                "options": {
                    "baseURL": endpoint.base_url,
                    "apiKey": endpoint.api_key,
                },
                "models": (
                    {
                        model: {
                            "id": model,
                            "name": model,
                            "tool_call": True,
                            "capabilities": {
                                "reasoning": {
                                    "supported": True,
                                    "effort": ["low", "medium", "high"],
                                }
                            },
                        }
                    }
                    if model
                    else {}
                ),
            }
        }
    }
    return json.dumps(block)


def describe(endpoint: Endpoint | None) -> str:
    """One line for `harness2 check`; never includes the key."""
    if endpoint is None:
        return "(no API endpoint configured)"
    model = endpoint.model or "(model from CLI flag)"
    return f"{endpoint.protocol} -> {endpoint.base_url} model={model}"


__all__ = [
    "PI_PROVIDER",
    "PROTOCOLS",
    "Endpoint",
    "describe",
    "opencode",
    "opencode_config",
    "opencode_env",
    "pi",
    "pi_env",
    "pi_models_json",
]
