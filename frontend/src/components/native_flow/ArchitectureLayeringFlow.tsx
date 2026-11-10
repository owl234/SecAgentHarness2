import React from 'react';
import {
  Compass,
  Terminal,
  Cpu,
  Database,
  ArrowDown,
  Layers,
  ShieldCheck,
  Activity,
  FolderLock,
  GitBranch,
} from 'lucide-react';
import { FlowNode } from './flowTypes';
import { FlowNodeCard } from './FlowNodeCard';

interface ArchitectureLayeringFlowProps {
  selectedNodeId?: string;
  onSelectNode: (node: FlowNode) => void;
  lang?: 'zh' | 'en';
}

export const ARCHITECTURE_NODES: FlowNode[] = [
  // Layer 1: Entry
  {
    id: 'l1-sweep',
    titleZh: '批处理扫参入口',
    titleEn: 'Batch Sweep CLI',
    subtitleZh: 'sec_agent_harness2/cli/run_sweep.py',
    subtitleEn: 'sec_agent_harness2/cli/run_sweep.py',
    badge: 'CLI Entry',
    category: 'entry',
    icon: Terminal,
    filePath: 'backend/sec_agent_harness2/cli/run_sweep.py',
    descriptionZh: '支持批量评测任务扫参、跨任务流序执行与分布式任务并发分派。',
    descriptionEn: 'Orchestrates batch sweeps across task discovery and cross-task sequences.',
  },
  {
    id: 'l1-demo',
    titleZh: '单任务演示入口',
    titleEn: 'Single Task Demo',
    subtitleZh: 'sec_agent_harness2/cli/demo.py',
    subtitleEn: 'sec_agent_harness2/cli/demo.py',
    badge: 'Demo CLI',
    category: 'entry',
    icon: Activity,
    filePath: 'backend/sec_agent_harness2/cli/demo.py',
    descriptionZh: '一键运行单任务快速演示（如 accounting demo），验证递归优化效果。',
    descriptionEn: 'Quick one-off execution on standalone tasks to test recursion.',
  },
  {
    id: 'l1-web',
    titleZh: 'Web 实时控制台',
    titleEn: 'Web Console Server',
    subtitleZh: 'sec_agent_harness2/ui/server.py',
    subtitleEn: 'sec_agent_harness2/ui/server.py',
    badge: 'Web UI',
    category: 'entry',
    icon: Compass,
    filePath: 'backend/sec_agent_harness2/ui/server.py',
    descriptionZh: 'FastAPI 服务端，提供 SSE 实时日志事件流、RESTful 任务状态与可视化交互。',
    descriptionEn: 'FastAPI server providing SSE streaming logs and interactive SPA console.',
  },

  // Layer 2: Dispatch
  {
    id: 'l2-schedule',
    titleZh: '任务调度与状态机',
    titleEn: 'Schedule State Machine',
    subtitleZh: 'sec_agent_harness2/core/schedule.py',
    subtitleEn: 'sec_agent_harness2/core/schedule.py',
    badge: 'Dispatch Seam',
    category: 'core',
    icon: GitBranch,
    filePath: 'backend/sec_agent_harness2/core/schedule.py',
    descriptionZh: '流序状态推进、文件锁原子写入、带指纹校验的断点续跑 (Resume)。',
    descriptionEn: 'Stream scheduling, file-locking state updates, and resumable execution.',
  },
  {
    id: 'l2-seam',
    titleZh: '评测基准规范契约',
    titleEn: 'Benchmark Seam Spec',
    subtitleZh: 'sec_agent_harness2/core/spec.py (BenchSpec)',
    subtitleEn: 'sec_agent_harness2/core/spec.py (BenchSpec)',
    badge: 'Isolation Seam',
    category: 'core',
    icon: ShieldCheck,
    filePath: 'backend/sec_agent_harness2/core/spec.py',
    descriptionZh: '严格定义任务规格接口与盲选裁判模板，保证优化器对评测集零知识。',
    descriptionEn: 'Enforces strict separation between optimization prompts and benchmark truth.',
  },

  // Layer 3: Core Recursion
  {
    id: 'l3-recursion',
    titleZh: '双层递归编排器',
    titleEn: 'Dual Recursion Engine',
    subtitleZh: 'sec_agent_harness2/core/recursion.py',
    subtitleEn: 'sec_agent_harness2/core/recursion.py',
    badge: 'Core Engine',
    category: 'propose',
    icon: Cpu,
    filePath: 'backend/sec_agent_harness2/core/recursion.py',
    descriptionZh: '驱动 4k 次 Rollout 与 3k 次提议调用，协调 INV/DOM 改写及并行/串行分支。',
    descriptionEn: 'Orchestrates 4k rollouts and 3k proposer calls across INV, DOM, and compose.',
  },
  {
    id: 'l3-tree',
    titleZh: '8 大组件树物化规范',
    titleEn: 'Component Tree Materializer',
    subtitleZh: 'sec_agent_harness2/core/tree.py (SurfaceSpec)',
    subtitleEn: 'sec_agent_harness2/core/tree.py (SurfaceSpec)',
    badge: 'Surface Spec',
    category: 'propose',
    icon: Layers,
    filePath: 'backend/sec_agent_harness2/core/tree.py',
    descriptionZh: '解析、校验并物化 8 大组件树至物理文件，提供带错重试安全网关。',
    descriptionEn: 'Parses, verifies, and materializes component tree with SurfaceSpec rules.',
  },

  // Layer 4: Substrates & Benchmarks
  {
    id: 'l4-substrate',
    titleZh: 'Substrate 载体协议',
    titleEn: 'Substrate Protocol',
    subtitleZh: 'substrate/base.py · opencode.py · pi.py',
    subtitleEn: 'substrate/base.py · opencode.py · pi.py',
    badge: 'Substrate Base',
    category: 'substrate',
    icon: Terminal,
    filePath: 'backend/sec_agent_harness2/substrate/base.py',
    descriptionZh: '定义标准化 Agent 交互沙箱协议，对接 OpenCode 与 Pi 原生运行时。',
    descriptionEn: 'Abstract protocol materializing tree into OpenCode and Pi execution sandboxes.',
  },
  {
    id: 'l4-benchmarks',
    titleZh: '评测基准适配器群',
    titleEn: 'Benchmark Adapters',
    subtitleZh: 'jobbench.py · lab.py · workbuddy.py',
    subtitleEn: 'jobbench.py · lab.py · workbuddy.py',
    badge: 'Quarantined Graders',
    category: 'bench',
    icon: FolderLock,
    filePath: 'backend/sec_agent_harness2/benchmarks/jobbench.py',
    descriptionZh: 'JobBench, LAB, WorkBuddy 独立评测适配器，评分器与 Ground Truth 物理绝对隔离。',
    descriptionEn: 'JobBench, LAB, WorkBuddy benchmark adapters strictly quarantined from optimizer.',
  },

  // Layer 5: Persistence
  {
    id: 'l5-selection',
    titleZh: '零标注无监督盲选决策',
    titleEn: 'Unsupervised Blind Judge',
    subtitleZh: 'sec_agent_harness2/core/selection.py',
    subtitleEn: 'sec_agent_harness2/core/selection.py',
    badge: 'Selection',
    category: 'judge',
    icon: ShieldCheck,
    filePath: 'backend/sec_agent_harness2/core/selection.py',
    descriptionZh: '确定性哈希匿名化打乱映射 (assign_ids)，消除位置偏见做出终审裁决。',
    descriptionEn: 'Deterministic hash shuffle eliminating position bias for unsupervised selection.',
  },
  {
    id: 'l5-library',
    titleZh: '跨任务持久化经验库',
    titleEn: 'Persistent Experience Library',
    subtitleZh: 'sec_agent_harness2/core/library.py (INDEX.md)',
    subtitleEn: 'sec_agent_harness2/core/library.py (INDEX.md)',
    badge: 'Continual Memory',
    category: 'memory',
    icon: Database,
    filePath: 'backend/sec_agent_harness2/core/library.py',
    descriptionZh: '沉淀高置信度经验三元组，自动注入后续同领域任务实现系统级持续演进。',
    descriptionEn: 'Accumulates high-confidence experience triples into domain INDEX.md for continual learning.',
  },
];

