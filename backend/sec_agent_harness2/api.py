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

The three CLIs do not speak the same protocol, so a single
`SEC_AGENT_HARNESS2_API_BASE_URL` / `SEC_AGENT_HARNESS2_API_KEY` pair is translated per substrate:

    cx      openai-responses   Codex refuses anything but `wire_api = "responses"`
    claude  anthropic          native Messages API; `openai-chat` opts into clawgod's proxy
    oc      openai-chat        OpenAI-compatible provider block in opencode.json

Per-substrate variables win over the shared pair, so an existing deployment that
sets `SEC_AGENT_HARNESS2_CODEX_*` or `ANTHROPIC_*` keeps working unchanged.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

# Importing config runs load_dotenv(); api must not resolve an endpoint before that,
# or .env values are invisible and the host's ANTHROPIC_* leak through instead.
from . import config  # noqa: F401

PROTOCOLS = ("anthropic", "openai-chat", "openai-responses")

# clawgod selects its translation proxy from provider.json, not from the environment.
CLAW_GOD_PROVIDER = "claude"
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


def _get_bridge_endpoint(for_container: bool = False) -> tuple[str, str] | None:
    """Read bridge configuration (port, key) from dependencies/codex/responses-bridge.json."""
    try:
        bridge_path = config.DEPENDENCIES / "codex" / "responses-bridge.json"
        if not bridge_path.is_file():
            from .cli.responses_bridge import _endpoint

            bridge_path.parent.mkdir(parents=True, exist_ok=True)
            _endpoint(bridge_path)
        if bridge_path.is_file():
            data = json.loads(bridge_path.read_text(encoding="utf-8"))
            port = data.get("port") or 8765
            key = data.get("key") or ""
            host = "host.docker.internal" if for_container else "127.0.0.1"
            return f"http://{host}:{port}/v1", key
    except Exception:
        pass
    return None


def probe_upstream_responses_capability(
    base_url: str,
    api_key: str,
    *,
    timeout: float = 8.0,
) -> dict:
    """Probe whether an upstream base_url supports the Responses API (/v1/responses) natively."""
    import time
    import urllib.error
    import urllib.request

    clean_base = (base_url or "").rstrip("/")
    if not clean_base:
        return {
            "wire_mode": "bridge",
            "status_code": None,
            "latency_ms": 0,
            "message": "No base_url provided",
            "url": "",
        }
    responses_url = clean_base + ("/responses" if clean_base.endswith("/v1") else "/v1/responses")
    body = json.dumps({"model": "ping", "input": "ping", "max_output_tokens": 1}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Harness2-ResponsesProbe/1.0",
    }
    req = urllib.request.Request(responses_url, data=body, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.perf_counter() - t0) * 1000)
            return {
                "wire_mode": "native",
                "status_code": resp.status,
                "latency_ms": latency,
                "message": f"Upstream natively supports Responses API (HTTP {resp.status}, {latency}ms)",
                "url": responses_url,
            }
    except urllib.error.HTTPError as err:
        latency = int((time.perf_counter() - t0) * 1000)
        # Route does not exist on server -> bridge needed
        if err.code in (404, 405):
            return {
                "wire_mode": "bridge",
                "status_code": err.code,
                "latency_ms": latency,
                "message": f"Upstream lacks Responses endpoint (HTTP {err.code}, {latency}ms) - Bridge managed",
                "url": responses_url,
            }
        # Route exists and responded (even if rejecting model/auth/params) -> native responses capability
        if err.code in (400, 401, 403, 422):
            return {
                "wire_mode": "native",
                "status_code": err.code,
                "latency_ms": latency,
                "message": f"Upstream recognizes Responses endpoint (HTTP {err.code}, {latency}ms)",
                "url": responses_url,
            }
        return {
            "wire_mode": "bridge",
            "status_code": err.code,
            "latency_ms": latency,
            "message": f"Upstream error (HTTP {err.code}, {latency}ms) - fallback to Bridge",
            "url": responses_url,
        }
    except Exception as exc:
        latency = int((time.perf_counter() - t0) * 1000)
        return {
            "wire_mode": "bridge",
            "status_code": None,
            "latency_ms": latency,
            "message": f"Connection to upstream failed ({type(exc).__name__}) - fallback to Bridge",
            "url": responses_url,
        }


