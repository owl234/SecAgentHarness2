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

"""Deployment settings and dependency versions. Shell values override .env."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent


def _resolve_root() -> Path:
    if (PKG.parent.parent / "third_party").is_dir() or (PKG.parent.parent / ".env.example").is_file():
        return PKG.parent.parent
    if (PKG.parent / "pyproject.toml").is_file():
        return PKG.parent
    return Path.cwd()


ROOT = _resolve_root()
THIRD_PARTY = ROOT / "third_party"
METHOD_VERSION = 2

DEPENDENCIES = ROOT / "dependencies"


class ConfigError(RuntimeError):
    """A required deployment value is missing; the message carries the remediation."""


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load KEY=VALUE lines from `path` into os.environ with setdefault (the shell wins).

    Accepts blank lines, `#` comments, an optional `export ` prefix, and single- or
    double-quoted values. A missing or unreadable file is not an error.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not all(c.isalnum() or c == "_" for c in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)


load_dotenv()


def env(name: str, default=None):
    """Env override where a set-but-empty variable is the same as an unset one.

    Supports bidirectional fallback between SEC_AGENT_HARNESS2_* and legacy HARNESS2_*.
    """
    v = os.environ.get(name)
    if not v:
        if name.startswith("SEC_AGENT_HARNESS2_"):
            legacy_name = "HARNESS2_" + name[len("SEC_AGENT_HARNESS2_") :]
            v = os.environ.get(legacy_name)
        elif name.startswith("HARNESS2_"):
            new_name = "SEC_AGENT_HARNESS2_" + name[len("HARNESS2_") :]
            v = os.environ.get(new_name)
    return v or default


def env_int(name: str, default: int) -> int:
    v = env(name)
    if v is None:
        return int(default)
    try:
        return int(v)
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer, got {v!r}") from e


def require(name: str, *, needed_by: str) -> str:
    """The value of `name`, or ConfigError with the remediation line when it is unset/empty."""
    v = env(name)
    if not v:
        raise ConfigError(
            f"{name} is required for {needed_by}; set it in .env or the shell (see .env.example)"
        )
    return str(v)


RUNS = Path(env("SEC_AGENT_HARNESS2_RUNS_DIR", ROOT / "runs")).expanduser().resolve()
VERTEX_PROJECT = env("GOOGLE_CLOUD_PROJECT", env("SEC_AGENT_HARNESS2_VERTEX_PROJECT", ""))
VERTEX_REGION = env("GOOGLE_CLOUD_LOCATION", "global")
if VERTEX_PROJECT:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", VERTEX_PROJECT)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", VERTEX_REGION)


# One endpoint and key can drive all three substrates; see sec_agent_harness2/api.py for the
# per-substrate protocol mapping. The per-substrate variables still win.
API_BASE_URL = env("SEC_AGENT_HARNESS2_API_BASE_URL", "")
API_KEY = env("SEC_AGENT_HARNESS2_API_KEY", "")
API_MODEL = env("SEC_AGENT_HARNESS2_API_MODEL", "")


def _solver_model_oc() -> str:
    """The executor model in OpenCode's `provider/model` form.

    A shared endpoint owns its own provider id (`sec_agent_harness2/`), so a bare
    SEC_AGENT_HARNESS2_API_MODEL is qualified here rather than at every call site.
    """
    explicit = env("SEC_AGENT_HARNESS2_SOLVER_MODEL", "")
    if explicit or not API_MODEL:
        return explicit
    return f"sec_agent_harness2/{API_MODEL}" if API_BASE_URL else API_MODEL


SOLVER_MODEL_OC = _solver_model_oc()
SOLVER_MODEL_CX = env("SEC_AGENT_HARNESS2_CODEX_MODEL", SOLVER_MODEL_OC.removeprefix("sec_agent_harness2/"))
SOLVER_MODEL_CLAUDE = env("SEC_AGENT_HARNESS2_CLAUDE_MODEL", API_MODEL or "claude-3-7-sonnet-20250219")
IMPROVER_MODEL = env("SEC_AGENT_HARNESS2_IMPROVER_MODEL", SOLVER_MODEL_OC)
JUDGE_MODEL = env("SEC_AGENT_HARNESS2_JUDGE_MODEL", API_MODEL)

DEPENDENCY_PINS = {
    "job-bench-eval": "fa03a17f9ff662f136798a274e10011c3aa00fd0",
    "workbuddy-bench": "b516950be5b56eb3be406c2f76ee1c5111dcb57f",
    "harvey-labs": "b58a28ae9fde5ee4b810e53b4fd0a1915325a35d",
    "opencode": "23fb5e0516c99ac04a1aa46c193efda2e1b9bb24",
}
DEPENDENCY_ORIGINS = {
    "job-bench-eval": "https://github.com/Job-Bench/job-bench-eval.git",
    "workbuddy-bench": "https://github.com/Tencent/workbuddy-bench.git",
    "harvey-labs": "https://github.com/harveyai/harvey-labs.git",
    "opencode": "https://github.com/anomalyco/opencode.git",
}


def jb_repo() -> Path:
    return DEPENDENCIES / "job-bench-eval"


def wb_repo() -> Path:
    return DEPENDENCIES / "workbuddy-bench"


def lab_repo() -> Path:
    return DEPENDENCIES / "harvey-labs"


OPENCODE_DIR = DEPENDENCIES / "opencode"
BUN = DEPENDENCIES / "tools" / "node_modules" / ".bin" / "bun"
LAB_PYTHON = lab_repo() / ".venv" / "bin" / "python"
LAB_JUDGE_MODEL = (
    "vertex/" + JUDGE_MODEL if JUDGE_MODEL.startswith(("claude", "gemini")) else JUDGE_MODEL
)
LAB_DELIV_CAP = 60000
JB_JUDGE_PYTHON = jb_repo() / ".venv" / "bin" / "python"
JB_JUDGE_MODEL = (
    "google/" + JUDGE_MODEL
    if JUDGE_MODEL.startswith("gemini") and not env("SEC_AGENT_HARNESS2_JUDGE_BASE_URL")
    else JUDGE_MODEL
)
_vertex_host = (
    "aiplatform.googleapis.com"
    if VERTEX_REGION == "global"
    else f"{VERTEX_REGION}-aiplatform.googleapis.com"
)
VERTEX_OPENAI_URL = (
    f"https://{_vertex_host}/v1/projects/{VERTEX_PROJECT}"
    f"/locations/{VERTEX_REGION}/endpoints/openapi"
)
JB_JUDGE_API_BASE = env(
    "SEC_AGENT_HARNESS2_JUDGE_BASE_URL",
    (VERTEX_OPENAI_URL if VERTEX_PROJECT else "") or API_BASE_URL,
)
JB_JUDGE_API_KEY = env("SEC_AGENT_HARNESS2_JUDGE_API_KEY", API_KEY if not VERTEX_PROJECT else "")
JB_JUDGE_REASONING_EFFORT = "low"
JB_REPORTING_JUDGE_DETAILS = ""
JB_OBS_TRUNC = 50000

CODEX_VERSION = "0.144.6"
CODEX_DIST = str(DEPENDENCIES / "codex" / "dist")
CODEX_BASE_URL = env("SEC_AGENT_HARNESS2_CODEX_BASE_URL", API_BASE_URL)
CODEX_CONTAINER_URL = env("SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL", CODEX_BASE_URL)
VERTEX_PROXY_KEY = env("SEC_AGENT_HARNESS2_CODEX_API_KEY", API_KEY)
CODEX_HOME_DIR = DEPENDENCIES / "codex" / "home"

CLAUDE_DIST = DEPENDENCIES / "claude"
CLAUDE_BIN = CLAUDE_DIST / "bin" / "clawgod"
CLAUDE_VERSION = "2.1.307"

WB_SOLVER_MODEL = "sec_agent_harness2/solver"
WB_WEB_JUDGE = "sec_agent_harness2/judge"
WB_RENDER_PY = sys.executable
WB_OC_HARNESS_VER = "1.14.18"
WB_CX_HARNESS_VER = CODEX_VERSION
WB_CLAUDE_HARNESS_VER = "1.0.0"
WB_MAX_JOBS = {"oc": 1, "cx": 1, "claude": 1}
WB_MAX_TRIALS = {"oc": 2, "cx": 2, "claude": 2}
WB_MODEL_CONNECTION = "local_proxy"

DEFAULT_PROPOSER_CHANNEL = "opencode"
PROPOSER_MODEL_BY_CHANNEL = {"opencode": IMPROVER_MODEL, "claude_cli": IMPROVER_MODEL}
PHASE_WIDTH = 2
TRANSPORT_ATTEMPTS = 2
PROPOSER_CONCURRENCY = 2


def validate_models(*, judge: bool = False) -> None:
    if not SOLVER_MODEL_OC:
        raise ConfigError(
            "SEC_AGENT_HARNESS2_SOLVER_MODEL is required for executor rollouts; set it in .env or "
            "the shell, or set SEC_AGENT_HARNESS2_API_MODEL alongside SEC_AGENT_HARNESS2_API_BASE_URL "
            "(see .env.example)"
        )
    if "/" not in SOLVER_MODEL_OC or "/" not in IMPROVER_MODEL:
        raise ConfigError("Executor and improver models must use OpenCode's provider/model syntax")
    if any(m.startswith("google-vertex") for m in (SOLVER_MODEL_OC, IMPROVER_MODEL)):
        if not VERTEX_PROJECT:
            raise ConfigError("Set GOOGLE_CLOUD_PROJECT for Vertex AI")
    if judge:
        require("SEC_AGENT_HARNESS2_JUDGE_MODEL", needed_by="benchmark judging")
