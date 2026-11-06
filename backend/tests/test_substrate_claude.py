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

"""Unit tests for ClaudeSubstrate (clawgod distribution)."""

import json
from pathlib import Path

import pytest

from sec_agent_harness2.cli._common import make_adapter, normalize_substrate
from sec_agent_harness2.core import tree as HT
from sec_agent_harness2.core.spec import BenchSpec
from sec_agent_harness2.substrate.base import Substrate
from sec_agent_harness2.substrate.claude import (
    CLAUDE_SURFACE,
    ClaudeSubstrate,
    find_claude_binary,
    render_events,
)


def test_claude_surface_spec():
    assert CLAUDE_SURFACE.name == "claude"
    assert CLAUDE_SURFACE.always_on == ("CLAUDE.md",)
    assert CLAUDE_SURFACE.always_on_max == 24_000
    assert CLAUDE_SURFACE.skill_dir == ".claude/skills"
    assert CLAUDE_SURFACE.hooks_file == ".claude/settings.json"


def test_substrate_protocol_compliance():
    sub = ClaudeSubstrate()
    assert isinstance(sub, Substrate)
    assert sub.name == "claude"
    assert sub.surface() == CLAUDE_SURFACE


def test_find_claude_binary(monkeypatch, tmp_path):
    fake_bin = tmp_path / "clawgod"
    fake_bin.write_text("#!/bin/sh\necho clawgod\n")
    fake_bin.chmod(0o755)

    monkeypatch.setenv("SEC_AGENT_HARNESS2_CLAWGOD_PATH", str(fake_bin))
    found = find_claude_binary()
    assert found == fake_bin

    monkeypatch.delenv("SEC_AGENT_HARNESS2_CLAWGOD_PATH", raising=False)
    from sec_agent_harness2 import config
    assert find_claude_binary() == config.CLAUDE_BIN


def test_materialise(tmp_path):
    sub = ClaudeSubstrate()
    from sec_agent_harness2.core.spec import ChannelSpec
    dummy_ch = ChannelSpec(kind="claude_cli", model="claude-3-7-sonnet-20250219")
    spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="claude_root",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
        domain_word="test",
        leak_globs=(),
        allow_subagents=True,
    )

    tree_dir = tmp_path / "harness"
    tree_dir.mkdir()
    (tree_dir / "CLAUDE.md").write_text("# Claude Harness Rules\n", encoding="utf-8")
    scripts_dir = tree_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "helper.py").write_text("print('hello')\n", encoding="utf-8")

    install = sub.materialise(tree_dir, spec, {"file:.claude/settings.json": '{"hooks": {}}'})
    try:
        assert install.staging_dir.is_dir()
        assert (install.staging_dir / "CLAUDE.md").read_text(encoding="utf-8") == "# Claude Harness Rules\n"
        assert (install.staging_dir / "scripts" / "helper.py").is_file()
        assert (install.staging_dir / ".claude" / "settings.json").is_file()
        assert install.extras["install_mode"] == "claude_root"
    finally:
        import shutil
        shutil.rmtree(install.staging_dir, ignore_errors=True)


def test_exec_argv():
    sub = ClaudeSubstrate()
    ws = Path("/tmp/mock_ws")
    argv = sub.exec_argv("Do task 1", ws, "claude-3-7-sonnet-20250219", effort="high")
    assert "-p" in argv
    assert "Do task 1" in argv
    assert "--output-format=stream-json" in argv
    assert "--dangerously-skip-permissions" in argv
    assert "--include-hook-events" in argv
    assert "--forward-subagent-text" in argv
    assert "--model" in argv
    assert "claude-3-7-sonnet-20250219" in argv
    assert "--effort" in argv
    assert "high" in argv
    assert "--add-dir" in argv
    assert str(ws) in argv
    # no staged tree -> no --agents flag
    assert "--agents" not in argv