export const ArchitectureLayeringFlow: React.FC<ArchitectureLayeringFlowProps> = ({
  selectedNodeId,
  onSelectNode,
  lang = 'zh',
}) => {
  const isZh = lang === 'zh';
  const getNode = (id: string) => ARCHITECTURE_NODES.find((n) => n.id === id)!;

  return (
    <div className="space-y-6">
      {/* 3-Axis Guarantees Banner */}
      <div className="p-4 rounded-2xl bg-teal-50/70 dark:bg-gradient-to-r dark:from-teal-950/40 dark:via-slate-900 dark:to-slate-950 border border-teal-200/90 dark:border-teal-900/40 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 text-teal-800 dark:text-teal-300">
          <Compass className="w-4 h-4 text-teal-600 dark:text-teal-400" />
          <span>
            {isZh
              ? 'SecAgentHarness² 严格遵循三轴正交分离：Method（方法轴）· Substrate（载体轴）· Benchmark（评测轴）绝对解耦。'
              : 'SecAgentHarness² adheres to strict 3-axis decoupling: Method, Substrate, and Benchmark are 100% quarantined.'}
          </span>
        </div>
        <span className="font-mono text-[11px] bg-teal-100 dark:bg-teal-900/60 text-teal-800 dark:text-teal-200 px-2 py-0.5 rounded-full border border-teal-200 dark:border-teal-700/50">
          Zero Leakage Guarantee
        </span>
      </div>

      {/* Layer 1: Entry */}
      <div className="rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-500/20 dark:text-sky-400 font-mono font-bold text-xs flex items-center justify-center">
              L1
            </span>
            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
              {isZh ? '1. 用户交互与入口控制层 (CLI & Web UI)' : '1. Entry & User Interface'}
            </h4>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">Entrypoints</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <FlowNodeCard
            node={getNode('l1-sweep')}
            isSelected={selectedNodeId === 'l1-sweep'}
            onClick={() => onSelectNode(getNode('l1-sweep'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l1-demo')}
            isSelected={selectedNodeId === 'l1-demo'}
            onClick={() => onSelectNode(getNode('l1-demo'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l1-web')}
            isSelected={selectedNodeId === 'l1-web'}
            onClick={() => onSelectNode(getNode('l1-web'))}
            lang={lang}
            compact
          />
        </div>
      </div>

      <div className="flex justify-center -my-3">
        <ArrowDown className="w-4 h-4 text-slate-400 dark:text-slate-600" />
      </div>

      {/* Layer 2: Dispatch */}
      <div className="rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-400 font-mono font-bold text-xs flex items-center justify-center">
              L2
            </span>
            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
              {isZh ? '2. 调度与规划中心 (Dispatch & Seams)' : '2. Dispatch & Seams'}
            </h4>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">State Machine & Seam</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FlowNodeCard
            node={getNode('l2-schedule')}
            isSelected={selectedNodeId === 'l2-schedule'}
            onClick={() => onSelectNode(getNode('l2-schedule'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l2-seam')}
            isSelected={selectedNodeId === 'l2-seam'}
            onClick={() => onSelectNode(getNode('l2-seam'))}
            lang={lang}
            compact
          />
        </div>
      </div>

      <div className="flex justify-center -my-3">
        <ArrowDown className="w-4 h-4 text-slate-400 dark:text-slate-600" />
      </div>

      {/* Layer 3: Core Recursion Engine */}
      <div className="rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 font-mono font-bold text-xs flex items-center justify-center">
              L3
            </span>
            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
              {isZh ? '3. 核心递归引擎 (Core Recursion Engine)' : '3. Core Recursion Engine'}
            </h4>
          </div>
          <span className="text-[10px] font-mono text-blue-600 dark:text-blue-400">Propose & Surface</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FlowNodeCard
            node={getNode('l3-recursion')}
            isSelected={selectedNodeId === 'l3-recursion'}
            onClick={() => onSelectNode(getNode('l3-recursion'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l3-tree')}
            isSelected={selectedNodeId === 'l3-tree'}
            onClick={() => onSelectNode(getNode('l3-tree'))}
            lang={lang}
            compact
          />
        </div>
      </div>

      <div className="flex justify-center -my-3">
        <ArrowDown className="w-4 h-4 text-slate-400 dark:text-slate-600" />
      </div>

      {/* Layer 4: Substrates & Benchmarks */}
      <div className="rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-teal-50 text-teal-700 border border-teal-200 dark:bg-teal-500/20 dark:text-teal-400 font-mono font-bold text-xs flex items-center justify-center">
              L4
            </span>
            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
              {isZh ? '4. 执行载体与隔离评测 (Substrates & Benchmark Isolation)' : '4. Substrates & Benchmarks'}
            </h4>
          </div>
          <span className="text-[10px] font-mono text-rose-700 bg-rose-50 border border-rose-200 dark:text-rose-400 dark:bg-rose-950/40 px-2 py-0.5 rounded dark:border-rose-800/40">
            Strict Physical Isolation
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FlowNodeCard
            node={getNode('l4-substrate')}
            isSelected={selectedNodeId === 'l4-substrate'}
            onClick={() => onSelectNode(getNode('l4-substrate'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l4-benchmarks')}
            isSelected={selectedNodeId === 'l4-benchmarks'}
            onClick={() => onSelectNode(getNode('l4-benchmarks'))}
            lang={lang}
            compact
          />
        </div>
      </div>

      <div className="flex justify-center -my-3">
        <ArrowDown className="w-4 h-4 text-slate-400 dark:text-slate-600" />
      </div>

      {/* Layer 5: Persistence */}
      <div className="rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-xl space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-500/20 dark:text-purple-400 font-mono font-bold text-xs flex items-center justify-center">
              L5
            </span>
            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
              {isZh ? '5. 裁决、反思与持久化 (Selection & Persistence)' : '5. Selection & Persistence'}
            </h4>
          </div>
          <span className="text-[10px] font-mono text-purple-700 bg-purple-50 border border-purple-200 dark:text-purple-400 dark:bg-purple-950/50 px-2 py-0.5 rounded dark:border-purple-800/40">
            Zero-GT & Continual
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FlowNodeCard
            node={getNode('l5-selection')}
            isSelected={selectedNodeId === 'l5-selection'}
            onClick={() => onSelectNode(getNode('l5-selection'))}
            lang={lang}
            compact
          />
          <FlowNodeCard
            node={getNode('l5-library')}
            isSelected={selectedNodeId === 'l5-library'}
            onClick={() => onSelectNode(getNode('l5-library'))}
            lang={lang}
            compact
          />
        </div>
      </div>
    </div>
  );
};
