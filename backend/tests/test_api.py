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

"""Unit tests for the shared API endpoint layer (sec_agent_harness2/api.py)."""

import json

import pytest

from sec_agent_harness2 import api

_ALL = (
    "SEC_AGENT_HARNESS2_API_BASE_URL",
    "SEC_AGENT_HARNESS2_API_KEY",
    "SEC_AGENT_HARNESS2_API_MODEL",
    "SEC_AGENT_HARNESS2_API_PROTOCOL",
    "SEC_AGENT_HARNESS2_CODEX_BASE_URL",
    "SEC_AGENT_HARNESS2_CODEX_API_KEY",
    "SEC_AGENT_HARNESS2_CODEX_MODEL",
    "SEC_AGENT_HARNESS2_CLAUDE_BASE_URL",
    "SEC_AGENT_HARNESS2_CLAUDE_API_KEY",
    "SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL",
    "SEC_AGENT_HARNESS2_CLAUDE_MODEL",
    "SEC_AGENT_HARNESS2_OPENCODE_BASE_URL",
    "SEC_AGENT_HARNESS2_OPENCODE_API_KEY",
    "SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL",
    "SEC_AGENT_HARNESS2_SOLVER_MODEL",
    "SEC_AGENT_HARNESS2_CODEX_MODEL",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ALL:
        monkeypatch.delenv(name, raising=False)


def test_no_endpoint_configured():
    assert api.codex() is None
    assert api.claude() is None
    assert api.opencode() is None


def test_shared_endpoint_reaches_every_substrate(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_MODEL", "shared-model")

    for resolve, protocol in (
        (api.codex, "openai-responses"),
        (api.claude, "anthropic"),
        (api.opencode, "openai-chat"),
    ):
        endpoint = resolve()
        assert endpoint.base_url == "https://shared.example.com/v1"
        assert endpoint.api_key == "shared-key"
        assert endpoint.protocol == protocol


def test_codex_only_speaks_responses(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_PROTOCOL", "openai-chat")
    assert api.codex().protocol == "openai-responses"


def test_per_substrate_values_win(monkeypatch):
    """A per-substrate variable beats the shared pair, but SEC_AGENT_HARNESS2_* beats ANTHROPIC_*.

    The ANTHROPIC_* fallback exists for hosts that export it themselves (Claude Code
    does); it must never outrank an endpoint the user configured for Harness2.
    """
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_BASE_URL", "https://codex.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_API_KEY", "codex-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CLAUDE_BASE_URL", "https://claude.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CLAUDE_API_KEY", "claude-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://host-proxy.example.com")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "host-token")

    assert api.codex().base_url == "https://codex.example.com/v1"
    assert api.codex().api_key == "codex-key"
    assert api.claude().base_url == "https://claude.example.com"
    assert api.claude().api_key == "claude-key"


def test_anthropic_env_is_only_a_fallback(monkeypatch):
    """With nothing HARNESS2-specific set, the host's ANTHROPIC_* is honoured."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://host-proxy.example.com")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "host-token")

    assert api.claude().base_url == "https://host-proxy.example.com"
    assert api.claude().api_key == "host-token"


def test_claude_native_uses_api_key(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://api.anthropic.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "sk-ant-x")
    env = api.claude_env(api.claude(), {})
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-x"
    assert "ANTHROPIC_AUTH_TOKEN" not in env


def test_claude_proxy_uses_auth_token(monkeypatch):
    """A non-Anthropic host must get AUTH_TOKEN; clawgod drops the key otherwise."""
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "proxy-key")
    env = api.claude_env(api.claude(), {})
    assert env["ANTHROPIC_AUTH_TOKEN"] == "proxy-key"
    assert "ANTHROPIC_API_KEY" not in env


def test_claude_does_not_clobber_existing_values(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "proxy-key")
    env = api.claude_env(api.claude(), {"ANTHROPIC_AUTH_TOKEN": "caller-token"})
    assert env["ANTHROPIC_AUTH_TOKEN"] == "caller-token"


def test_claude_openai_chat_is_refused(monkeypatch):
    """clawgod's chat mode needs a global provider.json, so it cannot be per-run."""
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "proxy-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL", "openai-chat")
    with pytest.raises(ValueError, match="provider.json"):
        api.claude_env(api.claude(), {})


def test_unknown_protocol_is_rejected(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL", "graphql")
    with pytest.raises(ValueError, match="expected one of"):
        api.opencode()


def test_opencode_config_shape(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "k")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_MODEL", "some-model")

    block = json.loads(api.opencode_config(api.opencode()))
    provider = block["provider"]["sec_agent_harness2"]
    assert provider["npm"] == "@ai-sdk/openai-compatible"
    assert provider["options"]["baseURL"] == "https://shared.example.com/v1"
    assert provider["options"]["apiKey"] == "k"
    assert "some-model" in provider["models"]


def test_opencode_config_anthropic_uses_native_sdk(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "k")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL", "anthropic")

    block = json.loads(api.opencode_config(api.opencode()))
    assert block["provider"]["sec_agent_harness2"]["npm"] == "@ai-sdk/anthropic"


def test_describe_never_leaks_the_key(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "super-secret-value")
    assert "super-secret-value" not in api.describe(api.opencode())


def test_opencode_env_adds_the_provider_block(monkeypatch):
    """Without this OpenCode fails with `Model not found: sec_agent_harness2/<model>`."""
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "k")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_MODEL", "m")

    env = api.opencode_env(api.opencode(), {})
    block = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert block["provider"]["sec_agent_harness2"]["options"]["baseURL"] == "https://shared.example.com/v1"


def test_opencode_env_keeps_a_callers_config(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "k")
    env = api.opencode_env(api.opencode(), {"OPENCODE_CONFIG_CONTENT": '{"mine":1}'})
    assert env["OPENCODE_CONFIG_CONTENT"] == '{"mine":1}'


def test_proposer_env_wires_shared_endpoint(monkeypatch):
    from sec_agent_harness2.core.proposer import Proposer
    from sec_agent_harness2.core.spec import ChannelSpec

    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_SOLVER_MODEL", "sec_agent_harness2/solver-m")

    oc_prop = Proposer(ChannelSpec("opencode", "sec_agent_harness2/improver-m"))
    oc_env = oc_prop.env()
    block = json.loads(oc_env["OPENCODE_CONFIG_CONTENT"])
    assert block["provider"]["sec_agent_harness2"]["options"]["baseURL"] == "https://shared.example.com/v1"
    assert "improver-m" in block["provider"]["sec_agent_harness2"]["models"]

    cl_prop = Proposer(ChannelSpec("claude_cli", "improver-m"))
    cl_env = cl_prop.env()
    assert cl_env["ANTHROPIC_BASE_URL"] == "https://shared.example.com/v1"
    assert cl_env["ANTHROPIC_AUTH_TOKEN"] == "shared-key"
    assert cl_env["ANTHROPIC_MODEL"] == "improver-m"
    assert "CLAUDE_CODE_USE_VERTEX" not in cl_env


def test_probe_upstream_responses_capability_404_triggers_bridge(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=8.0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = api.probe_upstream_responses_capability("https://api.openai-gateway.com/v1", "test-key")
    assert res["wire_mode"] == "bridge"
    assert res["status_code"] == 404
    assert "Bridge managed" in res["message"]


def test_probe_upstream_responses_capability_200_triggers_native(monkeypatch):
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    def fake_urlopen(req, timeout=8.0):
        return mock_resp

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = api.probe_upstream_responses_capability("https://native.openai.com/v1", "test-key")
    assert res["wire_mode"] == "native"
    assert res["status_code"] == 200
    assert "natively supports" in res["message"]


def test_codex_endpoint_bridge_mode_and_container(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-only.upstream.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-chat-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")

    fake_dep = tmp_path / "dependencies" / "codex"
    fake_dep.mkdir(parents=True, exist_ok=True)
    bridge_json = fake_dep / "responses-bridge.json"
    bridge_json.write_text(json.dumps({"port": 8765, "key": "bridge-secret-key"}), encoding="utf-8")
    monkeypatch.setattr(api.config, "DEPENDENCIES", tmp_path / "dependencies")

    # Host environment
    ep_host = api.codex(for_container=False)
    assert ep_host is not None
    assert ep_host.base_url == "http://127.0.0.1:8765/v1"
    assert ep_host.api_key == "bridge-secret-key"
    assert ep_host.protocol == "openai-responses"

    # Container environment
    ep_container = api.codex(for_container=True)
    assert ep_container is not None
    assert ep_container.base_url == "http://host.docker.internal:8765/v1"
    assert ep_container.api_key == "bridge-secret-key"


def test_codex_endpoint_bridge_key_precedence_over_env_key(monkeypatch, tmp_path):
    """When in bridge mode, the local bridge key MUST take precedence over upstream explicit CODEX_API_KEY."""
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-only.upstream.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "upstream-shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_API_KEY", "upstream-explicit-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")

    fake_dep = tmp_path / "dependencies" / "codex"
    fake_dep.mkdir(parents=True, exist_ok=True)
    bridge_json = fake_dep / "responses-bridge.json"
    bridge_json.write_text(json.dumps({"port": 8765, "key": "bridge-local-token-xyz"}), encoding="utf-8")
    monkeypatch.setattr(api.config, "DEPENDENCIES", tmp_path / "dependencies")

    ep = api.codex()
    assert ep is not None
    assert ep.base_url == "http://127.0.0.1:8765/v1"
    # Crucial assertion: Must NOT be upstream-explicit-key, which would cause HTTP 401 on bridge!
    assert ep.api_key == "bridge-local-token-xyz"


def test_codex_endpoint_lazy_generates_bridge_json(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")
    monkeypatch.setattr(api.config, "DEPENDENCIES", tmp_path / "dependencies")

    bridge_json = tmp_path / "dependencies" / "codex" / "responses-bridge.json"
    assert not bridge_json.is_file()

    ep = api.codex()
    assert ep is not None
    assert ep.base_url == "http://127.0.0.1:8765/v1"
    assert len(ep.api_key) > 10
    assert bridge_json.is_file()


def test_probe_upstream_responses_capability_401_triggers_native(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=8.0):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = api.probe_upstream_responses_capability("https://api.openai.com/v1", "bad-key")
    assert res["wire_mode"] == "native"
    assert res["status_code"] == 401
    assert "recognizes Responses endpoint" in res["message"]


def test_configure_codex_and_codex_config_error_equivalence(monkeypatch, tmp_path):
    from sec_agent_harness2 import install

    fake_codex_home = tmp_path / "codex_home"
    monkeypatch.setattr(install.config, "CODEX_HOME_DIR", fake_codex_home)
    monkeypatch.setattr(api.config, "DEPENDENCIES", tmp_path / "dependencies")
    monkeypatch.setattr(install.config, "DEPENDENCIES", tmp_path / "dependencies")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-only.upstream.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "test-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")

    # 1. configure_codex writes bridge config
    install.configure_codex(home_dir=fake_codex_home)
    assert (fake_codex_home / "config.toml").is_file()

    # 2. codex_config_error returns None when URLs match exactly
    err = install.codex_config_error(home_dir=fake_codex_home)
    assert err is None

    # 3. Localhost and 127.0.0.1 equivalence on same port should not trigger stale error
    toml_content = (fake_codex_home / "config.toml").read_text(encoding="utf-8")
    (fake_codex_home / "config.toml").write_text(
        toml_content.replace("127.0.0.1:8765", "localhost:8765"), encoding="utf-8"
    )
    err2 = install.codex_config_error(home_dir=fake_codex_home)
    assert err2 is None