def test_exec_argv_agents_wiring(tmp_path):
    import json as _json

    from sec_agent_harness2.substrate.claude import agents_json

    staged = tmp_path / "staged"
    (staged / "sub_agents" / "researcher").mkdir(parents=True)
    (staged / "sub_agents" / "researcher" / "AGENT.md").write_text(
        "---\ndescription: Deep research agent\n---\nYou research things.\n",
        encoding="utf-8",
    )
    payload = agents_json(staged)
    assert payload
    assert _json.loads(payload)["researcher"]["description"] == "Deep research agent"
    # empty tree -> empty string, no flag emitted
    assert agents_json(tmp_path / "nonexistent") == ""

    sub = ClaudeSubstrate()
    argv = sub.exec_argv("task", Path("/tmp/ws"), "m", harness_dir=staged)
    assert "--agents" in argv

    argv2 = sub.exec_argv("task", Path("/tmp/ws"), "m")
    assert "--agents" not in argv2


def test_render_forwarded_subagent(tmp_path):
    stream_file = tmp_path / "sub.jsonl"
    events = [
        {
            "type": "assistant",
            "parent_tool_use_id": "call_9",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "subagent reporting"}],
            },
        },
    ]
    with open(stream_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    rendered = render_events(stream_file, obs_trunc=1000, max_chars=10_000)
    assert "[SUBAGENT ASSISTANT] subagent reporting" in rendered


def test_trajectory_rendering(tmp_path):
    stream_file = tmp_path / "claude_stream.jsonl"
    events = [
        {"type": "system", "subtype": "init", "model": "claude-3-7-sonnet"},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let's inspect the files first."},
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "Bash",
                        "input": {"command": "ls -la"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "file1.txt\nfile2.txt",
                        "is_error": False,
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "I see file1 and file2."}],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "result": "Task finished successfully.",
            "usage": {"input_tokens": 500, "output_tokens": 120, "cache_read_input_tokens": 50},
        },
    ]

    with open(stream_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    rendered = render_events(stream_file, obs_trunc=1000, max_chars=10_000)
    assert "[THINKING] Let's inspect the files first." in rendered
    assert "[ACTION] Bash: ls -la" in rendered
    assert "[OBSERVATION] file1.txt\nfile2.txt" in rendered
    assert "[ASSISTANT] I see file1 and file2." in rendered
    assert "[HARNESS] turn completed | tokens in=500 out=120 cache_read=50" in rendered
    assert "[DELIVERABLE] Task finished successfully." in rendered


def test_benchmark_adapters_claude_support():
    assert normalize_substrate("claude") == "claude"
    assert normalize_substrate("cl") == "claude"
    assert normalize_substrate("clawgod") == "claude"

    # JobBench
    jb = make_adapter("jb", None, "claude")
    assert jb.substrate.name == "claude"
    assert jb.spec.install_mode == "claude_root"

    # WorkBuddy
    wb = make_adapter("wb", "office", "claude")
    assert wb.substrate.name == "claude"
    assert wb.spec.install_mode == "claude_root"

    # Lab
    lab = make_adapter("lab", None, "claude")
    assert lab.substrate.name == "claude"
    assert lab.spec.install_mode == "claude_root"


def test_lab_claude_run_dir_preserves_nested_hierarchy(tmp_path):
    import importlib.util

    from sec_agent_harness2 import config

    runner_py = config.THIRD_PARTY / "lab_runner" / "adapt_runs_claude" / "run_claude_lab.py"
    spec = importlib.util.spec_from_file_location("_test_run_claude_lab", runner_py)
    mod = importlib.util.module_from_spec(spec)
    # Stub external.tts_lab before executing module
    import sys
    import types
    fake_ext = types.ModuleType("external")
    fake_tts = types.ModuleType("external.tts_lab")
    fake_tts.config = types.SimpleNamespace()
    sys.modules.setdefault("external", fake_ext)
    sys.modules.setdefault("external.tts_lab", fake_tts)
    spec.loader.exec_module(mod)

    run_id = "lab-claude-agg1/antitrust-competition__task1/b1"
    resolved = mod.run_dir_for(run_id, results_root=tmp_path)
    assert resolved == (tmp_path / run_id).resolve()

    with pytest.raises(SystemExit):
        mod.run_dir_for("../escape", results_root=tmp_path)


def test_workbuddy_claude_job_yaml_mounts_and_env(tmp_path, monkeypatch):
    from sec_agent_harness2.benchmarks.workbuddy import SUBSETS, _job_yaml

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.anthropic.proxy/v1")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token")
    ws = tmp_path / "ws"
    ws.mkdir()
    yml = _job_yaml(
        SUBSETS["code"],
        "claude",
        "wb-code-claude-agg1",
        ["task-1"],
        ws,
        1,
        tmp_path / "jobs",
    )
    assert "target: /opt/claude" in yml
    assert "host.docker.internal" in yml
    assert "host.docker.internal:host-gateway" in yml
    assert "WB_HARNESS_WS" in yml
    assert "ANTHROPIC_BASE_URL" in yml


