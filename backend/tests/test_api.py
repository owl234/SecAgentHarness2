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
    "SEC_AGENT_HARNESS2_OPENCODE_BASE_URL",
    "SEC_AGENT_HARNESS2_OPENCODE_API_KEY",
    "SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL",
    "SEC_AGENT_HARNESS2_SOLVER_MODEL",
    "SEC_AGENT_HARNESS2_PI_BASE_URL",
    "SEC_AGENT_HARNESS2_PI_API_KEY",
    "SEC_AGENT_HARNESS2_PI_PROTOCOL",
    "SEC_AGENT_HARNESS2_PI_MODEL",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in _ALL:
        monkeypatch.delenv(name, raising=False)


def test_no_endpoint_configured():
    assert api.opencode() is None
    assert api.pi() is None


def test_shared_endpoint_reaches_every_substrate(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_MODEL", "shared-model")

    for resolve, protocol in (
        (api.opencode, "openai-chat"),
        (api.pi, "openai-chat"),
    ):
        endpoint = resolve()
        assert endpoint is not None
        assert endpoint.base_url == "https://shared.example.com/v1"
        assert endpoint.api_key == "shared-key"
        assert endpoint.protocol == protocol


def test_per_substrate_values_win(monkeypatch):
    """A per-substrate variable beats the shared pair."""
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_BASE_URL", "https://oc.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_API_KEY", "oc-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_BASE_URL", "https://pi.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_API_KEY", "pi-key")

    assert api.opencode().base_url == "https://oc.example.com/v1"
    assert api.opencode().api_key == "oc-key"
    assert api.pi().base_url == "https://pi.example.com/v1"
    assert api.pi().api_key == "pi-key"


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
    model_obj = provider["models"]["some-model"]
    assert model_obj["capabilities"]["reasoning"]["supported"] is True
    assert model_obj["capabilities"]["reasoning"]["effort"] == ["low", "medium", "high"]
    assert "reasoning" not in model_obj or not isinstance(model_obj["reasoning"], bool)


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
    assert "super-secret-value" not in api.describe(api.pi())


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


def test_pi_env_adds_keys(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://shared.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "pi-secret")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_MODEL", "gpt-4o")

    env = api.pi_env(api.pi(), {})
    assert env["PI_BASE_URL"] == "https://shared.example.com/v1"
    assert env["PI_API_KEY"] == "pi-secret"
    assert env["PI_MODEL"] == "gpt-4o"


def test_pi_container_url(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_BASE_URL", "http://127.0.0.1:8000/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_API_KEY", "test-key")

    ep = api.pi(for_container=True)
    assert ep.base_url == "http://host.docker.internal:8000/v1"


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

    pi_prop = Proposer(ChannelSpec("pi", "improver-m"))
    pi_env = pi_prop.env()
    assert pi_env["PI_BASE_URL"] == "https://shared.example.com/v1"
    assert pi_env["PI_API_KEY"] == "shared-key"
