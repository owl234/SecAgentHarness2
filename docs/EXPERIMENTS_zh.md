# 实验指南

请先完成[安装配置](SETUP_zh.md)并选择[基准测试](BENCHMARKS_zh.md)。本指南涵盖递归预算设置、任务选取、实验可复现性以及评测流程。

<a id="recursion-modes"></a>
## 递归模式

两种模式均以同一基础套件（Base harness）的 `k` 次参考基准执行为起点：

- **并行递归（Parallel recursion）**：提议并探测 `k` 个通用不变（Invariant）候选套件与 `k` 个领域特定（Domain-specific）候选套件。随后进行的 `k` 次独立组合，每次均基于全部候选池及执行证据，生成优化后的运行套件。
- **序列递归（Sequential recursion）**：连续执行 `k` 轮提议–探测–组合（Propose–Probe–Compose）步骤，将上一轮优化出的套件和累积的执行证据传递到下一步骤中。

在采纳（Adoption）之后，反思（Reflection）阶段会将采纳的运行套件以及有证据支持的经验总结存储到按领域划分的经验库（Library）中。同一领域内的任务按序执行，且仅能读取早前已生成的经验条目；不同领域之间的任务可以并发运行。经验库按基准测试、执行器、递归模式、预算及随机种子进行隔离区分。

| 参数选项 | 行为说明 |
|---|---|
| `--k 1` | 单步 Propose–Probe–Compose 提炼，采纳后执行反思总结 |
| `--k K --mode parallel` | 每个范围（Scope）探索 `K` 个候选套件，并生成 `K` 个组合套件 |
| `--k K --mode sequential` | 通过 `K` 个连续递进步骤提炼运行套件 |
| `--workers N` | 并发运行 `N` 个领域；每个领域内的任务保持严格串行顺序 |
| `--substrate pi` | 使用 Pi Coding Agent 执行器替代默认的 OpenCode 执行器 |
| `--seed N` | 以可复现的方式打乱任务执行流；不控制模型的采样随机性 |

在优化提炼（Refinement）、评测（Judging）和生成报告（Reporting）时，请务必使用完全相同的基准测试、执行器、子集、`k` 值、递归模式及随机种子（`harness2` 作为完全兼容的简短别名继续可用）。示例：

```bash
export SEC_AGENT_HARNESS2_RUNS_DIR=runs/lab-sequential-k3
sec-agent-harness2 run --bench lab --k 3 --mode sequential \
  --only-domains antitrust-competition --max-tasks 1
sec-agent-harness2 judge --bench lab --k 3 --mode sequential
sec-agent-harness2 report --bench lab --k 3 --mode sequential
```

更改预算（`--k`）或模式（`--mode`）时，请使用独立的输出目录，以便于清晰区分不同实验组。

<a id="task-selection-and-cost"></a>
## 任务选取与成本控制

基于大模型的实际运行会因执行器采样（Rollouts）与优化提炼阶段产生 API 调用费用。完整的 LAB 任务流包含 1,143 个任务。建议在启动全量评测之前，先从少量任务开始，并核算模型调用的计费成本。

- `--only-domains`：将运行范围限制在指定的领域内。
- `--max-tasks`：限制**每个领域**的最大任务数，而非整个运行的总任务数。
- `--dry-run`：在不调用任何模型的情况下，预览选取的任务列表和可用领域。

每个基准测试还提供了一个封装脚本，用于按顺序自动执行检查、优化提炼、评测打分和报告生成。可通过环境变量设置 `SUBSTRATE`、`K`、`MODE`，以及（针对 WorkBuddy）`SUBSET`；额外的命令行参数将直接传递给核心优化提炼命令：

```bash
bash scripts/run_lab.sh --only-domains antitrust-competition --max-tasks 1
SUBSTRATE=cx K=3 MODE=sequential bash scripts/run_jobbench.sh --max-tasks 1
SUBSET=web bash scripts/run_workbuddy.sh --max-tasks 1
```

<a id="reproducibility"></a>
## 实验可复现性

对比不同预算或不同模式时，请保持任务选择、执行器、优化器、裁判以及网络访问策略完全一致。更换模型或调整任务选取时，请使用全新的 `SEC_AGENT_HARNESS2_RUNS_DIR` 输出目录；保存的运行配置会阻止不兼容的断点续跑。

JobBench 的数据集在下载时解析，而非固定在特定 Git Commit 上。安装脚本会将下载时的 Hugging Face 版本记录在 `dependencies/job-bench-eval/dataset/main/.harness2-download.json` 中。在报告 JobBench 评测结果时，建议一并附上该版本号。

<a id="task-partitions"></a>
### 任务划分

若要对已安装的任务生成可复现的、按领域分层（Domain-stratified）的划分数据集：

```bash
python scripts/split_tasks.py --bench lab --seed 42 --output splits/lab.json
sec-agent-harness2 run --bench lab --split-file splits/lab.json --split test --mode parallel
```

默认的训练集比例（Train fraction）为 0.5。生成的划分文件属于本地生成文件，并非发布包资产，且该脚本不会覆盖已存在的同名划分文件。

<a id="baseline-evaluation"></a>
## 基线对比评估

`sec-agent-harness2 judge --bases` 会对当前运行命名空间下的参考执行（Reference executions）进行打分，并在 `judged.json` 同级生成 `base_judged.json`，用于与基础运行套件（Base harness）进行对比。而 `sec-agent-harness2 report` 则专门针对优化提炼后的运行套件进行分析报告。

<a id="web-access"></a>
## 网络访问控制

所有三个基准测试均属于公开数据集，且 JobBench 在 Hugging Face 上直接公开了各任务的 `RUBRICS.json` 评分准则。因此，具备网络访问权限的执行器可能会检索到评分标准。

本发行版本默认不对网络访问施加限制。在安装配置完成后，建议针对执行器屏蔽以下主机域名，以杜绝智能体接触基准测试答案和评分标准的可能：

- `huggingface.co`、`hf.co` 以及 `*.hf.co`
- `github.com` 与 `raw.githubusercontent.com`（针对基准测试相关代码仓库）

安装步骤本身需要访问上述主机以下载依赖和数据集。执行器在运行时处于沙箱关闭状态，因此请在网络层面实施访问限制（例如在执行器宿主机上配置出站防火墙规则或 DNS 策略），而不要依赖工具内部设置。在汇报实验结果时，请说明所采取的网络限制措施。

<a id="results-and-resume"></a>
## 结果与断点恢复

默认输出根目录分别为 `runs/lab/`、`runs/jb/` 以及 `runs/wb/<subset>/`。目录内包含任务摘要、执行产出物、采纳的运行套件、反思笔记以及评分结果。

重复执行相同命令即可从断点继续运行（Resume）。评测失败的任务将保持未评分状态，而不会被计为 0 分。更改模型或修改任务范围时，请使用新的 `SEC_AGENT_HARNESS2_RUNS_DIR`。

优化提炼、评测与报告分别使用 `sec-agent-harness2`、`sec-agent-harness2 judge` 和 `sec-agent-harness2 report`（或 `harness2` 别名）；每个命令均支持使用 `--help` 查看完整参数选项。
