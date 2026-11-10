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

"""Unit tests for PiSubstrate (@mariozechner/pi-coding-agent)."""

import json
import os
import shutil
from unittest.mock import MagicMock

import pytest

from sec_agent_harness2 import api, config
from sec_agent_harness2.cli._common import make_adapter, normalize_substrate
from sec_agent_harness2.core import proposer
from sec_agent_harness2.core import tree as HT
from sec_agent_harness2.core.spec import BenchSpec, ChannelSpec
from sec_agent_harness2.substrate.base import Substrate
from sec_agent_harness2.substrate.pi import (
    PI_BUILTIN_TOOLS,
    PI_SURFACE,
    PiSubstrate,
    final_message,
    find_pi_binary,
    mcp_config_json,
    parse_items,
    render_events,
)

# -----------------------------------------------------------------------------
# 1. Surface and Protocol Compliance Tests
# -----------------------------------------------------------------------------


def test_pi_surface_spec():
    assert PI_SURFACE.name == "pi"
    assert PI_SURFACE.always_on == ("AGENTS.md",)
    assert PI_SURFACE.always_on_max == 24_000
    assert PI_SURFACE.skill_dir == ".pi/skills"
    assert PI_SURFACE.plugin_dir == ".pi/extensions"
    assert PI_SURFACE.hooks_file == ".pi/hooks.json"
    assert PI_SURFACE.hook_events == frozenset(
        {
            "PreToolUse",
            "PostToolUse",
            "SessionStart",
            "Stop",
            "UserPromptSubmit",
        }
    )
    assert PI_SURFACE.subagent_requires_mode is False


def test_pi_substrate_protocol():
    sub = PiSubstrate()
    assert isinstance(sub, Substrate)
    assert sub.name == "pi"
    assert sub.surface() == PI_SURFACE


def test_normalize_substrate_pi():
    assert normalize_substrate("pi") == "pi"
    assert normalize_substrate("pi-mono") == "pi"
    assert normalize_substrate("pi-coding-agent") == "pi"
    assert normalize_substrate("PI") == "pi"


# -----------------------------------------------------------------------------
# 2. Dual-Track c8 Surface Validation Tests
# -----------------------------------------------------------------------------


def test_surface_dual_track_declarative_hooks():
    valid_hooks = json.dumps(
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": {"tool": "bash"},
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 scripts/check_bash.py",
                            }
                        ],
                    }
                ],
                "PostToolUse": [],
                "SessionStart": [],
            }
        }
    )
    tree = {
        "AGENTS.md": "# Agent Instructions\n",
        ".pi/hooks.json": valid_hooks,
    }
    census = HT.validate(PI_SURFACE, tree)
    assert census["always_on_chars"] > 0
    assert census["hooks"] == 1


def test_surface_dual_track_extensions():
    ts_ext = """// in-process extension
export default function (pi: any) {
  pi.on("tool_call", async (event: any) => {
    return event;
  });
}
"""
    tree = {
        "AGENTS.md": "# Agent Instructions\n",
        ".pi/extensions/guard.ts": ts_ext,
    }
    census = HT.validate(PI_SURFACE, tree)
    assert census["always_on_chars"] > 0
    assert census["plugins"] == 1


def test_surface_dual_track_both_simultaneously():
    tree = {
        "AGENTS.md": "# Dual Track Instructions\n",
        ".pi/hooks.json": '{\n  "hooks": {\n    "Stop": []\n  }\n}\n',
        ".pi/extensions/logger.ts": 'export default function (pi: any) {}',
        "scripts/helper.py": 'print("helper")\n',
    }
    census = HT.validate(PI_SURFACE, tree)
    assert census["hooks"] == 1
    assert census["plugins"] == 1
    assert census["scripts"] == 1


def test_surface_invalid_hook_event_rejected():
    invalid_hooks = json.dumps(
        {
            "hooks": {
                "UnknownEvent": [
                    {
                        "hooks": [
                            {"type": "command", "command": "echo test"}
                        ]
                    }
                ]
            }
        }
    )
    tree = {
        "AGENTS.md": "# Agent Instructions\n",
        ".pi/hooks.json": invalid_hooks,
    }
    with pytest.raises(ValueError, match="unknown event 'UnknownEvent'"):
        HT.validate(PI_SURFACE, tree)


# -----------------------------------------------------------------------------
# 3. Binary Discovery and Configuration Tests
# -----------------------------------------------------------------------------


