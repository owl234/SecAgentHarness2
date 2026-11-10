import React from 'react';
import {
  FileText,
  Shield,
  Brain,
  Terminal,
  Cpu,
  Boxes,
  BookOpen,
  Zap,
  ArrowRight,
  Server,
  Layers,
} from 'lucide-react';
import { FlowNode } from './flowTypes';
import { FlowNodeCard } from './FlowNodeCard';

interface ComponentsTopologyFlowProps {
  selectedNodeId?: string;
  onSelectNode: (node: FlowNode) => void;
  lang?: 'zh' | 'en';
}

export const COMPONENT_NODES: FlowNode[] = [
  // Context Construction
  {
    id: 'c1',
    code: 'c1',
    titleZh: '系统提示词 (System Prompt)',
    titleEn: 'System Prompt',
    subtitleZh: '全局身份与行为准则 · AGENTS.md',
    subtitleEn: 'Global identity & directives · AGENTS.md',
    badge: 'c1 Prompt',
    category: 'propose',
    icon: FileText,
    filePath: 'AGENTS.md / config.toml',
    formula: '\\text{Identity} \\oplus \\text{Reasoning Principles}',
    descriptionZh: '定义智能体的核心角色、顶层目标拆解原则与输出格式规约。受严格字符配额约束，由 INV 改写器优化。',
    descriptionEn: 'Defines agent core identity, top-level reasoning rules, and output schemas, bounded by character limits.',
    invariantsZh: ['字符预算通常受配额硬约束 (≤ 4,000 字符)', '禁止引入未经测试的冗余提示'],
    invariantsEn: ['Hard character budget constraint', 'Eliminates prompt verbosity'],
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c1',
    actionLabelEn: 'Edit c1 in Studio',
  },
  {
    id: 'c2',
    code: 'c2',
    titleZh: '安全护栏 (Guardrails)',
    titleEn: 'Guardrails',
    subtitleZh: '安全边界与行为防线 · guardrails/',
    subtitleEn: 'Operational boundaries · guardrails/',
    badge: 'c2 Guardrails',
    category: 'alert',
    icon: Shield,
    filePath: 'guardrails/ 或提示词独立防线段',
    formula: '\\text{Constraints} \\cap \\text{Permitted Actions}',
    descriptionZh: '设定操作不可逾越的安全红线（防止越权命令、禁止删除测试集与沙箱逃逸）。随探针报错动态补充负面规约。',
    descriptionEn: 'Enforces operational guardrails preventing destructive commands, test suite deletion, or escapes.',
    invariantsZh: ['不可删除关键评测与系统防护文件', '动态提炼针对死循环与写覆盖的约束'],
    invariantsEn: ['Protected directories cannot be removed', 'Negative constraints against infinite loops'],
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c2',
    actionLabelEn: 'Edit c2 in Studio',
  },
  {
    id: 'c3',
    code: 'c3',
    titleZh: '长效记忆 (Memory)',
    titleEn: 'Memory',
    subtitleZh: '跨步骤环境事实 · AGENTS.md [Memory]',
    subtitleEn: 'Persistent facts · AGENTS.md [Memory]',
    badge: 'c3 Memory',
    category: 'memory',
    icon: Brain,
    filePath: 'AGENTS.md [Memory] 段',
    formula: '\\mathcal{M}_{context} \\subseteq \\text{Facts}',
    descriptionZh: '记录环境路径、已测试常数与前置失败教训，在反思阶段自动压缩更新，防止重复踩坑。',
    descriptionEn: 'Maintains long-term factual findings, verified parameters, and past failure insights.',
    invariantsZh: ['严格限制长度 (通常 ≤ 2,000 字符)，自动摘要压缩'],
    invariantsEn: ['Strict length bounds (usually ≤ 2,000 chars)'],
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c3',
    actionLabelEn: 'Edit c3 in Studio',
  },
  {
    id: 'c6',
    code: 'c6',
    titleZh: '专有技能 (Skills)',
    titleEn: 'Skills',
    subtitleZh: 'SOP 标准作业程序 · skills/<name>/SKILL.md',
    subtitleEn: 'Domain SOPs · skills/<name>/SKILL.md',
    badge: 'c6 Skills',
    category: 'propose',
    icon: BookOpen,
    filePath: 'skills/<name>/SKILL.md',
    formula: '\\text{Frontmatter} + \\text{Markdown Playbook}',
    descriptionZh: '为复杂领域（如渗透测试、漏洞挖掘、日志排查）提供端到端操作 SOP、解题模板与实操案例。',
    descriptionEn: 'Supplies domain-specific playbooks, step-by-step SOPs, and best practices.',
    invariantsZh: ['必须包含标准 YAML Frontmatter', '支持自带专有 scripts/ 脚本'],
    invariantsEn: ['Must contain valid YAML Frontmatter', 'Can bundle localized scripts/'],
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c6',
    actionLabelEn: 'Edit c6 in Studio',
  },

  // Core & Middleware
  {
    id: 'core-llm',
    titleZh: '冻结核心模型 (Frozen LLM)',
    titleEn: 'Frozen Core Model',
    subtitleZh: '零参数梯度反向传播',
    subtitleEn: 'Zero Parameter Updates',
    badge: 'Weights Frozen',
    category: 'core',
    icon: Cpu,
    formula: '\\theta_{LLM} \\equiv \\text{Constant}',
    descriptionZh: '基础大模型权重绝对保持冻结不变（如 GLM-5、Gemini 2.5 Pro、GPT-5），所有智能进化完全由外周 Harness 承载！',
    descriptionEn: 'Foundational model weights are strictly frozen with zero backprop; all intelligence emerges through surrounding harness.',
    invariantsZh: ['绝对无梯度更新', '跨基准评测保证公平基石'],
    invariantsEn: ['Absolute zero weight mutation', 'Cross-benchmark reproducibility anchor'],
  },
  {
    id: 'c8',
    code: 'c8',
    titleZh: '拦截插件与钩子 (Plugins)',
    titleEn: 'Plugins & Middleware',
    subtitleZh: '生命周期事件拦截器 · plugins/*.py',
    subtitleEn: 'Lifecycle event hooks · plugins/*.py',
    badge: 'c8 Plugins',
    category: 'probe',
    icon: Zap,
    filePath: 'plugins/*.py',
    formula: '\\text{Event} \\xrightarrow{Hook} \\text{Mutated Event}',
    descriptionZh: '挂载在执行器生命周期各阶段的拦截插件（输入过滤、敏感词脱敏、动态超时熔断、流量审查）。',
    descriptionEn: 'Middleware lifecycle hooks for input filtering, output sanitation, and timeouts.',
    invariantsZh: ['符合标准 Hook 接口签名', '必须安全处理异常防止执行器崩溃'],
    invariantsEn: ['Standard hook signature', 'Exception-safe wrappers'],
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c8',
    actionLabelEn: 'Edit c8 in Studio',
  },

  // Tool & Delegation
  {
    id: 'c4',
    code: 'c4',
    titleZh: '工具指引 (Tool Guidance)',
    titleEn: 'Tool Guidance',
    subtitleZh: 'API 调用协议与约束',
    subtitleEn: 'API contracts & schemas',
    badge: 'c4 Tool Guidance',
    category: 'substrate',
    icon: Terminal,
    filePath: 'tool_guidance/ 或参数描述段',
    formula: '\\text{Tool Contract} \\colon \\text{Args} \\to \\text{Response}',
    descriptionZh: '规范执行器提供的原生工具（如 bash, read_file, edit_file）的参数调用方式与返回值解析建议。',
    descriptionEn: 'Specifies tool invocation parameters, syntax rules, and error recovery guidance.',
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c4',
    actionLabelEn: 'Edit c4 in Studio',
  },
  {
    id: 'c7',
    code: 'c7',
    titleZh: '辅助执行脚本 (Scripts)',
    titleEn: 'Automation Scripts',
    subtitleZh: 'Python 本地工具集 · scripts/*.py',
    subtitleEn: 'Local Python scripts · scripts/*.py',
    badge: 'c7 Scripts',
    category: 'substrate',
    icon: Terminal,
    filePath: 'scripts/*.py',
    formula: '\\text{Deterministic Tooling} = f(\\text{Input})',
    descriptionZh: '存放可被模型直接调用的本地自动化脚本，将复杂的多步解析或模糊测试外包给确定性代码。',
    descriptionEn: 'Deterministic python scripts callable by agents for parsing, fuzzy testing, and data extraction.',
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c7',
    actionLabelEn: 'Edit c7 in Studio',
  },
  {
    id: 'c5',
    code: 'c5',
    titleZh: '子智能体委派 (Subagents)',
    titleEn: 'Subagent Delegation',
    subtitleZh: '专业分工协同 · sub_agents/<name>/AGENT.md',
    subtitleEn: 'Modular delegation · sub_agents/<name>/AGENT.md',
    badge: 'c5 Subagents',
    category: 'bench',
    icon: Boxes,
    filePath: 'sub_agents/<name>/AGENT.md',
    formula: '\\text{Agent}_{main} \\xrightarrow{\\text{Delegate}} \\text{Subagent}_{spec}',
    descriptionZh: '配置可被主代理调用的专业辅助智能体（如安全审计员、重构助手），实现分工协作与上下文隔离。',
    descriptionEn: 'Defines modular secondary agents with independent system prompts for delegated tasks.',
    actionTab: 'studio',
    actionLabelZh: '在工作室编辑 c5',
    actionLabelEn: 'Edit c5 in Studio',
  },

  // Sandbox Target
  {
    id: 'target-sandbox',
    titleZh: 'Substrate 执行沙箱 (Sandbox)',
    titleEn: 'Substrate Execution Sandbox',
    subtitleZh: 'OpenCode / Pi 隔离运行时',
    subtitleEn: 'OpenCode / Pi Isolation',
    badge: 'Isolated Target',
    category: 'substrate',
    icon: Server,
    filePath: 'substrate/base.py',
    formula: '\\text{Sandbox} \\vDash \\text{Tools} + \\text{OS State}',
    descriptionZh: '接收物化（Materialize）后的完整组件树，提供严格物理隔离的容器或沙箱环境，执行真实工具调用。',
    descriptionEn: 'Isolated execution sandbox receiving materialized harness tree and executing tool loops.',
  },
];