def test_workbuddy_codex_job_yaml_structure(monkeypatch, tmp_path):
    from sec_agent_harness2.benchmarks.workbuddy import SUBSETS, _job_yaml

    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-gateway.example.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "shared-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")

    fake_dep = tmp_path / "dependencies" / "codex"
    fake_dep.mkdir(parents=True, exist_ok=True)
    bridge_json = fake_dep / "responses-bridge.json"
    bridge_json.write_text(json.dumps({"port": 8765, "key": "codex-bridge-key"}), encoding="utf-8")
    from sec_agent_harness2 import api
    monkeypatch.setattr(api.config, "DEPENDENCIES", tmp_path / "dependencies")

    ws = tmp_path / "ws"
    ws.mkdir()
    yml = _job_yaml(
        SUBSETS["code"],
        "cx",
        "wb-code-cx-agg1",
        ["task-1"],
        ws,
        1,
        tmp_path / "jobs",
    )
    assert "target: /opt/codex" in yml
    assert "host.docker.internal:host-gateway" in yml
    assert "http://host.docker.internal:8765/v1" in yml
    assert "codex-bridge-key" in yml


def test_codex_substrate_preflight_auto_probes_and_heals(monkeypatch, tmp_path):
    from sec_agent_harness2.substrate.codex import CodexSubstrate
    from sec_agent_harness2 import api, install

    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-gateway.upstream.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "upstream-secret-key")
    monkeypatch.delenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", raising=False)

    fake_dep = tmp_path / "dependencies"
    fake_codex_dist = fake_dep / "codex" / "dist"
    fake_codex_dist.mkdir(parents=True, exist_ok=True)
    fake_bin = fake_codex_dist / "codex"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    fake_codex_home = fake_dep / "codex" / "home"

    monkeypatch.setattr(api.config, "DEPENDENCIES", fake_dep)
    monkeypatch.setattr(install.config, "DEPENDENCIES", fake_dep)
    monkeypatch.setattr(install.config, "CODEX_DIST", fake_codex_dist)
    monkeypatch.setattr(install.config, "CODEX_HOME_DIR", fake_codex_home)

    from sec_agent_harness2.substrate import codex as codex_mod
    monkeypatch.setattr(codex_mod.config, "DEPENDENCIES", fake_dep)
    monkeypatch.setattr(codex_mod.config, "CODEX_DIST", fake_codex_dist)

    calls = {"probed": 0, "ensured": 0}

    def fake_probe(url, key, timeout=8.0):
        calls["probed"] += 1
        return {"wire_mode": "bridge", "status_code": 404, "message": "Bridge managed"}

    monkeypatch.setattr(api, "probe_upstream_responses_capability", fake_probe)

    from sec_agent_harness2.cli import responses_bridge
    def fake_ensure(*args, **kwargs):
        calls["ensured"] += 1
        return {"port": 8765, "key": "bridge-token-auto", "wire_mode": "bridge"}

    monkeypatch.setattr(responses_bridge, "ensure_bridge_running", fake_ensure)

    # Mock socket.create_connection so it doesn't fail on mock port
    import socket
    from unittest.mock import MagicMock
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: MagicMock())

    sub = CodexSubstrate()
    sub.preflight()

    # Verify: Probe was invoked because wire_mode was unset
    assert calls["probed"] == 1
    # Verify: Bridge was ensured
    assert calls["ensured"] == 1
    # Verify: config.toml was auto-healed and created
    assert (fake_codex_home / "config.toml").is_file()
    assert install.codex_config_error(home_dir=fake_codex_home) is None


