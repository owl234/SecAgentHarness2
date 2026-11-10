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

"""Benchmark dependency and runtime readiness checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from . import config
from . import i18n as I18N
from .install import PATCHES, missing_runners
from .substrate.opencode import OpencodeSubstrate


def check(adapter, *, judge=False) -> list[str]:
    missing = missing_runners()
    if missing:
        return [missing]
    errors = []

    def probe(label, cmd, *, cwd=None, remedy="run harness2-setup for this benchmark"):
        try:
            r = subprocess.run(
                [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=45
            )
            if r.returncode:
                errors.append(f"{label} failed; {remedy}")
            return r.returncode == 0
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{label}: {type(exc).__name__}; see README.md")
            return False

    sub_name = getattr(getattr(adapter, "substrate", None), "name", "oc")
    validations = [
        lambda: config.validate_models(judge=judge, substrate=sub_name),
        adapter.tasks,
        adapter.preflight,
    ]
    if sub_name == "oc":
        validations.append(OpencodeSubstrate().preflight)

    for validate in validations:
        try:
            validate()
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(str(exc))

    bench = adapter.spec.name.split("-", 1)[0]
    name = {"jb": "job-bench-eval", "lab": "harvey-labs", "wb": "workbuddy-bench"}[bench]
    repo = config.DEPENDENCIES / name
    deps_to_check = [name, "opencode"] if sub_name == "oc" else [name]
    for dependency in deps_to_check:
        target = config.DEPENDENCIES / dependency
        if (target / ".git").exists():
            try:
                head = subprocess.check_output(
                    ["git", "-C", str(target), "rev-parse", "HEAD"], text=True
                ).strip()
                if head != config.DEPENDENCY_PINS[dependency]:
                    errors.append(f"{dependency}: checkout differs from the supported pin")
            except subprocess.CalledProcessError:
                errors.append(f"{dependency}: cannot read checkout revision")
        if dependency in PATCHES:
            patch = config.THIRD_PARTY / "patches" / PATCHES[dependency]
            probe(
                f"{dependency} patch",
                ["git", "-C", target, "apply", "--reverse", "--check", patch],
            )
    if sub_name == "oc" and not (config.OPENCODE_DIR / "node_modules").is_dir():
        errors.append(I18N.t("preflight.oc_missing", I18N.get_lang(), b=bench))

    if sub_name == "pi":
        from . import api
        from .substrate.pi import find_pi_binary

        pi_bin = find_pi_binary()
        if not pi_bin.is_file() or not os.access(pi_bin, os.X_OK):
            errors.append(
                f"Pi Coding Agent binary missing or not executable at {pi_bin}; "
                "run 'harness2 setup <benchmark> --substrate pi' to install"
            )
        else:
            want = getattr(config, "PI_VERSION", "")
            if want:
                try:
                    r = subprocess.run(
                        [str(pi_bin), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if want not in (r.stdout or ""):
                        errors.append(
                            f"pi at {pi_bin} reports {r.stdout.strip()!r}, expected {want}; "
                            "rerun 'harness2 setup <benchmark> --substrate pi'"
                        )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"could not probe pi version at {pi_bin}: {exc}")

        ep = api.pi()
        if ep is None or not (ep.api_key or ep.base_url):
            errors.append(
                "Pi API endpoint not configured; set SEC_AGENT_HARNESS2_PI_BASE_URL / "
                "SEC_AGENT_HARNESS2_PI_API_KEY (or SEC_AGENT_HARNESS2_API_*)"
            )

    if any(
        m.startswith("google-vertex") for m in (config.SOLVER_MODEL_OC, config.IMPROVER_MODEL)
    ) or (judge and (bench == "wb" or config.JUDGE_MODEL.startswith("gemini"))):
        probe(
            "Google Application Default Credentials",
            ["gcloud", "auth", "application-default", "print-access-token"],
        )
    if bench == "lab":
        for binary in ("pandoc", "pdftoppm"):
            if not shutil.which(binary):
                errors.append(I18N.t("preflight.binary_missing", I18N.get_lang(), b=binary))
        probe(
            "LAB document and judge dependencies",
            [config.LAB_PYTHON, "-c", "import evaluation.scoring; import google.auth, anthropic"],
            cwd=repo,
        )
    elif bench == "jb" and judge:
        probe(
            "JobBench document and judge dependencies",
            [
                config.JB_JUDGE_PYTHON,
                "-c",
                "import pandas, openpyxl, docx, mammoth, pdfplumber, pptx, openai",
            ],
        )
        if not config.JB_JUDGE_API_BASE:
            errors.append(
                "Set GOOGLE_CLOUD_PROJECT or SEC_AGENT_HARNESS2_JUDGE_BASE_URL for JobBench judging"
            )
        if (
            config.JUDGE_MODEL
            and not config.JB_JUDGE_API_KEY
            and not config.JUDGE_MODEL.startswith("gemini")
        ):
            errors.append(
                "A non-Gemini JobBench judge requires SEC_AGENT_HARNESS2_JUDGE_BASE_URL and SEC_AGENT_HARNESS2_JUDGE_API_KEY"
            )
    elif bench == "wb":
        probe("Docker daemon", ["docker", "info", "--format", "{{.ServerVersion}}"])
        if adapter.spec.name == "wb-office":
            probe(
                "WorkBuddy document rendering",
                [config.WB_RENDER_PY, "-c", "import openpyxl, pptx"],
                remedy="install 'harness2[render]' in the main environment",
            )
        if sub_name == "pi" and not (config.PI_DIST / "node_modules" / ".bin" / "pi").is_file():
            errors.append(
                f"WorkBuddy pi-harness requires mounted /opt/pi distribution at {config.PI_DIST}; "
                "run 'harness2 setup wb --substrate pi'"
            )
        probe(
            "WorkBuddy runtime",
            [
                repo / ".venv/bin/python",
                "-c",
                "import harbor; from workbuddy_bench.runner.harness_adapters import HARNESS_ADAPTERS; "
                "assert all(k in HARNESS_ADAPTERS for k in ('opencode', 'oc-harness', 'pi-harness'))",
            ],
            cwd=repo,
        )
        for role, expected in (
            ("solver", config.SOLVER_MODEL_OC.removeprefix("google-vertex/")),
            ("judge", config.JUDGE_MODEL),
        ):
            path = repo / "configs/models/harness2" / f"{role}.yaml"
            try:
                if json.loads(path.read_text())["model"]["name"] != "google/" + expected:
                    errors.append(f"WorkBuddy {role} configuration is stale; rerun setup")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(f"WorkBuddy {role} configuration missing; rerun setup")
    return errors


def require_ready(adapter, *, judge=False):
    """Raise before a caller spends anything when this benchmark is not ready to run.

    `judge=True` also demands what grading will need: `SEC_AGENT_HARNESS2_JUDGE_MODEL` set, and,
    where a benchmark grades in its own environment, that environment installed and
    pointed at an endpoint. Those are offline presence and import checks — they catch an
    unset or unbuilt judge, not an account that cannot serve the judge model, which is
    still first learned when the judge actually calls it.
    """
    errors = check(adapter, judge=judge)
    if errors:
        lang = I18N.get_lang()
        raise config.ConfigError(
            I18N.t("preflight.incomplete", lang, errs="\n  - ".join(errors))
        )