export const ComponentsTopologyFlow: React.FC<ComponentsTopologyFlowProps> = ({
  selectedNodeId,
  onSelectNode,
  lang = 'zh',
}) => {
  const isZh = lang === 'zh';
  const getNode = (id: string) => COMPONENT_NODES.find((n) => n.id === id)!;

  return (
    <div className="space-y-6">
      {/* Topology Header Banner */}
      <div className="p-4 rounded-2xl bg-indigo-50/70 dark:bg-gradient-to-r dark:from-indigo-950/40 dark:via-slate-900 dark:to-slate-950 border border-indigo-200/90 dark:border-indigo-900/40 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-indigo-800 dark:text-indigo-300">
          <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <span>
            {isZh
              ? 'SecAgentHarness² 围绕模型开放了 8 个可编辑组件，按运行时角色分为上下文、接口、委派与中间件 4 大体系。'
              : 'SecAgentHarness² exposes 8 editable components across Context, Interface, Delegation, and Middleware roles.'}
          </span>
        </div>
        <span className="font-mono text-[11px] bg-indigo-100 dark:bg-indigo-900/60 text-indigo-800 dark:text-indigo-200 px-2 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-700/50">
          c1 ~ c8 Multi-Role Matrix
        </span>
      </div>

      {/* 3-Column Runtime Topology Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Left Column: Context Construction (4 cols) */}
        <div className="lg:col-span-4 rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-500/20 dark:text-sky-400 font-mono font-bold text-xs flex items-center justify-center">
                1
              </span>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isZh ? '上下文构建 (Context Construction)' : 'Context Construction'}
              </h3>
            </div>
            <span className="text-[10px] font-mono text-sky-700 bg-sky-50 border border-sky-200 dark:text-sky-400 dark:bg-sky-950/50 px-2 py-0.5 rounded dark:border-sky-800/40">
              4 Components
            </span>
          </div>

          <div className="space-y-3">
            <FlowNodeCard
              node={getNode('c1')}
              isSelected={selectedNodeId === 'c1'}
              onClick={() => onSelectNode(getNode('c1'))}
              lang={lang}
            />
            <FlowNodeCard
              node={getNode('c2')}
              isSelected={selectedNodeId === 'c2'}
              onClick={() => onSelectNode(getNode('c2'))}
              lang={lang}
            />
            <FlowNodeCard
              node={getNode('c3')}
              isSelected={selectedNodeId === 'c3'}
              onClick={() => onSelectNode(getNode('c3'))}
              lang={lang}
            />
            <FlowNodeCard
              node={getNode('c6')}
              isSelected={selectedNodeId === 'c6'}
              onClick={() => onSelectNode(getNode('c6'))}
              lang={lang}
            />
          </div>
        </div>

        {/* Center Column: Core Model & Middleware Hook (4 cols) */}
        <div className="lg:col-span-4 flex flex-col justify-between rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-400 font-mono font-bold text-xs flex items-center justify-center">
                  2
                </span>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  {isZh ? '核心模型与拦截控制 (Core & Hook)' : 'Core Model & Middleware'}
                </h3>
              </div>
              <span className="text-[10px] font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 dark:text-indigo-400 dark:bg-indigo-950/50 px-2 py-0.5 rounded dark:border-indigo-800/40">
                Frozen Core
              </span>
            </div>

            <div className="space-y-4 mt-4">
              <FlowNodeCard
                node={getNode('core-llm')}
                isSelected={selectedNodeId === 'core-llm'}
                onClick={() => onSelectNode(getNode('core-llm'))}
                lang={lang}
              />

              <div className="p-3 rounded-2xl bg-purple-50/70 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800/30 space-y-2">
                <div className="flex items-center justify-between text-xs text-purple-800 dark:text-purple-300">
                  <span className="font-bold flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5" />
                    <span>{isZh ? '生命周期中间件钩子' : 'Lifecycle Hook'}</span>
                  </span>
                  <span className="text-[10px] font-mono">c8</span>
                </div>
                <FlowNodeCard
                  node={getNode('c8')}
                  isSelected={selectedNodeId === 'c8'}
                  onClick={() => onSelectNode(getNode('c8'))}
                  lang={lang}
                />
              </div>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-1">
            <span className="font-semibold text-slate-800 dark:text-slate-300 block">{isZh ? '交互数据流向:' : 'Data Flow:'}</span>
            <div className="flex items-center gap-2 text-[11px] font-mono text-blue-600 dark:text-cyan-400">
              <span>Context</span>
              <ArrowRight className="w-3 h-3" />
              <span>Prompt</span>
              <ArrowRight className="w-3 h-3" />
              <span>Tool Call</span>
            </div>
          </div>
        </div>

        {/* Right Column: Tool Interface & Delegation (4 cols) */}
        <div className="lg:col-span-4 rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-400 font-mono font-bold text-xs flex items-center justify-center">
                3
              </span>
              <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                {isZh ? '工具接口与任务委派 (Execution)' : 'Tools & Delegation'}
              </h3>
            </div>
            <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 dark:text-emerald-400 dark:bg-emerald-950/50 px-2 py-0.5 rounded dark:border-emerald-800/40">
              3 Components
            </span>
          </div>

          <div className="space-y-3">
            <FlowNodeCard
              node={getNode('c4')}
              isSelected={selectedNodeId === 'c4'}
              onClick={() => onSelectNode(getNode('c4'))}
              lang={lang}
            />
            <FlowNodeCard
              node={getNode('c7')}
              isSelected={selectedNodeId === 'c7'}
              onClick={() => onSelectNode(getNode('c7'))}
              lang={lang}
            />
            <FlowNodeCard
              node={getNode('c5')}
              isSelected={selectedNodeId === 'c5'}
              onClick={() => onSelectNode(getNode('c5'))}
              lang={lang}
            />
          </div>
        </div>
      </div>

      {/* Target Sandbox Bottom Strip */}
      <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/90 border border-teal-200 dark:border-teal-500/30 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-teal-50 text-teal-700 border border-teal-200 dark:bg-teal-500/20 dark:text-teal-400 dark:border-teal-500/30">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-bold text-sm text-slate-900 dark:text-white">
              {isZh ? '最终执行沙箱环境 (Substrate Sandboxes)' : 'Target Substrate Sandboxes'}
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isZh
                ? '所有组件树物化（Materialize）至临时沙箱目录，由 OpenCode / Pi 执行原生命令交互。'
                : 'Materialized harness trees deployed to isolated OpenCode / Pi sandboxes.'}
            </p>
          </div>
        </div>

        <button
          onClick={() => onSelectNode(getNode('target-sandbox'))}
          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white shadow-sm transition-all shrink-0"
        >
          {isZh ? '查看沙箱契约' : 'Inspect Sandbox'}
        </button>
      </div>
    </div>
  );
};