def test_find_pi_binary_with_env_override(monkeypatch, tmp_path):
    fake_bin = tmp_path / "custom_pi"
    fake_bin.write_text("#!/bin/sh\necho pi\n")
    fake_bin.chmod(0o755)

    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_BIN", str(fake_bin))
    assert find_pi_binary() == fake_bin

    monkeypatch.delenv("SEC_AGENT_HARNESS2_PI_BIN")
    monkeypatch.setenv("HARNESS2_PI_BIN", str(fake_bin))
    assert find_pi_binary() == fake_bin

    monkeypatch.delenv("HARNESS2_PI_BIN")
    wrapper = config.PI_DIST / "bin" / "pi"
    expected = wrapper if (wrapper.is_file() and os.access(wrapper, os.X_OK)) else config.PI_BIN
    assert find_pi_binary() == expected


def test_pi_models_json_camelcase_and_reasoning():
    endpoint = api.Endpoint(
        base_url="https://api.openai.internal/v1",
        api_key="secret-key-123",
        protocol="openai-chat",
        model="gpt-5.4",
    )
    doc_str = api.pi_models_json(endpoint, extra_models=["extra-model-1"])
    doc = json.loads(doc_str)

    provider = doc["providers"][api.PI_PROVIDER]
    assert provider["baseUrl"] == "https://api.openai.internal/v1"
    assert "baseURL" not in provider
    assert provider["apiKey"] == "secret-key-123"
    assert provider["api"] == "openai-completions"

    models = provider["models"]
    model_ids = [m["id"] for m in models]
    assert "gpt-5.4" in model_ids
    assert "extra-model-1" in model_ids
    for m in models:
        assert m["reasoning"] is True
        assert m["maxTokens"] == 64000
        assert m["contextWindow"] == 200000


# -----------------------------------------------------------------------------
# 4. Materialisation and Staging Tests
# -----------------------------------------------------------------------------


def test_pi_materialise_stages_tree_and_runtime_bridge(tmp_path):
    sub = PiSubstrate()
    dummy_ch = ChannelSpec(kind="pi", model="gpt-5.4")
    spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="pi_root",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
        domain_word="test",
        leak_globs=(),
        allow_subagents=True,
    )

    tree_dir = tmp_path / "harness"
    tree_dir.mkdir()
    (tree_dir / "AGENTS.md").write_text("# Pi Harness Rules\n", encoding="utf-8")
    (tree_dir / ".pi").mkdir()
    (tree_dir / ".pi" / "hooks.json").write_text('{"hooks": {"PostToolUse": []}}', encoding="utf-8")
    (tree_dir / "scripts").mkdir()
    (tree_dir / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")

    subagents_dir = tree_dir / "sub_agents" / "scout"
    subagents_dir.mkdir(parents=True)
    (subagents_dir / "AGENT.md").write_text(
        "---\ndescription: Fast scout agent\n---\nFind initial files.\n",
        encoding="utf-8",
    )

    install = sub.materialise(
        tree_dir, spec, {"file:.pi/extensions/logger.ts": "export default function () {}"}
    )
    try:
        staging = install.staging_dir
        assert staging.is_dir()
        assert (staging / "AGENTS.md").read_text(encoding="utf-8") == "# Pi Harness Rules\n"
        assert (staging / ".pi" / "hooks.json").is_file()
        assert (staging / "scripts" / "tool.py").is_file()
        assert (staging / ".pi" / "extensions" / "logger.ts").is_file()
        assert (staging / "sub_agents" / "scout" / "AGENT.md").is_file()

        # Bridge extension auto-generated because sub_agents exist
        bridge_file = staging / "_pi_runtime" / "harness2_bridge.ts"
        assert bridge_file.is_file()
        bridge_text = bridge_file.read_text(encoding="utf-8")
        assert "findHarnessRoot" in bridge_text
        assert "subagent" in bridge_text
    finally:
        shutil.rmtree(install.staging_dir, ignore_errors=True)


def test_pi_materialise_invalid_mode(tmp_path):
    sub = PiSubstrate()
    dummy_ch = ChannelSpec(kind="pi", model="gpt-5.4")
    spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="workspace_config",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
    )
    tree_dir = tmp_path / "tree"
    tree_dir.mkdir()
    (tree_dir / "AGENTS.md").write_text("ok")
    with pytest.raises(ValueError, match="is not valid for PiSubstrate"):
        sub.materialise(tree_dir, spec, {})


# -----------------------------------------------------------------------------
# 5. Exec Argv & Exec Env Tests
# -----------------------------------------------------------------------------


