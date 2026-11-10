#!/usr/bin/env python3
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

"""Central bilingual (EN/ZH) string table for Harness2 CLIs and user-facing errors.

Usage:
    from sec_agent_harness2 import i18n
    lang = i18n.get_lang(args.lang)          # 'zh' (default) | 'en'
    parser.add_argument("--host", help=i18n.t("ui.host", lang))

Language resolution order (first hit wins):
    1. explicit `override` argument (i.e. --lang zh / --lang en)
    2. `--lang <v>` / `--lang=<v>` pre-scan of sys.argv (so --help itself is translated)
    3. $SEC_AGENT_HARNESS2_LANG
    4. $LANG / $LANGUAGE
    5. 'zh' (default; native Chinese localization)

Conventions:
    - ZH is the default.
    - t() never raises: unknown keys return the key itself.
    - Machine-readable tokens (bench names, on-disk agg/seq, JSON keys,
      routes, file names) are NEVER translated; only human prose is.
"""

from __future__ import annotations

import os
import sys

SUPPORTED = ("en", "zh")

# key -> (en, zh). Keep tokens (jb/wb/lab, oc/cx, agg/seq, paths) identical.
_STR: dict[str, tuple[str, str]] = {
    # ---------- shared cell / identity ----------
    "cell.bench": (
        "jb (=jobbench) | wb (=workbuddy) | lab (=harvey-labs)",
        "jb（=jobbench）| wb（=workbuddy）| lab（=harvey-labs）：缩写与全名通用",
    ),
    "cell.subset": (
        "WB only: office | web | code",
        "仅 WB：office | web | code（办公 / 网页 / 代码）",
    ),
    "cell.substrate": (
        "task-executor substrate: oc (=opencode) | pi (=pi coding agent)",
        "任务执行基座：oc（=opencode）| pi（=pi coding agent）：缩写与全名通用",
    ),
    "cell.modes": (
        "parallel | sequential (agg / seq accepted: the on-disk tokens); "
        "comma list, e.g. 'parallel' or 'parallel,sequential'",
        "parallel | sequential（agg / seq 为磁盘存储令牌）；逗号分隔，如 'parallel' 或 'parallel,sequential'",
    ),
    "cell.k": (
        "scale: R=4k rollouts, P=3k improver sessions per task",
        "规模：每任务 R=4k 条轨迹、P=3k 次优化器会话",
    ),
    "cell.seed": (
        "stream-order seed; omit for sorted task order",
        "任务流排序种子；省略则按任务名排序执行",
    ),
    "cell.lang": (
        "output language: zh (default) | en",
        "输出语言：zh（默认，简体中文）| en（英文）",
    ),
    "err.unknown_bench": ("unknown bench {v!r}; expected one of {opts}", "未知基准 {v!r}；应为 {opts} 之一"),
    "err.unknown_substrate": (
        "unknown substrate {v!r}; expected one of {opts}",
        "未知执行基座 {v!r}；应为 {opts} 之一",
    ),
    "err.wb_need_subset": (
        "--bench wb needs --subset from {opts}, got {v!r}",
        "--bench wb 需要 --subset（{opts} 之一），实际得到 {v!r}",
    ),
    "err.subset_only_wb": (
        "--subset applies to --bench wb only, got {v!r} for {b}",
        "--subset 仅适用于 --bench wb，当前 bench={b} 却传入 {v!r}",
    ),
    "err.modes_empty": (
        "--modes takes a comma list of parallel | sequential (agg | seq), got {v!r}",
        "--modes 需要 parallel | sequential（agg | seq）的逗号列表，实际得到 {v!r}",
    ),
    # ---------- run_sweep ----------
    "sweep.desc": (
        "Run one adaptation sweep.",
        "运行一次适配扫描（全量任务， domains 并行、任务按流顺序执行）。",
    ),
    "sweep.split_file": (
        "optional partition from scripts/split_tasks.py",
        "可选任务划分文件（来自 scripts/split_tasks.py）",
    ),
    "sweep.preset": (
        "smoke: the documented one-task smoke test "
        "(--only-domains <first-domain> --max-tasks 1); explicit flags win",
        "smoke：文档标准单任务冒烟（--only-domains 首领域 --max-tasks 1）；显式参数优先",
    ),
    "sweep.workers": ("domains to run concurrently", "并发运行的领域数"),
    "sweep.only_domains": (
        "comma list restricting the sweep to these domains",
        "仅限这些领域的逗号列表",
    ),
    "sweep.max_tasks": (
        "per-domain cap on the stream (the first N tasks of every domain); "
        "drop it for the full run",
        "每领域任务上限（每领域前 N 个任务）；省略则全量运行",
    ),
    "sweep.dry_run": (
        "print the stream order, the namespaces and the split's domains, then "
        "exit — no rollouts, no sessions, nothing written",
        "仅打印任务流顺序、命名空间与划分领域后退出——不产生轨迹、不建会话、不写盘",
    ),
    "sweep.group_cell": ("cell", "基准单元"),
    "sweep.group_identity": ("run identity (enters the namespace)", "运行标识（进入命名空间）"),
    "sweep.group_control": ("run control", "运行控制"),
    "sweep.err_k_workers": ("--k and --workers must be positive", "--k 与 --workers 必须为正数"),
    "sweep.err_prefix": ("error: {e}", "错误：{e}"),
    "sweep.domains_of_split": (
        "# domains of this split, with task counts (the legal --only-domains names):",
        "# 本划分领域及任务数（合法 --only-domains 名称）：",
    ),
    "sweep.start": (
        "sweep {ns}: {lanes} domain(s) in parallel, tasks within a domain in stream order",
        "扫描 {ns}：{lanes} 个领域并行，领域内任务按流顺序执行",
    ),
    "sweep.zero_tasks": (
        "sweep {ns}: zero tasks scheduled (split={split!r}, only_domains={only!r}, "
        "max_tasks={max!r}); refusing to report success",
        "扫描 {ns}：未排期任何任务（split={split!r}，only_domains={only!r}，max_tasks={max!r}）；拒绝报成功",
    ),
    "sweep.done": (
        "sweep {ns}: {done} tasks ok, {failed} failed, {ndead} domain(s) died{died}",
        "扫描 {ns}：成功 {done} 个，失败 {failed} 个，{ndead} 个领域异常{died}",
    ),
    "sweep.next": ("next:", "下一步："),
    "sweep.record": ("record: {rec}", "记录：{rec}"),
    "sweep.err_identity": (
        "This run directory belongs to different models or tasks. "
        "Choose a new SEC_AGENT_HARNESS2_RUNS_DIR for a new experiment.",
        "该运行目录属于不同的模型或任务。请为新实验选择新的 SEC_AGENT_HARNESS2_RUNS_DIR。",
    ),
    # ---------- judge ----------
    "judge.desc": (
        "Judge the SELECTED run of each finished task in one namespace, and cache the rows.",
        "评审一个命名空间下各已完成任务的已选（SELECTED）运行，并缓存评分行。",
    ),
    "judge.bases": (
        "score this namespace's reference executions into base_judged.json "
        "instead of the selected runs",
        "改为将该命名空间的基准执行写入 base_judged.json，而非已选运行",
    ),
    "judge.err_cache": (
        "unreadable judged cache {p}: {e}; move it aside to rebuild",
        "无法读取已缓存评分 {p}：{e}；请移走后重建",
    ),
    "judge.skip": ("  ! skipping unreadable {p}: {e}", "  ! 跳过不可读文件 {p}：{e}"),
    "judge.no_ref": (
        "no reference executions recorded under {d}; wrote nothing",
        "{d} 下未记录任何基准执行；未写入任何内容",
    ),
    "judge.legacy": (
        "  {n} reference execution(s) predate run-directory recording and cannot be "
        "scored; re-run those tasks to include them.",
        "  有 {n} 条基准执行早于运行目录记录，无法评分；请重跑这些任务以纳入统计。",
    ),
    "judge.wrote": ("wrote {o}: {n} row(s), {g} graded", "已写入 {o}：共 {n} 行，已评分 {g} 行"),
    "judge.err_model_changed": (
        "Judge model changed for this experiment; choose a new SEC_AGENT_HARNESS2_RUNS_DIR",
        "本实验的裁判模型已变更；请选择新的 SEC_AGENT_HARNESS2_RUNS_DIR",
    ),
    "judge.err_nothing": (
        "nothing to judge: {d} does not exist — has the sweep `{ns}` run on this machine?",
        "无可评审：{d} 不存在——扫描 `{ns}` 是否在本机运行过？",
    ),
    "judge.err_no_sel": (
        "nothing to judge: no selections for modes {m} under {d} (tasks may still "
        "be running, or the wrong --k/--seed was given)",
        "无可评审：{d} 下模式 {m} 无候选结果（任务可能仍在运行，或 --k/--seed 给错）",
    ),
    "judge.judging": ("judging {n} selection(s) under {ns} ...", "正在评审 {ns} 下的 {n} 个候选项……"),
    "judge.summary": (
        "judged.json: {n} row(s), {g} graded, {u} ungraded (judge failure or no pick — NOT zeros)",
        "judged.json：共 {n} 行，已评分 {g} 行，未评分 {u} 行（裁判失败或未选中——不是零分）",
    ),
    "judge.wrote_path": ("wrote {p}", "已写入 {p}"),
    # ---------- report ----------
    "report.desc": (
        "Render the score report for one cell from cached judged.json rows — read-only.",
        "离线渲染已缓存 judged.json 行的评分报告（只读）。",
    ),
    "report.k": (
        "comma list of scales to report, e.g. 1,2,3",
        "要报告的规模列表，如 1,2,3",
    ),
    "report.seed": (
        "stream-order seed of the sweep; omit for the seedless namespace",
        "扫描的任务流种子；无种子命名空间请省略",
    ),
    "report.group_identity": ("run identity (names the sweeps)", "运行标识（命名扫描）"),
    "report.err_k": ("--k takes a comma list of ints, got {v!r}", "--k 需要整数逗号列表，实际得到 {v!r}"),
    "report.err_no_scale": ("--k named no scale", "--k 未指定任何规模"),
    "report.no_rows": (
        "  ! no judged rows at {p} — run cli.judge for k={k} first",
        "  ! {p} 无已评分行——请先为 k={k} 运行 cli.judge",
    ),
    "report.nothing": ("nothing to report", "无可报告内容"),
    "report.spend": (
        "  improver (editors, composer, selection, reflection) spend across reported modes: ${s:.2f}",
        "  已报告模式下优化器（编辑器/组合器/筛选/反思）总花费：${s:.2f}",
    ),
    # ---------- setup ----------
    "setup.desc": (
        "Install a benchmark's pinned tools, runner overlays, dependencies, and data.",
        "安装基准测试的固定版本工具、运行器覆盖层、依赖与数据。",
    ),
    "setup.subset": (
        "wb only: one subset to install; omitted installs office, web, and code",
        "仅 wb：要安装的子集；省略则安装 office、web、code 全部",
    ),
    "setup.err_subset": ("--subset only applies to wb", "--subset 仅适用于 wb"),
    "setup.failed": ("setup failed: {e}", "安装失败：{e}"),
    "setup.note": ("Note: {m}", "提示：{m}"),
    "setup.missing": ("Missing {b}; see README_en.md", "缺少 {b}；详见 README.md"),
    "setup.plan_done": ("Setup plan complete.", "方案预览完成（dry-run，未实际安装）。"),
    "setup.done": (
        "Installation complete. Run harness2-check before an experiment.",
        "安装完成。实验前请先运行 harness2-check。",
    ),
    # ---------- check ----------
    "check.desc": (
        "Check one installed benchmark before running adaptation and judging.",
        "在运行适配与评审前检查已安装的基准测试。",
    ),
    "check.fail": ("FAIL: {e}", "失败 FAIL：{e}"),
    "check.incomplete": (
        "Setup incomplete: {n} issue(s). See docs/BENCHMARKS.md.",
        "环境未就绪：共 {n} 个问题，详见 docs/BENCHMARKS_zh.md。",
    ),
    "check.ready": (
        "Ready: {spec}/{sub}; {n} tasks. "
        "Model access is not exercised; the first real run is the first model call.",
        "就绪：{spec}/{sub}；共 {n} 个任务。未实际调用模型；首次真实运行即首次模型调用。",
    ),
    # ---------- demo ----------
    "demo.desc": (
        "Run the real recursion and library workflow with local, deterministic editors.",
        "使用本地确定性编辑器运行真实递归与经验库流程。",
    ),
    "demo.output": ("output directory", "输出目录"),
    "demo.k": ("recursion budget", "递归预算 k"),
    "demo.mode": ("recursion mode", "递归模式"),
    "demo.err_k": ("--k must be positive", "--k 必须为正数"),
    "demo.done": (
        "Local demo: {d} tasks completed; {f} failed. {r}",
        "本地 Demo：完成 {d} 个任务，失败 {f} 个。报告：{r}",
    ),
    # ---------- ui ----------
    "ui.desc": (
        "Launch the Harness² Visual Web Console and Workbench",
        "启动 Harness² 可视化 Web 控制台与工作台",
    ),
    "ui.host": (
        "Host to bind the server to (default: 127.0.0.1)",
        "服务监听地址（默认 127.0.0.1）",
    ),
    "ui.port": (
        "Port to serve the web console (default: 8520)",
        "Web 控制台端口（默认 8520）",
    ),
    "ui.runs_dir": (
        "Root directory where runs and sweeps reside (default: runs)",
        "运行与扫描结果根目录（默认 runs）",
    ),
    "ui.no_open": (
        "Do not automatically open the browser on startup",
        "启动时不自动打开浏览器",
    ),
    "ui.no_deps": (
        "error: web console dependencies missing. Please install with: "
        "uv pip install -e '.[ui]' or uv pip install fastapi uvicorn",
        "错误：缺少 Web 控制台依赖，请运行：uv pip install -e '.[ui]' 或 uv pip install fastapi uvicorn",
    ),
    "ui.banner": (
        " 🚀  Harness² Web Console & Recursive Workbench",
        " 🚀  Harness² 可视化控制台 & 递归工作台",
    ),
    "ui.web_url": (" • Web URL:        {u}", " • Web 地址：     {u}"),
    "ui.workspace": (" • Workspace:      {w}", " • 工作区：       {w}"),
    "ui.runs_dir_line": (" • Runs Directory: {r}", " • 运行目录：     {r}"),
    "ui.api": (" • API Endpoints:  {u}/api/runs, {u}/docs", " • API 接口：     {u}/api/runs，{u}/docs"),
    "ui.stop": (" Press Ctrl+C to stop the server.", " 按 Ctrl+C 停止服务。"),
    # ---------- preflight / install (user-facing remedies) ----------
    "preflight.incomplete": (
        "Setup incomplete; nothing has run yet:\n  - {errs}",
        "环境未就绪，尚未运行任何任务：\n  - {errs}",
    ),
    "preflight.oc_missing": (
        "OpenCode dependencies missing; run harness2-setup {b}",
        "缺少 OpenCode 依赖；请运行 harness2-setup {b}",
    ),
    "preflight.binary_missing": (
        "{b} missing; install pandoc and poppler-utils (README_en.md)",
        "缺少 {b}；请安装 pandoc 与 poppler-utils（详见 README.md）",
    ),
    # ---------- unified dispatcher ----------
    "cli.desc": (
        "One entry for the whole lifecycle: setup → check → run → judge → report. "
        "Legacy scripts (harness2-setup, harness2-check, ...) keep working.",
        "全生命周期统一入口：setup → check → run → judge → report。旧的分立命令保持可用。",
    ),
    "cli.cmd_setup": ("install a benchmark", "安装基准测试"),
    "cli.cmd_check": ("offline preflight for a benchmark", "基准测试离线预检"),
    "cli.cmd_run": ("run one adaptation sweep (alias: sweep)", "运行一次适配扫描（别名 sweep）"),
    "cli.cmd_sweep": ("alias of run", "run 的别名"),
    "cli.cmd_judge": ("judge the selected runs of one namespace", "评审命名空间的已选运行"),
    "cli.cmd_report": ("render the score report from cached rows", "渲染已缓存评分报告"),
    "cli.cmd_demo": ("zero-credential local smoke test", "零凭证本地冒烟测试"),
    "cli.cmd_pipeline": (
        "one command for check → run → judge → report",
        "一键跑通 check → run → judge → report",
    ),
    "cli.cmd_ui": ("launch the visual web console", "启动可视化 Web 控制台"),
    "cli.unknown": (
        "unknown command {v!r}; expected one of: {opts} (try `harness2 --help`)",
        "未知子命令 {v!r}；应为：{opts}（试试 `harness2 --help`）",
    ),
    "cli.pipeline_help": (
        "usage: harness2 pipeline --bench BENCH [--subset S] [--substrate SUB] "
        "[--k K] [--mode M] [--seed S] [--split S] [--only-domains D] "
        "[--max-tasks N] [--workers N] [--dry-run] [--skip-judge] [-- <run-only flags>]",
        "用法：harness2 pipeline --bench BENCH [--subset S] [--substrate SUB] "
        "[--k K] [--mode M] [--seed S] [--split S] [--only-domains D] "
        "[--max-tasks N] [--workers N] [--dry-run] [--skip-judge] [-- <仅传给 run 的参数>]",
    ),
    "cli.pipeline_check": ("[pipeline 1/4] check ...", "[流水线 1/4] 预检 ……"),
    "cli.pipeline_run": ("[pipeline 2/4] run ...", "[流水线 2/4] 适配扫描 ……"),
    "cli.pipeline_judge": ("[pipeline 3/4] judge ...", "[流水线 3/4] 评审 ……"),
    "cli.pipeline_report": ("[pipeline 4/4] report ...", "[流水线 4/4] 报告 ……"),
}


