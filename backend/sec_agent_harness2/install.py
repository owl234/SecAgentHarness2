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

"""Repeatable installation of benchmark tools and release-owned runner overlays."""

from __future__ import annotations

import json
import shlex
import shutil
import stat
import subprocess
import tempfile
import tomllib
from pathlib import Path

from . import api, config

PATCHES = {
    "opencode": "opencode-compat.diff",
    "job-bench-eval": "job-bench-eval-judge.diff",
    "harvey-labs": "harvey-labs-judge-vertex-anthropic.diff",
    "workbuddy-bench": "workbuddy-bench-runtime.diff",
}

RUNNERS = (
    "jb_runner/run_benchmark_codex_cli_adapt.sh",
    "jb_runner/run_benchmark_claude_cli_adapt.sh",
    "lab_runner/opencode/run_opencode.py",
    "lab_runner/adapt_runs_claude/run_claude_lab.py",
    "wb_runner/agents/oc_agent.py",
    "wb_runner/agents/claude_agent.py",
    "wb_runner/agents/claude_harness_agent.py",
)


def missing_runners() -> str:
    """Explain which setup runners or patches are absent from third_party/, if any.

    A copy of the code without third-party material still runs the demo and tests, but
    setup needs these files to install a benchmark.
    """
    need = [config.THIRD_PARTY / "patches" / name for name in PATCHES.values()]
    need += [config.THIRD_PARTY / name for name in RUNNERS]
    absent = [path for path in need if not path.exists()]
    if not absent:
        return ""
    return (
        "benchmark runners and patches are not included in this copy "
        f"({len(absent)} of {len(need)} missing under third_party/); "
        "see third_party/README.md"
    )


def run(cmd, *, cwd=None, dry_run=False):
    cmd = [str(c) for c in cmd]
    print((f"[{cwd}] " if cwd else "") + shlex.join(cmd), flush=True)
    if not dry_run:
        subprocess.run(cmd, cwd=cwd, check=True)


def clone(name: str, *, dry_run=False):
    repo = config.DEPENDENCIES / name
    pin = config.DEPENDENCY_PINS[name]
    if (repo / ".git").exists():
        revision = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
        )
        if revision.returncode == 0:
            head = revision.stdout.strip()
            if head == pin:
                return
            raise RuntimeError(
                f"{repo} is at {head}, expected {pin}; move this checkout aside before setup"
            )
        origin = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if any(path.name != ".git" for path in repo.iterdir()) or (
            origin.stdout.strip() != config.DEPENDENCY_ORIGINS[name]
        ):
            raise RuntimeError(f"Incomplete checkout at {repo}; move it aside before setup")
    else:
        if repo.exists() and any(repo.iterdir()):
            raise RuntimeError(f"Refusing to overwrite nonempty {repo}")
        run(["git", "init", "-q", repo], dry_run=dry_run)
        run(
            ["git", "-C", repo, "remote", "add", "origin", config.DEPENDENCY_ORIGINS[name]],
            dry_run=dry_run,
        )
    run(["git", "-C", repo, "fetch", "--depth", "1", "origin", pin], dry_run=dry_run)
    run(["git", "-C", repo, "checkout", "--detach", "FETCH_HEAD"], dry_run=dry_run)


def patch(name: str, *, dry_run=False):
    repo = config.DEPENDENCIES / name
    source = config.THIRD_PARTY / "patches" / PATCHES[name]
    if dry_run:
        run(["git", "-C", repo, "apply", "--check", source], dry_run=True)
        run(["git", "-C", repo, "apply", source], dry_run=True)
        return
    if (
        subprocess.run(
            ["git", "-C", str(repo), "apply", "--reverse", "--check", str(source)],
            capture_output=True,
        ).returncode
        == 0
    ):
        return
    run(["git", "-C", repo, "apply", "--check", source])
    run(["git", "-C", repo, "apply", source])


