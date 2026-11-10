# 基准测试指南

请先完成[安装与凭据配置](SETUP_zh.md)。每个基准测试均独立安装；请仅安装您计划运行的基准测试。以下所有命令均支持传入 `--substrate pi` 以使用 [Pi 执行器](SETUP_zh.md#pi-执行器) 代替默认的 OpenCode（`harness2` 作为完全兼容的简短别名继续可用）。通过 `--mode parallel` 或 `--mode sequential` 选择递归模式，并通过 `--k` 设置任务级递归预算。请确保在运行（run）、评测（judge）和报告（report）命令中保持这些参数完全一致。

<a id="lab"></a>
## LAB

上游项目：[harveyai/harvey-labs](https://github.com/harveyai/harvey-labs)。
法律业务任务，包含原始案卷文档以及基于评分细则（Rubric）的打分机制。适配器会按专业执业领域（Practice area）对任务进行归类，并从传递给优化器（Improver）的材料中剥离评判标准。需要依赖 Pandoc 与 Poppler。

```bash
sec-agent-harness2 setup lab
sec-agent-harness2 check --bench lab
sec-agent-harness2 run --bench lab --k 1 --mode parallel
sec-agent-harness2 judge --bench lab --k 1 --mode parallel
sec-agent-harness2 report --bench lab --k 1 --mode parallel
```

序列递归模式只需将上述命令中的参数替换为 `--mode sequential`。

任务随固定版本的克隆代码存放在 `dependencies/harvey-labs/tasks/<practice-area>/<task>/task.json` 中，适配器会自动扫描发现所有已安装的任务；无需额外的任务列表文件。安装程序会配置 LAB 依赖环境、运行器层以及内置的 Vertex 裁判补丁。

裁判仅在完成候选套件筛选（Selection）后才会读取最终输出。评估指标采用 Partial（通过评分细则标准的比例）和 All-pass（所有标准全数通过）。如果裁判调用失败，该任务保持未评分（unscored）状态，并将输出写入运行目录下的 `judge.log`；如果其中出现 Vertex `429 RESOURCE_EXHAUSTED`，表示触发了配额限制，后续可直接重跑 `sec-agent-harness2 judge`。更换裁判模型会导致评测基准改变。输出结果位于 `runs/lab/` 目录下。

<a id="jobbench"></a>
## JobBench

上游项目：[Job-Bench/job-bench-eval](https://github.com/Job-Bench/job-bench-eval)。
数据集：[JobBench/job-bench](https://huggingface.co/datasets/JobBench/job-bench)。
专业工作日常任务，经验库（Library）按照数据集中的职业类别目录进行组织划分。

```bash
sec-agent-harness2 setup jb
sec-agent-harness2 check --bench jb
sec-agent-harness2 run --bench jb --k 1 --mode parallel
sec-agent-harness2 judge --bench jb --k 1 --mode parallel
sec-agent-harness2 report --bench jb --k 1 --mode parallel
```

序列递归模式运行相同命令并带上 `--mode sequential`。

安装脚本仅从 Hugging Face 下载主数据集——该数据集完全公开且未设置门禁，无需账号、Token 或签署协议——同时记录其版本号，并将任务放置在 `dependencies/job-bench-eval/dataset/main/` 目录下。安装程序还会安装文档抽取依赖项，并打上支持思考强度（Reasoning effort）和处理空补全的裁判补丁。评分准则（Rubrics）会被严格隔离在优化器的证据池之外。

当配置 Gemini 作为 `SEC_AGENT_HARNESS2_JUDGE_MODEL` 时，裁判会通过 GCP 项目的 Vertex OpenAI 兼容端点和应用默认凭据（ADC）进行评测。如需使用独立裁判 Provider，请设置 `SEC_AGENT_HARNESS2_JUDGE_BASE_URL`、`SEC_AGENT_HARNESS2_JUDGE_API_KEY` 及该端点支持的模型 ID。报告的分数采用上游评分标准的权重计算；未成功评分的任务会单独统计。结果保存在 `runs/jb/` 目录下。

注意：JobBench 的数据（包括 `RUBRICS.json`）在 Hugging Face 上完全公开，具有联网权限的执行器可能会检索到它们。在正式评测期间，请按照[网络访问控制](EXPERIMENTS_zh.md#网络访问控制)中的说明屏蔽相关域名。

<a id="workbuddy-bench"></a>
## WorkBuddy-Bench

上游项目：[Tencent/workbuddy-bench](https://github.com/Tencent/workbuddy-bench)。
数据集：[tencent/workbuddy-bench](https://huggingface.co/datasets/tencent/workbuddy-bench)。
涵盖办公（Office）、网页（Web）和代码（Code）三个子集。需要依赖 Docker。

上游腾讯定制许可证包含地域使用限制；在下载或使用该基准测试前，请先阅读[其许可证条款](https://github.com/Tencent/workbuddy-bench/blob/main/LICENSE)。衍生出来的 Runner 文件和补丁继承该许可证。

```bash
docker info
sec-agent-harness2 setup wb --subset office
sec-agent-harness2 check --bench wb --subset office
sec-agent-harness2 run --bench wb --subset office --k 1 --mode parallel
sec-agent-harness2 judge --bench wb --subset office --k 1 --mode parallel
sec-agent-harness2 report --bench wb --subset office --k 1 --mode parallel
```

序列递归模式运行相同命令并带上 `--mode sequential`。

不带 `--subset` 参数执行 `sec-agent-harness2 setup wb` 会一次性安装所有三个子集；传入 `--subset` 可仅安装您计划运行的具体子集。在此之后的所有其他命令一次只针对一个子集运行。

安装程序会安装固定版本的基于 Harbor 的运行时，应用附带的适配器、挂载和凭据/传输补丁，拷贝套件运行器，从 `.env` 创建求解器与裁判路由，利用上游脚本下载指定子集，并构建 OpenCode 套件镜像。公开的 Vertex 配置采用 `google-vertex/gemini...` 执行器格式与纯 `gemini...` 裁判模型 ID；无需从其他分支拷贝模型 YAML 或特定账号代理配置。如果未设置 `GOOGLE_CLOUD_PROJECT`，或者 `SEC_AGENT_HARNESS2_SOLVER_MODEL` 不是 `google-vertex/gemini...`、`SEC_AGENT_HARNESS2_JUDGE_MODEL` 不是纯 `gemini...`，安装程序将拒绝运行；`--dry-run` 会提示该要求并继续打印其余执行计划。该基准测试的任务本地代理（job-local proxy）会自动刷新 ADC Token，并在工具调用间完整保留 Gemini 的思考签名（thought signatures）。

安装程序对上游下载脚本进行了打补丁，优先使用 `curl` 下载（其次 `wget`，最后 `hf`），并强制校验数据集仓库的 `SHA256SUMS`：无法通过校验的压缩包将不会被解压。校验通过的下载会输出 `wb-bench-<subset>-v1.0.tar.gz: OK`。

任务根据 `dependencies/workbuddy-bench/datasets/wb-bench-<subset>-v1.0/tasks/` 下的 `task.toml` 与 `instruction.md` 进行发现。经验库（Libraries）在 code 子集下使用 `metadata.role` 分类，在 office 和 web 子集下使用 `metadata.category` 分类。每次轨迹采样（Rollout）均使用全新的基准测试 Docker 容器。适配器会读取验证器的 `score.json`；优化器绝不会接收到验证器的输出。缺失验证器结果的任务保持未评分状态。运行结果保存在 `runs/wb/<subset>/`。


