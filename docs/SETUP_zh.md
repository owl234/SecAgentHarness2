# 安装配置指南

请先阅读[快速入门指南](../README.md#安装指南)。本指南详细介绍基准测试依赖、模型 API 凭据配置以及可选的 Pi 执行器。针对具体的基准测试，请参阅[基准测试指南](BENCHMARKS_zh.md)。

<a id="requirements"></a>
## 系统要求

运行基准测试推荐使用 Linux 与 Python 3.12；Python 核心包亦支持 3.13。在 Debian/Ubuntu 系统上：

```bash
sudo apt-get update
sudo apt-get install -y git curl unzip ca-certificates pandoc poppler-utils
```

LAB 基准测试需要 Pandoc 与 Poppler。此外还需安装：

- [Node.js](https://nodejs.org/en/download) 20 或更高版本。
- [uv](https://docs.astral.sh/uv/getting-started/installation/)。
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)。
- [Docker Engine](https://docs.docker.com/engine/install/)（WorkBuddy-Bench 必需），且当前用户需具备运行 `docker info` 的权限。

基准测试的安装程序会在 `dependencies/` 目录下安装其独立固定版本的 Bun 运行时。
执行以下命令时，请保持 Harness² 主虚拟环境处于激活状态。

<a id="models-and-credentials"></a>
## 模型与身份凭据

如果尚未复制，请将 `.env.example` 复制为 `.env`。设置您的 Vertex AI 项目 ID 与模型 ID，然后进行身份验证：

```bash
gcloud auth application-default login
```

Shell 环境变量的优先级高于 `.env` 文件。
`GOOGLE_CLOUD_PROJECT` 用于指定您的 GCP 项目；`GOOGLE_CLOUD_LOCATION` 默认为 `global`。您的账号必须具备访问所配置各个模型的权限。

| 配置项 | 含义说明 |
|---|---|
| `SEC_AGENT_HARNESS2_API_BASE_URL` | 可选统一 API 端点基础 URL（`…/v1`），自适应驱动三大执行器（向下兼容 `HARNESS2_API_BASE_URL`） |
| `SEC_AGENT_HARNESS2_API_KEY` | 可选统一 API 密钥（向下兼容 `HARNESS2_API_KEY`） |
| `SEC_AGENT_HARNESS2_API_MODEL` | 可选统一模型 ID（OpenCode 会自动补齐 `sec_agent_harness2/` 前缀） |
| `SEC_AGENT_HARNESS2_SOLVER_MODEL` | 执行器模型（采用 OpenCode 的 `provider/model` 格式） |
| `SEC_AGENT_HARNESS2_IMPROVER_MODEL` | 改进器模型（同上格式；默认使用执行器模型） |
| `SEC_AGENT_HARNESS2_JUDGE_MODEL` | 基础评测模型 ID（适配器会自动添加 Vertex 前缀） |
| `SEC_AGENT_HARNESS2_RUNS_DIR` | 结果输出根目录；默认为 `runs/` |

提供的配置使用 Vertex Gemini 作为执行器与裁判（Judge），并支持使用 Gemini 作为优化器（Improver）。LAB 在配置对应凭据后，亦支持上游评测直接对接的 Provider。对于 WorkBuddy，安装程序会根据这些设置生成 Gemini 求解器与裁判路由；如果修改了任一模型，请重新执行 setup。

<a id="authentication-alternatives"></a>
### 替代身份验证方案

在配置了关联服务账号（Attached Service Account）的机器上，应用默认凭据（Application Default Credentials, ADC）可以直接使用该账号。其他验证方式包括：

- `gcloud auth application-default login --no-browser`：会在终端输出一段命令，供您在有浏览器的其他设备上完成认证并回传授权码。
- 将 `GOOGLE_APPLICATION_CREDENTIALS` 环境变量指向服务账号密钥 JSON 文件。
- `gcloud auth application-default login --impersonate-service-account=<account>`：模拟特定服务账号。

对于这些 Vertex 配置（包括使用密钥文件的方案），请确保 `gcloud` 位于系统的 `PATH` 路径中：因为环境安装检查程序会调用 `gcloud auth application-default print-access-token` 来验证凭据有效性。

<a id="benchmark-installation"></a>
## 基准测试安装

仅需安装您计划运行的基准测试：

```bash
sec-agent-harness2 setup lab
sec-agent-harness2 check --bench lab
```

JobBench 请使用 `jb`，WorkBuddy-Bench 请使用 `wb`（`harness2` 仍作为无缝别名可用）。子集选择与许可证说明请参阅[基准测试指南](BENCHMARKS_zh.md)。

相关的运行器层（Runner overlays）与兼容性补丁已包含在 [`third_party/`](../third_party/README.md) 中。安装脚本会将受支持的上游指定版本克隆到 `dependencies/` 目录下，应用对应补丁，创建基准测试专用环境，并下载评测任务数据。

各基准测试的独立运行环境位于各自的上游克隆目录内：

- `dependencies/harvey-labs/.venv`
- `dependencies/job-bench-eval/.venv`
- `dependencies/workbuddy-bench/.venv`

Harness² 会自动调用对应的解释器；在执行主命令时**请勿**手动激活这些内部虚拟环境。

<a id="installation-checks"></a>
### 安装预检

`sec-agent-harness2 setup <bench> --dry-run` 可以在不进行实际更改的情况下预览安装操作。
`sec-agent-harness2 check` 用于检查已安装的依赖项、凭据和配置，而不会发起模型调用。优化提炼任务在启动前也会执行相同的检查（包括裁判配置检查）。

这些检查不会测试模型的可用性。对执行器、优化器或裁判模型的访问权限将在该模型首次被调用时进行检验。如果提炼或评测未能正常完成，命令将返回非零退出状态码。

<a id="pi-executor"></a>
## Pi Coding Agent 执行器

Pi 执行器运行项目内隔离的 `@earendil-works/pi-coding-agent` 原生运行时（版本钉在 `sec_agent_harness2/config.py` 的 `PI_VERSION`），位于 `dependencies/pi/` 下。

在安装、检查、提炼、评测和报告命令中传入 `--substrate pi`：

```bash
sec-agent-harness2 setup lab --substrate pi
sec-agent-harness2 check --bench lab --substrate pi
sec-agent-harness2 run --bench lab --substrate pi --k 1 --mode parallel \
  --only-domains antitrust-competition --max-tasks 1
```

该基座通过独立 `PI_CODING_AGENT_DIR` 隔离 `models.json` 配置，严格遵循 camelCase baseUrl 规范，原生支持无锁并发与思考预算控制（`--thinking` 或 `SEC_AGENT_HARNESS2_PI_EFFORT`）。

<a id="network-access-during-setup"></a>
## 安装期间的网络访问

安装脚本会从以下主机下载依赖资源：

| 主机地址 | 用途 |
|---|---|
| `github.com` | 固定版本的上游仓库克隆 |
| `registry.npmjs.org` | 固定版本的 Bun 运行时，以及 npm / bun 解析的依赖包 |
| `huggingface.co` 及其 CDN | JobBench 数据集与 WorkBuddy 子集压缩包 |
| Docker Registry | WorkBuddy 容器镜像 |
| `astral.sh` | 当宿主机无系统级 Python 3.12 时下载 CPython 3.12 |

在配置网络环境或防火墙时，可使用 `sec-agent-harness2 setup <bench> --dry-run` 预览安装命令。实验运行期间还会访问 `.env` 中配置的模型端点。安装下载与执行器评测阶段的网络访问要求不同；详见[评测期间的网络访问控制](EXPERIMENTS_zh.md#网络访问控制)。

<a id="wheel-installations"></a>
## Wheel 轮子安装方式

构建的 Wheel 安装包仅分发 `sec-agent-harness2` 核心 Python 包。任务划分脚本 `python scripts/split_tasks.py` 必须依赖源码仓库目录树。如果通过 Wheel 安装，请在一个专属工作目录下操作：`.env`、`dependencies/` 和 `runs/` 将在该目录下被解析与创建。