def test_pi_exec_argv(tmp_path):
    sub = PiSubstrate()
    ws = tmp_path / "workspace"
    ws.mkdir()
    bridge_dir = ws / "_pi_runtime"
    bridge_dir.mkdir()
    (bridge_dir / "harness2_bridge.ts").write_text("// bridge")

    argv = sub.exec_argv(
        "Run task prompt",
        ws,
        "sec_agent_harness2/gpt-5.4",
        effort="medium",
        harness_dir=ws,
    )
    assert "-p" in argv
    assert "Run task prompt" in argv
    assert "--mode" in argv and "json" in argv
    assert "--no-session" in argv
    assert "--tools" in argv and PI_BUILTIN_TOOLS in argv
    assert "--provider" in argv and "sec_agent_harness2" in argv
    assert "--model" in argv and "gpt-5.4" in argv
    assert "--thinking" in argv and "medium" in argv
    assert "-e" in argv and str(bridge_dir / "harness2_bridge.ts") in argv


def test_pi_exec_env(tmp_path, monkeypatch):
    sub = PiSubstrate()
    agent_dir = tmp_path / "agent_dir"

    fake_ep = api.Endpoint(
        base_url="https://proxy.test/v1",
        api_key="test-api-key",
        protocol="openai-chat",
        model="gpt-5.4",
    )
    monkeypatch.setattr(api, "pi", lambda for_container=False: fake_ep)

    env = sub.exec_env(
        {"EXISTING_VAR": "keep_me"},
        workspace=tmp_path / "ws",
        model="custom-provider/my-model",
        agent_dir=agent_dir,
    )
    assert env["EXISTING_VAR"] == "keep_me"
    assert env["PI_OFFLINE"] == "1"
    assert env["PI_SKIP_VERSION_CHECK"] == "1"
    assert env["PI_TELEMETRY"] == "0"
    assert env["PI_CODING_AGENT_DIR"] == str(agent_dir)
    assert env["SEC_AGENT_HARNESS2_PI_PROVIDER"] == "custom-provider"
    assert env["SEC_AGENT_HARNESS2_PI_ACTIVE_MODEL"] == "my-model"
    assert (agent_dir / "models.json").is_file()


# -----------------------------------------------------------------------------
# 6. Trajectory Event Stream Parsing Tests
# -----------------------------------------------------------------------------


def test_pi_trajectory_parsing_and_rendering(tmp_path):
    stream_file = tmp_path / "session.jsonl"
    events = [
        {"type": "session", "id": "sess_123"},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let's first inspect directory contents."},
                    {
                        "type": "toolCall",
                        "name": "bash",
                        "arguments": {"command": "ls -la"},
                    },
                ],
                "usage": {
                    "input": 120,
                    "output": 45,
                    "cacheRead": 30,
                    "cost": {"total": 0.0015},
                },
            },
        },
        {
            "type": "tool_execution_end",
            "toolName": "bash",
            "isError": False,
            "result": {
                "content": [
                    {"type": "text", "text": "total 4\n-rw-r--r-- 1 user 10 TASK_INSTRUCTIONS.txt"}
                ]
            },
        },
        {
            "type": "auto_retry_start",
            "attempt": 1,
            "maxAttempts": 3,
            "errorMessage": "Rate limit backoff",
        },
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "The task instructions are loaded successfully."}
                ],
                "stopReason": "endTurn",
            },
        },
    ]

    with open(stream_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    items = parse_items(stream_file)
    assert len(items) >= 5

    kinds = [it["kind"] for it in items]
    assert "thinking" in kinds
    assert "action" in kinds
    assert "usage" in kinds
    assert "observation" in kinds
    assert "retry" in kinds
    assert "deliverable" in kinds

    rendered = render_events(stream_file)
    assert "[THINKING] Let's first inspect directory contents." in rendered
    assert "[ACTION] bash: ls -la" in rendered
    assert "[OBSERVATION] total 4" in rendered
    assert "[HARNESS] turn completed | tokens in=120 out=45 cache_read=30 cost=$0.0015" in rendered
    assert "[HARNESS] auto_retry 1/3: Rate limit backoff" in rendered
    assert "[DELIVERABLE] The task instructions are loaded successfully." in rendered

    final_txt = final_message(stream_file)
    assert final_txt == "The task instructions are loaded successfully."


def test_pi_trajectory_empty_or_broken(tmp_path):
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")
    assert parse_items(empty_file) == []
    assert render_events(empty_file) == ""
    assert final_message(empty_file) == ""

    corrupted_file = tmp_path / "corrupted.jsonl"
    corrupted_file.write_text("invalid json\n{truncated\n")
    assert parse_items(corrupted_file) == []
    assert render_events(corrupted_file) == ""


# -----------------------------------------------------------------------------
# 7. Proposer Channel Integration Tests
# -----------------------------------------------------------------------------


def test_proposer_pi_cost_and_stdout():
    stream = """{"type": "session"}
{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "Proposed mutation #1"}], "usage": {"cost": {"total": 0.0042}}}}
{"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "Final recommendation."}], "usage": {"cost": {"total": 0.0018}}}}
"""
    cost = proposer._pi_cost(stream)
    assert round(cost, 4) == 0.0060

    text, err = proposer._pi_stdout(stream)
    assert "Proposed mutation #1" in text
    assert "Final recommendation." in text
    assert err == ""


def test_proposer_pi_channel_invocation(tmp_path, monkeypatch):
    dummy_ch = ChannelSpec(kind="pi", model="sec_agent_harness2/gpt-5.4", effort="high")
    prop = proposer.Proposer(dummy_ch, tmp_path / "cache")

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Generated harness modification proposal"}],
                "usage": {"cost": {"total": 0.0025}},
            },
        }
    )
    mock_run.return_value.stderr = ""
    monkeypatch.setattr(proposer.subprocess, "run", mock_run)

    text, cost, err = prop._pi(tmp_path / "workspace", "Optimize harness prompt", "System rules", 60)
    assert "Generated harness modification proposal" in text
    assert cost == 0.0025
    assert err == ""
    assert mock_run.called
    cmd_called = mock_run.call_args[0][0]
    assert "--provider" in cmd_called
    assert "sec_agent_harness2" in cmd_called
    assert "--model" in cmd_called
    assert "gpt-5.4" in cmd_called
    assert "--thinking" in cmd_called
    assert "high" in cmd_called