def test_jobbench_codex_exec_env_receives_bridge_key(monkeypatch, tmp_path):
    from sec_agent_harness2.substrate.codex import CodexSubstrate
    from sec_agent_harness2 import api

    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_BASE_URL", "https://chat-gateway.upstream.com/v1")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_API_KEY", "upstream-secret-key")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_CODEX_WIRE_MODE", "bridge")

    fake_dep = tmp_path / "dependencies"
    fake_bridge = fake_dep / "codex" / "responses-bridge.json"
    fake_bridge.parent.mkdir(parents=True, exist_ok=True)
    fake_bridge.write_text(json.dumps({"port": 8765, "key": "bridge-token-expected"}), encoding="utf-8")

    monkeypatch.setattr(api.config, "DEPENDENCIES", fake_dep)

    from sec_agent_harness2.substrate import codex as codex_mod
    monkeypatch.setattr(codex_mod.config, "DEPENDENCIES", fake_dep)

    sub = CodexSubstrate()
    # Simulate base_env that already has old VERTEX_PROXY_KEY from .env
    base_env = {"VERTEX_PROXY_KEY": "upstream-secret-key", "PATH": "/usr/bin"}
    env = sub.exec_env(base_env, codex_home=tmp_path / "home")

    # Crucial assertion: Must receive the bridge token, NOT the upstream secret!
    assert env["VERTEX_PROXY_KEY"] == "bridge-token-expected"


def test_claude_prompt_surface_and_subagent_rules(tmp_path):
    from sec_agent_harness2.core import context, prompts
    from sec_agent_harness2.core import tree as HT
    from sec_agent_harness2.core.spec import BenchPrompts
    from sec_agent_harness2.substrate.claude import CLAUDE_SURFACE

    bp = BenchPrompts(
        work="Produce a legal analysis memo.",
        deliverable_word="deliverable",
        domain_word="practice area",
    )
    for pack in ("adapt", "tts"):
        bp_pack = BenchPrompts(
            work=bp.work,
            deliverable_word=bp.deliverable_word,
            domain_word=bp.domain_word,
            prompt_pack=pack,
        )
        inv_prompt = prompts.propose(bp_pack, "INV", CLAUDE_SURFACE, k=2, index=1)
        dom_prompt = prompts.propose(bp_pack, "DOM", CLAUDE_SURFACE, k=2, index=1)
        agg_prompt = prompts.aggregate(bp_pack, CLAUDE_SURFACE, k=2, index=1)
        seq_prompt = prompts.compose_round(bp_pack, CLAUDE_SURFACE, t=1, k=2)
        for text in (inv_prompt, dom_prompt, agg_prompt, seq_prompt):
            assert "CLAUDE.md" in text
            assert ".claude/skills/" in text
            assert ".claude/settings.json" in text

    # JobBench and WorkBuddy enable subagents on oc & claude, disable on cx; LAB disables on all.
    assert make_adapter("jb", None, "claude").spec.allow_subagents is True
    assert make_adapter("jb", None, "oc").spec.allow_subagents is True
    assert make_adapter("jb", None, "cx").spec.allow_subagents is False
    assert make_adapter("wb", "office", "claude").spec.allow_subagents is True
    assert make_adapter("wb", "office", "cx").spec.allow_subagents is False
    assert make_adapter("lab", None, "claude").spec.allow_subagents is False

    # When allow_subagents=False, write_tree and _copy_tree omit sub_agents/README.md stub.
    h_no_sub = HT.write_tree(
        CLAUDE_SURFACE,
        {"CLAUDE.md": "# Base"},
        tmp_path / "h_no_sub",
        stubs=True,
        allow_subagents=False,
    )
    assert not (h_no_sub / "sub_agents" / "README.md").exists()
    assert (h_no_sub / "scripts" / "README.md").exists()

    h_with_sub = HT.write_tree(
        CLAUDE_SURFACE,
        {"CLAUDE.md": "# Base"},
        tmp_path / "h_with_sub",
        stubs=True,
        allow_subagents=True,
    )
    assert (h_with_sub / "sub_agents" / "README.md").exists()

    copied = tmp_path / "copied_no_sub"
    context._copy_tree(h_with_sub, copied, allow_subagents=False)
    assert not (copied / "sub_agents" / "README.md").exists()