def normalize(lang: str | None) -> str:
    """Map 'zh-CN'/'zh_CN.UTF-8' -> 'zh', 'en*' -> 'en', unknown -> 'zh'."""
    if not lang:
        return "zh"
    low = lang.strip().lower().replace("_", "-")
    if low.startswith("en"):
        return "en"
    if low.startswith("zh"):
        return "zh"
    return "zh"


def _prescan_argv(argv: list[str] | None = None) -> str | None:
    """Return the value of --lang in argv if present, else None.

    Supports both `--lang zh` and `--lang=zh`. Never raises.
    """
    try:
        args = list(sys.argv[1:] if argv is None else argv)
    except Exception:
        return None
    for i, a in enumerate(args):
        if a == "--lang" and i + 1 < len(args):
            return args[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return None


def get_lang(override: str | None = None, argv: list[str] | None = None) -> str:
    """Resolve the active language: override > argv --lang > env > default zh."""
    if override:
        return normalize(override)
    pre = _prescan_argv(argv)
    if pre:
        return normalize(pre)
    for env in ("SEC_AGENT_HARNESS2_LANG", "LANGUAGE", "LANG"):
        val = os.environ.get(env, "")
        if val:
            norm = normalize(val)
            if env == "SEC_AGENT_HARNESS2_LANG":
                return norm
            if val.strip().lower().startswith("zh"):
                return "zh"
            if val.strip().lower().startswith("en") and env == "LANGUAGE":
                return "en"
    return "zh"


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    """Translate `key` to the active language and format with kwargs.

    Missing keys return the key itself; missing kwargs leave the template
    untouched (never raises — CLI output must not crash on i18n).
    """
    active = normalize(lang) if lang else get_lang()
    pair = _STR.get(key)
    if pair is None:
        template = key
    else:
        template = pair[1] if active == "zh" else pair[0]
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def add_lang_arg(p) -> None:
    """Add the shared --lang flag to an argparse parser / group."""
    try:
        p.add_argument(
            "--lang",
            default=None,
            choices=("en", "zh"),
            help=t("cell.lang"),
        )
    except Exception:
        pass


def resolve_lang(args, argv: list[str] | None = None) -> str:
    """Resolve language from parsed args (its .lang) with argv/env fallback."""
    try:
        override = getattr(args, "lang", None)
    except Exception:
        override = None
    return get_lang(override, argv)