# -----------------------------------------------------------------------------
# 8. MCP Configuration Generation Tests
# -----------------------------------------------------------------------------


def test_pi_mcp_config_generation(tmp_path):
    harness_dir = tmp_path / "harness"
    (harness_dir / "mcp").mkdir(parents=True)
    mcp_servers = {
        "mcpServers": {
            "vuln_scanner": {
                "command": "python3",
                "args": ["mcp/vuln_scanner.py"],
                "env": {"DEBUG": "1"},
            }
        }
    }
    (harness_dir / "mcp" / "servers.json").write_text(json.dumps(mcp_servers), encoding="utf-8")

    cfg_str = mcp_config_json(harness_dir)
    cfg = json.loads(cfg_str)
    assert "vuln_scanner" in cfg["mcpServers"]
    srv = cfg["mcpServers"]["vuln_scanner"]
    assert srv["command"] == "python3"
    assert srv["args"] == ["mcp/vuln_scanner.py"]
    assert srv["env"]["DEBUG"] == "1"


# -----------------------------------------------------------------------------
# 9. Adapter Creation Tests
# -----------------------------------------------------------------------------


def test_make_adapter_jb_pi():
    adapter = make_adapter("jb", None, "pi")
    assert adapter.substrate.name == "pi"
    assert isinstance(adapter.substrate, PiSubstrate)


def test_make_adapter_lab_pi():
    adapter = make_adapter("lab", None, "pi")
    assert adapter.substrate.name == "pi"
    assert isinstance(adapter.substrate, PiSubstrate)


def test_make_adapter_wb_pi():
    adapter = make_adapter("wb", "office", "pi")
    assert adapter.substrate.name == "pi"
    assert isinstance(adapter.substrate, PiSubstrate)


def test_config_validate_models_pi(monkeypatch):
    monkeypatch.setattr(config, "SOLVER_MODEL_PI", "custom-pi-model")
    monkeypatch.setattr(config, "SOLVER_MODEL_OC", "")
    config.validate_models(substrate="pi")

    monkeypatch.setattr(config, "SOLVER_MODEL_PI", "")
    with pytest.raises(config.ConfigError, match="SEC_AGENT_HARNESS2_PI_MODEL is required"):
        config.validate_models(substrate="pi")


def test_materialise_includes_mcp_json(tmp_path):
    sub = PiSubstrate()
    dummy_ch = ChannelSpec(kind="pi", model="gpt-5.4")
    spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="pi_root",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
    )
    tree_dir = tmp_path / "tree"
    tree_dir.mkdir()
    (tree_dir / "AGENTS.md").write_text("# Agents")
    (tree_dir / ".mcp.json").write_text('{"mcpServers": {"demo": {}}}')

    install = sub.materialise(tree_dir, spec, {})
    try:
        assert (install.staging_dir / ".mcp.json").is_file()
    finally:
        shutil.rmtree(install.staging_dir, ignore_errors=True)