def test_jobbench_claude_runner_prompt_parity():
    from sec_agent_harness2 import config

    cx_runner = (
        config.THIRD_PARTY / "jb_runner" / "run_benchmark_codex_cli_adapt.sh"
    ).read_text(encoding="utf-8")
    claude_runner = (
        config.THIRD_PARTY / "jb_runner" / "run_benchmark_claude_cli_adapt.sh"
    ).read_text(encoding="utf-8")
    for required_fragment in (
        "=== TASK FOLDER ===",
        "=== INSTRUCTIONS ===",
        "1. Read the TASK_INSTRUCTIONS.txt file in the task folder above",
        "4. Only save the final deliverables to the output directory specified below. Do not save any intermediate or temporary files.",
        "If a file cannot be read directly (e.g., .xlsx, .docx, .db, .pptx), use appropriate tools, MCP servers, or code to extract and process its contents.",
    ):
        assert required_fragment in cx_runner
        assert required_fragment in claude_runner


def test_c9_mcp_validation_and_multi_substrate_materialisation(tmp_path):
    from sec_agent_harness2.core.spec import ChannelSpec
    from sec_agent_harness2.substrate.codex import CODEX_SURFACE, CodexSubstrate
    from sec_agent_harness2.substrate.opencode import OPENCODE_SURFACE, OpencodeSubstrate

    for surface in (OPENCODE_SURFACE, CODEX_SURFACE, CLAUDE_SURFACE):
        assert HT.is_allowed(surface, "mcp/servers.json")
        assert HT.is_allowed(surface, "mcp/sec_recon.py")
        assert not HT.is_allowed(surface, "mcp/Invalid-Name.py")

    valid_mcp_json = json.dumps(
        {
            "mcpServers": {
                "sec_recon": {
                    "command": "python3",
                    "args": ["mcp/sec_recon.py"],
                    "env": {"PYTHONUNBUFFERED": "1"},
                },
                "remote_intel": {
                    "url": "https://mcp.example.internal/sse",
                },
            }
        }
    )
    valid_tree = {
        "CLAUDE.md": "# Base Rules\n",
        "mcp/servers.json": valid_mcp_json,
        "mcp/sec_recon.py": "import sys\nprint('ok')\n",
    }
    census = HT.validate(CLAUDE_SURFACE, valid_tree)
    assert census["mcp_servers"] == 2
    assert census["mcp_scripts"] == 1
    assert HT.mcp_server_names(CLAUDE_SURFACE, valid_tree) == ["remote_intel", "sec_recon"]

    # Missing referenced mcp/<name>.py fails validation
    with pytest.raises(ValueError, match="not in the harness"):
        HT.validate(
            CLAUDE_SURFACE,
            {"CLAUDE.md": "# Base\n", "mcp/servers.json": valid_mcp_json},
        )

    # Unregistered mcp/<name>.py without mcp/servers.json fails validation
    with pytest.raises(ValueError, match="require `mcp/servers.json`"):
        HT.validate(
            CLAUDE_SURFACE,
            {"CLAUDE.md": "# Base\n", "mcp/sec_recon.py": "print(1)\n"},
        )

    # Syntax error in mcp/<name>.py fails validation
    with pytest.raises(ValueError, match="does not compile"):
        HT.validate(
            CLAUDE_SURFACE,
            {
                "CLAUDE.md": "# Base\n",
                "mcp/servers.json": valid_mcp_json,
                "mcp/sec_recon.py": "def broken(:\n",
            },
        )

    # Claude materialisation & --mcp-config argv wiring
    dummy_ch = ChannelSpec(kind="claude_cli", model="claude-3-7-sonnet-20250219")
    cl_spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="claude_root",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
    )
    cl_dir = HT.write_tree(CLAUDE_SURFACE, valid_tree, tmp_path / "cl_tree")
    cl_sub = ClaudeSubstrate()
    cl_install = cl_sub.materialise(cl_dir, cl_spec, {})
    try:
        assert (cl_install.staging_dir / ".mcp.json").is_file()
        assert (cl_install.staging_dir / "mcp" / "sec_recon.py").is_file()
        argv = cl_sub.exec_argv("run task", tmp_path, "claude-sonnet-4-6", harness_dir=cl_install.staging_dir)
        assert "--mcp-config" in argv
    finally:
        import shutil
        shutil.rmtree(cl_install.staging_dir, ignore_errors=True)

    # Codex materialisation (.codex/config.toml [mcp_servers.<name>])
    cx_tree = {
        "AGENTS.md": "# Codex Rules\n",
        "mcp/servers.json": valid_mcp_json,
        "mcp/sec_recon.py": "print('ok')\n",
    }
    cx_dir = HT.write_tree(CODEX_SURFACE, cx_tree, tmp_path / "cx_tree")
    cx_spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="codex_root",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
    )
    cx_install = CodexSubstrate().materialise(cx_dir, cx_spec, {})
    try:
        toml_text = (cx_install.staging_dir / ".codex" / "config.toml").read_text(encoding="utf-8")
        assert "[mcp_servers.sec_recon]" in toml_text
        assert "[mcp_servers.remote_intel]" in toml_text
    finally:
        import shutil
        shutil.rmtree(cx_install.staging_dir, ignore_errors=True)

    # OpenCode materialisation (opencode.json `mcp` block & compose_prompt)
    oc_tree = {
        "systemprompt.md": "# OpenCode Rules\n",
        "mcp/servers.json": valid_mcp_json,
        "mcp/sec_recon.py": "print('ok')\n",
    }
    oc_dir = HT.write_tree(OPENCODE_SURFACE, oc_tree, tmp_path / "oc_tree")
    oc_spec = BenchSpec(
        name="test",
        runs_root=tmp_path / "runs",
        install_mode="home_dir_jinja",
        prompts=None,
        channels={"proposer": dummy_ch, "selector": dummy_ch},
    )
    oc_install = OpencodeSubstrate().materialise(oc_dir, oc_spec, {})
    try:
        oc_cfg = json.loads((oc_install.staging_dir / "opencode.json").read_text(encoding="utf-8"))
        assert oc_cfg["mcp"]["sec_recon"]["type"] == "local"
        assert oc_cfg["mcp"]["remote_intel"]["type"] == "remote"
        composed = (oc_install.staging_dir / "_composed" / "prompt.j2").read_text(encoding="utf-8")
        assert "# AVAILABLE MCP SERVERS" in composed
        assert "`sec_recon`" in composed
    finally:
        import shutil
        shutil.rmtree(oc_install.staging_dir, ignore_errors=True)