def overlays(name: str, *, dry_run=False):
    assets = config.THIRD_PARTY
    repo = config.DEPENDENCIES / name
    pairs = []
    if name == "harvey-labs":
        pairs = [
            (assets / "lab_runner" / "opencode", repo / "opencode"),
            (assets / "lab_runner" / "tts_lab", repo / "external" / "tts_lab"),
            (assets / "lab_runner" / "adapt_runs_cx", repo / "external" / "adapt_runs_cx"),
            (assets / "lab_runner" / "adapt_runs_claude", repo / "external" / "adapt_runs_claude"),
        ]
    if name == "workbuddy-bench":
        pairs = [
            (assets / "wb_runner" / "agents", repo / "src" / "workbuddy_bench" / "agents"),
            (assets / "wb_runner" / "configs" / "harnesses", repo / "configs" / "harnesses"),
        ]
    for source, dest in pairs:
        print(f"Copy runner assets: {source} -> {dest}", flush=True)
        if not dry_run:
            shutil.copytree(
                source,
                dest,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "PROVENANCE.md"),
            )


def workbuddy_models(*, dry_run=False):
    """Generate the two Vertex routes from the user's model IDs, never credentials."""
    solver = config.SOLVER_MODEL_OC.removeprefix("google-vertex/")
    judge = config.JUDGE_MODEL
    problem = ""
    if not config.SOLVER_MODEL_OC.startswith("google-vertex/gemini") or not judge.startswith(
        "gemini"
    ):
        problem = (
            "WorkBuddy setup requires a google-vertex/gemini... executor "
            "and a gemini... judge; choose IDs available in your project"
        )
    elif not config.VERTEX_PROJECT:
        problem = "Set GOOGLE_CLOUD_PROJECT for WorkBuddy's Vertex routes"
    if problem:
        if not dry_run:
            raise config.ConfigError(problem)
        print(f"Configure WorkBuddy solver and judge routes -- {problem}", flush=True)
        return
    for role, model in (("solver", solver), ("judge", judge)):
        payload = {
            "model": {
                "name": "google/" + model,
                "protocols": ["openai"],
                "backend_url_env": "SEC_AGENT_HARNESS2_WB_VERTEX_URL",
                "backend_key_command": "gcloud auth application-default print-access-token",
                "backend_key_ttl": 1800,
                "thought_signature_passback": True,
                "params": {
                    "max_output_tokens": 64000 if role == "solver" else 16384,
                    "extra_body": {"reasoning_effort": "high" if role == "solver" else "low"},
                },
            }
        }
        path = config.wb_repo() / "configs" / "models" / "harness2" / f"{role}.yaml"
        print(f"Configure WorkBuddy {role}: {model}", flush=True)
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)

            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


CODEX_LAUNCHER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REAL_BIN = Path(__file__).resolve().parent / "bin" / "codex"


def _normalize_tools(tools: object) -> list[dict]:
    if not isinstance(tools, list):
        return []
    out: list[dict] = []

    def _add_fn(item: dict) -> None:
        fn_block = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = item.get("name") or fn_block.get("name") or ""
        if not name:
            return
        desc = item.get("description") or fn_block.get("description") or ""
        params = (
            item.get("parameters")
            or fn_block.get("parameters")
            or {"type": "object", "properties": {}}
        )
        fn_obj = {"name": name, "description": desc, "parameters": params}
        merged = dict(item)
        merged.update(fn_obj)
        merged["type"] = "function"
        merged["function"] = fn_obj
        out.append(merged)

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        ttype = tool.get("type")
        if ttype == "function":
            _add_fn(tool)
        elif ttype == "namespace":
            for inner in tool.get("tools") or []:
                if isinstance(inner, dict) and inner.get("type") == "function":
                    _add_fn(inner)
        else:
            out.append(tool)
    return out


def _read_provider_config() -> tuple[str, str]:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    cfg = codex_home / "config.toml"
    if not cfg.is_file():
        return "", ""
    raw = cfg.read_text(encoding="utf-8", errors="replace")
    try:
        import tomllib

        data = tomllib.loads(raw)
        provider = str(data.get("model_provider") or "")
        block = (data.get("model_providers") or {}).get(provider) or {}
        return provider, str(block.get("base_url") or "")
    except Exception:
        m_prov = re.search(r'^model_provider\\s*=\\s*"([^"]+)"', raw, re.M)
        m_url = re.search(r'^base_url\\s*=\\s*"([^"]+)"', raw, re.M)
        return (m_prov.group(1) if m_prov else ""), (m_url.group(1) if m_url else "")


