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

"""Unit tests for thinking effort support across OpenCode & Pi substrates."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from sec_agent_harness2.substrate.opencode import OpencodeSubstrate
from sec_agent_harness2.benchmarks.jb_opencode_runner import Settings, _command
from sec_agent_harness2.benchmarks.lab import LabAdapter
from sec_agent_harness2.benchmarks.workbuddy import _job_yaml, SUBSETS
from sec_agent_harness2.core.spec import ChannelSpec
from sec_agent_harness2.core.proposer import Proposer
from sec_agent_harness2.ui.server import create_app
from sec_agent_harness2.ui import scanner
from sec_agent_harness2.ui.runner import ExecutionManager


def test_opencode_run_argv_effort_formatting():
    sub = OpencodeSubstrate()
    ws = Path("/tmp/fake_workspace")

    # 1. Non-off variant appends #variant and includes --thinking, excludes --variant
    argv_high = sub.run_argv("prompt", ws, "gemini-2.5-pro", variant="high")
    assert "--model" in argv_high
    model_idx = argv_high.index("--model")
    assert argv_high[model_idx + 1] == "gemini-2.5-pro#high"
    assert "--thinking" in argv_high
    assert "--variant" not in argv_high

    # 2. Existing hash in model is replaced cleanly
    argv_override = sub.run_argv("prompt", ws, "gemini-2.5-pro#low", variant="medium")
    model_idx = argv_override.index("--model")
    assert argv_override[model_idx + 1] == "gemini-2.5-pro#medium"
    assert "--thinking" in argv_override
    assert "--variant" not in argv_override

    # 3. Off variant uses bare model, omits --thinking, excludes --variant (case-insensitive)
    argv_off = sub.run_argv("prompt", ws, "gemini-2.5-pro#high", variant="off")
    model_idx = argv_off.index("--model")
    assert argv_off[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in argv_off
    assert "--variant" not in argv_off

    argv_off_caps = sub.run_argv("prompt", ws, "gemini-2.5-pro#high", variant="OFF")
    model_idx = argv_off_caps.index("--model")
    assert argv_off_caps[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in argv_off_caps
    assert "--variant" not in argv_off_caps

    # 4. Empty / None variant uses base model, omits --thinking, excludes --variant (and strips existing hash)
    argv_none = sub.run_argv("prompt", ws, "gemini-2.5-pro#high", variant=None)
    model_idx = argv_none.index("--model")
    assert argv_none[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in argv_none
    assert "--variant" not in argv_none

    argv_empty = sub.run_argv("prompt", ws, "gemini-2.5-pro#high", variant="")
    model_idx = argv_empty.index("--model")
    assert argv_empty[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in argv_empty
    assert "--variant" not in argv_empty


def test_jb_opencode_runner_command_effort():
    cfg_high = Settings(
        task_ids=("t1",),
        label="test",
        render_dir=Path("/tmp"),
        tasks_base=Path("/tmp"),
        opencode_dir=Path("/opt/opencode"),
        model_id="sec_agent_harness2/gemini-2.5-pro",
        agent_name="",
        variant="high",
        agent_steps="",
        timeout_per_task="300",
        max_retries=2,
        log_dir=Path("/tmp"),
    )
    cmd_high = _command(cfg_high, Path("/tmp/ws"), "prompt", "title")
    assert "--model" in cmd_high
    model_idx = cmd_high.index("--model")
    assert cmd_high[model_idx + 1] == "sec_agent_harness2/gemini-2.5-pro#high"
    assert "--thinking" in cmd_high
    assert "--variant" not in cmd_high

    cfg_off = Settings(
        task_ids=("t1",),
        label="test",
        render_dir=Path("/tmp"),
        tasks_base=Path("/tmp"),
        opencode_dir=Path("/opt/opencode"),
        model_id="sec_agent_harness2/gemini-2.5-pro#high",
        agent_name="",
        variant="OFF",
        agent_steps="",
        timeout_per_task="300",
        max_retries=2,
        log_dir=Path("/tmp"),
    )
    cmd_off = _command(cfg_off, Path("/tmp/ws"), "prompt", "title")
    model_idx = cmd_off.index("--model")
    assert cmd_off[model_idx + 1] == "sec_agent_harness2/gemini-2.5-pro"
    assert "--thinking" not in cmd_off
    assert "--variant" not in cmd_off

    cfg_empty = Settings(
        task_ids=("t1",),
        label="test",
        render_dir=Path("/tmp"),
        tasks_base=Path("/tmp"),
        opencode_dir=Path("/opt/opencode"),
        model_id="sec_agent_harness2/gemini-2.5-pro#high",
        agent_name="",
        variant="",
        agent_steps="",
        timeout_per_task="300",
        max_retries=2,
        log_dir=Path("/tmp"),
    )
    cmd_empty = _command(cfg_empty, Path("/tmp/ws"), "prompt", "title")
    model_idx = cmd_empty.index("--model")
    assert cmd_empty[model_idx + 1] == "sec_agent_harness2/gemini-2.5-pro"
    assert "--thinking" not in cmd_empty
    assert "--variant" not in cmd_empty


def test_proposer_opencode_cmd_assembly(monkeypatch):
    captured_cmds = []

    monkeypatch.setattr("sec_agent_harness2.core.proposer._opencode_dir", lambda: Path("/opt/opencode"))

    def mock_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout = '{"cost": 0.0}'
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        return mock_proc

    monkeypatch.setattr("subprocess.run", mock_run)

    # With effort="medium"
    prop_med = Proposer(ChannelSpec("opencode", "gemini-2.5-pro", effort="medium"))
    out_dir = Path("/tmp/prop_test_med")
    out_dir.mkdir(parents=True, exist_ok=True)
    prop_med._opencode(out_dir, "mission", "system", 60)

    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    # Check entrance path is packages/cli
    cwd_idx = cmd.index("--cwd")
    assert cmd[cwd_idx + 1].endswith("packages/cli")
    # Check model formatting and thinking
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "gemini-2.5-pro#medium"
    assert "--thinking" in cmd
    assert "--variant" not in cmd

    # With effort="OFF" and hash in model
    captured_cmds.clear()
    prop_off = Proposer(ChannelSpec("opencode", "gemini-2.5-pro#high", effort="OFF"))
    out_dir_off = Path("/tmp/prop_test_off")
    out_dir_off.mkdir(parents=True, exist_ok=True)
    prop_off._opencode(out_dir_off, "mission", "system", 60)

    assert len(captured_cmds) == 1
    cmd_off = captured_cmds[0]
    model_idx = cmd_off.index("--model")
    assert cmd_off[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in cmd_off
    assert "--variant" not in cmd_off

    # With effort="" and hash in model
    captured_cmds.clear()
    prop_empty = Proposer(ChannelSpec("opencode", "gemini-2.5-pro#high", effort=""))
    out_dir_empty = Path("/tmp/prop_test_empty")
    out_dir_empty.mkdir(parents=True, exist_ok=True)
    prop_empty._opencode(out_dir_empty, "mission", "system", 60)

    assert len(captured_cmds) == 1
    cmd_empty = captured_cmds[0]
    model_idx = cmd_empty.index("--model")
    assert cmd_empty[model_idx + 1] == "gemini-2.5-pro"
    assert "--thinking" not in cmd_empty
    assert "--variant" not in cmd_empty


def test_lab_adapter_env_passthrough(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_VARIANT", "low")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_EFFORT", "medium")

    adapter_oc = LabAdapter(substrate="oc")
    assert adapter_oc.solver_effort == "low"

    adapter_pi = LabAdapter(substrate="pi")
    assert adapter_pi.solver_effort == "medium"

    # Explicit override takes precedence
    adapter_explicit = LabAdapter(substrate="oc", solver_effort="high")
    assert adapter_explicit.solver_effort == "high"


def test_workbuddy_docker_yaml_passthrough(monkeypatch):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_PI_EFFORT", "low")
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_VARIANT", "medium")

    yaml_pi = _job_yaml(SUBSETS["office"], "pi", "label_pi", ["t1"], None, 1, Path("/tmp/wb_jobs"))
    assert 'PI_EFFORT: "low"' in yaml_pi

    yaml_oc = _job_yaml(SUBSETS["office"], "oc", "label_oc", ["t1"], None, 1, Path("/tmp/wb_jobs"))
    assert 'OPENCODE_VARIANT: "medium"' in yaml_oc


def test_scanner_oc_effort_field(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_AGENT_HARNESS2_OPENCODE_VARIANT", "medium")
    status = scanner.get_executors_status(tmp_path)
    oc_item = next(e for e in status["executors"] if e["id"] == "oc")
    assert oc_item["effort"] == "medium"


@pytest.mark.asyncio
async def test_server_executor_config_and_sweep(tmp_path, monkeypatch):
    app = create_app(tmp_path, runs_root=tmp_path / "runs")
    client = TestClient(app)

    # 1. Test POST /api/executors/config for oc
    res_oc = client.post("/api/executors/config", json={
        "executor_id": "oc",
        "effort": "low",
        "persist_dotenv": False,
    })
    assert res_oc.status_code == 200
    assert os.environ.get("SEC_AGENT_HARNESS2_OPENCODE_VARIANT") == "low"

    # 2. Test POST /api/executors/config for unified with oc_variant
    res_unified = client.post("/api/executors/config", json={
        "executor_id": "unified",
        "model": "gpt-4o",
        "effort": "high",
        "oc_variant": "medium",
        "persist_dotenv": False,
    })
    assert res_unified.status_code == 200
    assert os.environ.get("SEC_AGENT_HARNESS2_PI_EFFORT") == "high"
    assert os.environ.get("SEC_AGENT_HARNESS2_OPENCODE_VARIANT") == "medium"

    # 3. Test POST /api/execute/sweep with oc substrate
    mock_start = MagicMock()
    async def mock_start_job(*args, **kwargs):
        mock_start(*args, **kwargs)
        return {"job_id": "test_1", "status": "running"}

    monkeypatch.setattr(ExecutionManager, "start_job", mock_start_job)

    res_sweep = client.post("/api/execute/sweep", json={
        "bench": "jb",
        "substrate": "oc",
        "effort": "low",
    })
    assert res_sweep.status_code == 200
    # Check extra_env passed to start_job
    _, kwargs = mock_start.call_args
    assert kwargs["extra_env"]["SEC_AGENT_HARNESS2_OPENCODE_VARIANT"] == "low"


@pytest.mark.asyncio
async def test_oc_agent_command_assembly():
    import sys
    from unittest.mock import MagicMock
    from importlib.machinery import ModuleSpec

    class MockImporter:
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith("harbor") or fullname.startswith("workbuddy_bench"):
                return ModuleSpec(fullname, self)
            return None

        def create_module(self, spec):
            m = MagicMock()
            m.__path__ = []
            m.BaseInstalledAgent = type("BaseInstalledAgent", (), {})
            m.BaseEnvironment = type("BaseEnvironment", (), {})
            return m

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, MockImporter())
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "third_party" / "wb_runner"))
    from agents.oc_agent import OcAgent

    executed_cmds = []
    class DummyEnv:
        pass

    agent_high = object.__new__(OcAgent)
    agent_high._variant = "high"
    agent_high._max_output_tokens = None
    async def mock_exec_high(env, command):
        executed_cmds.append(command)
    agent_high.exec_as_agent = mock_exec_high

    await agent_high._run_opencode(DummyEnv(), "cfg", model_arg="sec_agent_harness2/gemini-2.5-pro", escaped_instruction="task")
    assert len(executed_cmds) == 2
    run_cmd_high = executed_cmds[1]
    assert "--model 'sec_agent_harness2/gemini-2.5-pro#high'" in run_cmd_high
    assert "--thinking" in run_cmd_high
    assert "--variant" not in run_cmd_high

    executed_cmds.clear()
    agent_off = object.__new__(OcAgent)
    agent_off._variant = "OFF"
    agent_off._max_output_tokens = None
    agent_off.exec_as_agent = mock_exec_high

    await agent_off._run_opencode(DummyEnv(), "cfg", model_arg="sec_agent_harness2/gemini-2.5-pro#high", escaped_instruction="task")
    assert len(executed_cmds) == 2
    run_cmd_off = executed_cmds[1]
    assert "--model sec_agent_harness2/gemini-2.5-pro" in run_cmd_off
    assert "--thinking" not in run_cmd_off
    assert "--variant" not in run_cmd_off

    executed_cmds.clear()
    agent_empty = object.__new__(OcAgent)
    agent_empty._variant = ""
    agent_empty._max_output_tokens = None
    agent_empty.exec_as_agent = mock_exec_high

    await agent_empty._run_opencode(DummyEnv(), "cfg", model_arg="sec_agent_harness2/gemini-2.5-pro#high", escaped_instruction="task")
    assert len(executed_cmds) == 2
    run_cmd_empty = executed_cmds[1]
    assert "--model sec_agent_harness2/gemini-2.5-pro" in run_cmd_empty
    assert "--thinking" not in run_cmd_empty
    assert "--variant" not in run_cmd_empty


def test_pi_substrate_effort_off_handling():
    from sec_agent_harness2.substrate.pi import PiSubstrate

    pi_sub = PiSubstrate()
    ws = Path("/tmp/fake_pi_ws")

    argv_high = pi_sub.exec_argv("prompt", ws, "gpt-5.4", effort="high")
    assert "--thinking" in argv_high
    assert argv_high[argv_high.index("--thinking") + 1] == "high"

    argv_off = pi_sub.exec_argv("prompt", ws, "gpt-5.4", effort="off")
    assert "--thinking" not in argv_off

    argv_off_caps = pi_sub.exec_argv("prompt", ws, "gpt-5.4", effort="OFF")
    assert "--thinking" not in argv_off_caps

    argv_empty = pi_sub.exec_argv("prompt", ws, "gpt-5.4", effort="")
    assert "--thinking" not in argv_empty


def test_opencode_config_strips_model_hash(monkeypatch):
    from sec_agent_harness2.api import Endpoint, opencode_config

    ep = Endpoint(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        model="sec_agent_harness2/gemini-2.5-pro#high",
        protocol="openai-chat",
    )
    cfg_json = opencode_config(ep)
    parsed = json.loads(cfg_json)
    models = parsed["provider"]["sec_agent_harness2"]["models"]
    assert "gemini-2.5-pro" in models
    assert "gemini-2.5-pro#high" not in models
    model_obj = models["gemini-2.5-pro"]
    assert model_obj["capabilities"]["reasoning"]["supported"] is True
    assert model_obj["capabilities"]["reasoning"]["effort"] == ["low", "medium", "high"]