def codex(for_container: bool = False) -> Endpoint | None:
    """Codex speaks only the Responses API; there is no chat fallback in 0.144.6."""
    shared_url, shared_key, shared_model = _shared()
    explicit_codex_url = _first("SEC_AGENT_HARNESS2_CODEX_BASE_URL")
    explicit_codex_key = _first("SEC_AGENT_HARNESS2_CODEX_API_KEY")
    model = _first("SEC_AGENT_HARNESS2_CODEX_MODEL") or shared_model

    wire_mode = _first("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE")
    if not wire_mode:
        try:
            bridge_path = config.DEPENDENCIES / "codex" / "responses-bridge.json"
            if bridge_path.is_file():
                saved = json.loads(bridge_path.read_text(encoding="utf-8"))
                wire_mode = saved.get("wire_mode", "")
        except Exception:
            pass

    # If explicit wire_mode is bridge, or if explicit_codex_url points to local bridge
    if wire_mode == "bridge" or (
        explicit_codex_url and any(h in explicit_codex_url for h in ("127.0.0.1:8765", "0.0.0.0:8765", "localhost:8765"))
    ):
        bridge_ep = _get_bridge_endpoint(for_container=for_container)
        if bridge_ep:
            b_url, b_key = bridge_ep
            return Endpoint(
                base_url=b_url,
                api_key=b_key or explicit_codex_key or shared_key,
                protocol="openai-responses",
                model=model,
            )
        host = "host.docker.internal" if for_container else "127.0.0.1"
        return Endpoint(
            base_url=f"http://{host}:8765/v1",
            api_key=explicit_codex_key or shared_key,
            protocol="openai-responses",
            model=model,
        )

    url = explicit_codex_url or shared_url
    if not url:
        return None

    key = explicit_codex_key or shared_key
    if for_container:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.hostname in ("127.0.0.1", "localhost", "0.0.0.0"):
            port_str = f":{parsed.port}" if parsed.port else ""
            netloc = f"host.docker.internal{port_str}"
            url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    return Endpoint(
        base_url=url,
        api_key=key,
        protocol="openai-responses",
        model=model,
    )


def claude() -> Endpoint | None:
    """Claude Code: native Messages by default, OpenAI chat through clawgod's proxy.

    SEC_AGENT_HARNESS2_* wins over ANTHROPIC_*: when Harness2 itself runs under Claude Code,
    the host session exports ANTHROPIC_BASE_URL pointing at its own proxy, and
    inheriting that would silently send rollouts to the wrong endpoint.
    """
    shared_url, shared_key, shared_model = _shared()
    url = _first("SEC_AGENT_HARNESS2_CLAUDE_BASE_URL") or shared_url or _first("ANTHROPIC_BASE_URL")
    if not url:
        return None
    return Endpoint(
        base_url=url,
        api_key=_first("SEC_AGENT_HARNESS2_CLAUDE_API_KEY")
        or shared_key
        or _first("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"),
        protocol=_protocol("SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL", "anthropic"),
        model=_first("SEC_AGENT_HARNESS2_CLAUDE_MODEL") or shared_model,
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
    return env


def claude_env(endpoint: Endpoint, env: dict[str, str]) -> dict[str, str]:
    """Map an endpoint onto the variables clawgod reads, without clobbering the caller.

    Only the native Anthropic protocol is expressible through the environment alone.
    `openai-chat` needs clawgod's provider.json, which is a single global file under
    the install directory, so concurrent rollouts would overwrite each other; callers
    that want it must use `claude_provider_json` and serialise their runs.
    """
    if endpoint.protocol != "anthropic":
        raise ValueError(
            "the claude substrate reaches a non-Anthropic endpoint only through clawgod's "
            "openai-chat proxy, which is configured by a single global provider.json; "
            "set SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL=anthropic or point SEC_AGENT_HARNESS2_API_BASE_URL at an "
            "Anthropic-compatible endpoint"
        )
    env.setdefault("ANTHROPIC_BASE_URL", endpoint.base_url)
    # clawgod sends ANTHROPIC_API_KEY to Anthropic itself and ANTHROPIC_AUTH_TOKEN to a
    # compatible proxy; sending the wrong one drops the Authorization header.
    if endpoint.is_anthropic_native:
        env.setdefault("ANTHROPIC_API_KEY", endpoint.api_key)
    else:
        env.setdefault("ANTHROPIC_AUTH_TOKEN", endpoint.api_key)
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
    model = endpoint.model.split("/", 1)[-1] if endpoint.model else ""
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
                            "reasoning": True,
                        }
                    }
                    if model
                    else {}
                ),
            }
        }
    }
    return json.dumps(block)


def claude_provider_json(endpoint: Endpoint) -> str:
    """`provider.json` for clawgod's openai-chat mode.

    clawgod only starts its Messages<->Chat translation proxy when `protocol` says
    `openai-chat`, and it reads that from provider.json rather than the environment,
    so this file is the one place the key has to be written to disk.
    """
    return json.dumps(
        {
            "protocol": "openai-chat",
            "apiKey": endpoint.api_key,
            "baseURL": endpoint.base_url,
            "model": endpoint.model,
            "smallModel": "",
            "effort": "",
            "timeoutMs": 3000000,
        },
        indent=2,
    ) + "\n"


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
    "claude",
    "claude_env",
    "claude_provider_json",
    "codex",
    "describe",
    "opencode",
    "opencode_config",
    "opencode_env",
    "pi",
    "pi_env",
    "pi_models_json",
    "probe_upstream_responses_capability",
]