def main() -> int:
    args = sys.argv[1:]
    if (
        not args
        or args[0] != "exec"
        or any(f in args for f in ("-V", "--version", "-h", "--help"))
        or os.environ.get("SEC_AGENT_HARNESS2_NO_CODEX_SHIM")
    ):
        os.execv(str(REAL_BIN), [str(REAL_BIN), *args])

    provider, upstream_base = _read_provider_config()
    if not provider or not upstream_base:
        os.execv(str(REAL_BIN), [str(REAL_BIN), *args])

    target_url = upstream_base.rstrip("/") + "/responses"

    class ProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, *a: object) -> None:
            pass

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length)
            try:
                payload = json.loads(raw_body)
                if isinstance(payload, dict) and "tools" in payload:
                    payload["tools"] = _normalize_tools(payload["tools"])
                    raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except Exception:
                pass

            fwd_headers = {}
            for k in ("Authorization", "Content-Type", "Accept", "User-Agent"):
                v = self.headers.get(k)
                if v:
                    fwd_headers[k] = v
            fwd_headers.setdefault("Content-Type", "application/json")
            fwd_headers.setdefault("User-Agent", "codex-cli")

            req = urllib.request.Request(
                target_url, data=raw_body, headers=fwd_headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    self.send_response(resp.status)
                    ct = resp.headers.get("Content-Type")
                    if ct:
                        self.send_header("Content-Type", ct)
                    self.end_headers()
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except urllib.error.HTTPError as err:
                err_body = err.read()
                self.send_response(err.code)
                ct = err.headers.get("Content-Type") if err.headers else None
                if ct:
                    self.send_header("Content-Type", ct)
                self.end_headers()
                if err_body:
                    self.wfile.write(err_body)
            except Exception as exc:
                msg = json.dumps({"error": {"message": str(exc)}}).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(msg)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
    port = srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    override = f'model_providers.{provider}.base_url="http://127.0.0.1:{port}/v1"'
    cmd = [str(REAL_BIN), "exec", "-c", override, *args[1:]]
    try:
        return subprocess.call(cmd)
    finally:
        srv.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
"""


def write_codex_launcher(dest: Path | None = None) -> None:
    """Install the transparent tools-normalizing launcher at `<CODEX_DIST>/codex`."""
    dist = Path(dest or config.CODEX_DIST)
    if not (dist / "bin" / "codex").is_file():
        return
    binary = dist / "codex"
    if binary.is_symlink() or binary.is_file():
        binary.unlink()
    binary.write_text(CODEX_LAUNCHER_SCRIPT, encoding="utf-8")
    binary.chmod(0o755)


def codex(*, dry_run=False):
    root = config.DEPENDENCIES / "codex"
    run(
        ["npm", "install", "--prefix", root, f"@openai/codex@{config.CODEX_VERSION}"],
        dry_run=dry_run,
    )
    if not dry_run:
        candidates = list((root / "node_modules" / "@openai").glob("**/bin/codex"))
        if len(candidates) != 1:
            raise RuntimeError(
                f"Expected one native Codex binary in {root}; found {len(candidates)}"
            )
        dest = Path(config.CODEX_DIST)
        platform = candidates[0].parent.parent
        shutil.copytree(platform, dest, dirs_exist_ok=True)
        write_codex_launcher(dest)
        _share_with_containers(dest)
    configure_codex(dry_run=dry_run)


def _share_with_containers(root: Path) -> None:
    """Make the staged dist readable by the container user it is bind-mounted for.

    The copy inherits the installing shell's umask, and under a private one (077) the
    WorkBuddy agent, which runs as a different user, cannot open /opt/codex at all.
    """
    for path in (root, *root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            continue
        extra = stat.S_IRGRP | stat.S_IROTH
        if stat.S_ISDIR(mode) or mode & stat.S_IXUSR:
            extra |= stat.S_IXGRP | stat.S_IXOTH
        path.chmod(mode | extra)


CODEX_CONFIG_REMEDY = "rerun harness2-setup <bench> --substrate cx"
CODEX_PROVIDER = "sec_agent_harness2"


def configure_codex(*, dry_run=False, home_dir: Path | None = None):
    endpoint = api.codex()
    if endpoint is None or not endpoint.base_url:
        raise config.ConfigError(
            "SEC_AGENT_HARNESS2_CODEX_BASE_URL (or SEC_AGENT_HARNESS2_API_BASE_URL) is required for Codex setup; "
            "see .env.example"
        )
    body = (
        f"model = {json.dumps(config.SOLVER_MODEL_CX)}\n"
        f"model_provider = {json.dumps(CODEX_PROVIDER)}\n"
        f'[model_providers.{CODEX_PROVIDER}]\nname = "Configured Responses endpoint"\n'
        f"base_url = {json.dumps(endpoint.base_url)}\n"
        'wire_api = "responses"\nenv_key = "VERTEX_PROXY_KEY"\n'
    )
    target_home = home_dir or config.CODEX_HOME_DIR
    if not dry_run:
        target_home.mkdir(parents=True, exist_ok=True)
        (target_home / "config.toml").write_text(body, encoding="utf-8")
        if target_home == config.CODEX_HOME_DIR:
            write_codex_launcher()


def codex_config_error(*, home_dir: Path | None = None) -> str | None:
    """Why `CODEX_HOME/config.toml` no longer matches the live Codex configuration.

    `configure_codex` bakes the endpoint and the model into a file that the Codex CLI
    reads at rollout time, and setup is the only thing that writes it. Nothing else
    re-reads `SEC_AGENT_HARNESS2_CODEX_BASE_URL` / `SEC_AGENT_HARNESS2_CODEX_MODEL` afterwards, so callers
    verify the derived file here before a rollout is paid for -- otherwise a changed
    endpoint is silently ignored and the run contacts the stale one. Returns None when
    the file agrees with the environment, else a message naming the remedy.
    """
    target_home = home_dir or config.CODEX_HOME_DIR
    path = target_home / "config.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return (
            f"CODEX_HOME has no readable config.toml: {path} -- the configured provider "
            f"block there routes Codex to your Responses endpoint; {CODEX_CONFIG_REMEDY}"
        )
    except tomllib.TOMLDecodeError as exc:
        return f"{path} is not valid TOML ({exc}); {CODEX_CONFIG_REMEDY}"
    provider = data.get("model_provider")
    block = (data.get("model_providers") or {}).get(provider) or {}
    endpoint = api.codex()
    want_url = endpoint.base_url if endpoint is not None else config.CODEX_BASE_URL
    stale = [
        f"{key} is {found!r}, configuration says {want!r}"
        for key, want, found in (
            ("base_url", want_url, block.get("base_url")),
            ("model", config.SOLVER_MODEL_CX, data.get("model")),
        )
        if found != want
    ]
    if stale:
        return f"{path} is stale ({'; '.join(stale)}); {CODEX_CONFIG_REMEDY}"
    return None


def claude(*, dry_run=False):
    root = config.DEPENDENCIES / "claude"
    if dry_run:
        print(f"Install Claude Code (clawgod) runtime in {root}", flush=True)
        return
    root.mkdir(parents=True, exist_ok=True)
    # 1. Install dedicated isolated Bun >= 1.3.14 inside dependencies/claude
    run(["npm", "install", "--prefix", root, "bun@1.3.14"], dry_run=dry_run)

    # 2. Extract or copy clawgod runtime
    host_clawgod = Path.home() / ".clawgod"
    if (host_clawgod / "cli.cjs").is_file():
        print(f"Cloning local clawgod runtime from {host_clawgod} into {root}...", flush=True)
        for item in (
            "cli.cjs",
            "cli.original.cjs",
            "bun-ant-shim.cjs",
            "runtime-helpers.cjs",
            "feature-gates.cjs",
            "openai-proxy.cjs",
            "startup-check.cjs",
            "features.json",
            ".clawgod-version",
            ".source-version",
        ):
            src_f = host_clawgod / item
            if src_f.is_file():
                shutil.copy2(src_f, root / item)
        # NOTE: provider.json is deliberately NOT cloned: it may carry the user's API
        # key. cli.cjs auto-creates an empty default on first run; credentials then
        # come from the environment (see ClaudeSubstrate.exec_env).
        # Same for patches.json: host customisations must not leak into the pinned
        # runtime; start from all-gates-default.
        if not (root / "patches.json").is_file():
            (root / "patches.json").write_text("{}\n", encoding="utf-8")

        for folder in ("bunfs", "vendor"):
            src_d = host_clawgod / folder
            if src_d.is_dir():
                shutil.copytree(src_d, root / folder, dirs_exist_ok=True)
        # source-backup.json records the exact upstream bundle this pin came from
        # (used for provenance, not at runtime).
        for item in ("source-backup.json",):
            src_f = host_clawgod / item
            if src_f.is_file():
                shutil.copy2(src_f, root / item)

        # Path relocation / decoupling from ~/.clawgod
        cli_cjs = root / "cli.cjs"
        if cli_cjs.is_file():
            txt = cli_cjs.read_text(encoding="utf-8")
            txt = txt.replace("const clawgodDir = join(homedir(), '.clawgod');", "const clawgodDir = __dirname;")
            cli_cjs.write_text(txt, encoding="utf-8")

        fg_cjs = root / "feature-gates.cjs"
        if fg_cjs.is_file():
            txt = fg_cjs.read_text(encoding="utf-8")
            txt = txt.replace(
                "var clawgodDir = require('path').join(require('os').homedir(), '.clawgod');",
                "var clawgodDir = __dirname;",
            )
            fg_cjs.write_text(txt, encoding="utf-8")

        old_bytes = str(host_clawgod.resolve()).encode("utf-8")
        new_bytes = str(root.resolve()).encode("utf-8")
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in (".js", ".cjs", ".json"):
                b = p.read_bytes()
                if old_bytes in b:
                    p.write_bytes(b.replace(old_bytes, new_bytes))
    else:
        print(f"Downloading clawgod distribution into {root}...", flush=True)
        installer = (
            f'CLAWGOD_DIR="{root}" BIN_DIR="{root}/bin" NO_UPGRADE=0 '
            'curl -fsSL https://github.com/0Chencc/clawgod/releases/latest/download/install.sh | '
            f'sed -e "s|CLAWGOD_DIR=.*|CLAWGOD_DIR=\\"{root}\\"|g" '
            f'-e "s|BIN_DIR=.*|BIN_DIR=\\"{root}/bin\\"|g" | bash'
        )
        run(["bash", "-c", installer], dry_run=dry_run)

    # 3. Create standalone launcher script
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / "clawgod"
    launcher_content = (
        "#!/bin/bash\n"
        'DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'BUN_BIN="$DIR/node_modules/.bin/bun"\n'
        'CLI="$DIR/cli.cjs"\n'
        'if [ ! -x "$BUN_BIN" ]; then\n'
        '    echo "Isolated bun not found at $BUN_BIN; run harness2 setup --substrate claude" >&2\n'
        "    exit 1\n"
        "fi\n"
        'exec "$BUN_BIN" "$CLI" "$@"\n'
    )
    launcher.write_text(launcher_content, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Claude Code (clawgod) installed successfully at {launcher}", flush=True)


def download_jobbench(*, dry_run=False):
    """Install the JobBench task tree from its public Hugging Face dataset repo.

    The dataset is public, so an executor with web access may retrieve it;
    see `docs/BENCHMARKS.md`.
    """
    repo = config.jb_repo()
    dest = repo / "dataset" / "main"
    if (dest / ".sec_agent_harness2-download.json").is_file():
        return

    code = """from huggingface_hub import HfApi, snapshot_download
import json, sys
revision = HfApi().dataset_info("JobBench/job-bench").sha
snapshot_download("JobBench/job-bench", repo_type="dataset", revision=revision,
                  allow_patterns=["dataset/**"], local_dir=sys.argv[1])
open(sys.argv[1]+"/revision.json", "w").write(json.dumps({"revision": revision}))
"""
    if dry_run:
        print("Download JobBench/job-bench dataset/** from Hugging Face; record its revision")
        return
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError(
            f"{dest} already contains data without a download record; move it aside first"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="download-", dir=dest.parent) as tmp:
        run([repo / ".venv" / "bin" / "python", "-c", code, tmp])
        staged = Path(tmp) / "dataset"
        if not list(staged.glob("*/*/task_folder/TASK_INSTRUCTIONS.txt")):
            raise RuntimeError("JobBench download did not contain task instructions")
        if dest.exists():
            dest.rmdir()
        staged.rename(dest)
        shutil.copy2(Path(tmp) / "revision.json", dest / ".sec_agent_harness2-download.json")
