import React from 'react';
import { X, BookOpen, Layers, Sparkles, Wrench, Terminal, Cpu } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { useEscapeKey } from './ui/ToastContext';

interface TerminologyGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TerminologyGuideModal: React.FC<TerminologyGuideModalProps> = ({ isOpen, onClose }) => {
  const { tx } = useLang();
  useEscapeKey(onClose, isOpen);

  if (!isOpen) return null;

  const coreConcepts = [
    {
      term: tx('智能体运行套件 (Harness)', 'Agent Harness'),
      desc: tx(
        '围绕底层大模型构建的一整套使之能够自主行动的运行环境，包括提示词、工具定义、记忆管理、安全护栏和自定义执行脚本。',
        'The complete surrounding runtime surface that turns a base model into an autonomous agent: prompts, tool contracts, memory, guardrails, subagents, skills, hooks, and scripts.'
      ),
      icon: Cpu,
      color: 'text-blue-500 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20',
    },
    {
      term: tx('套件递归优化', 'Recursive Harnessing'),
      desc: tx(
        '在冻结大模型权重不变的前提下，通过试跑对比自主发现缺陷并修改这套环境，让智能体在未知新任务中越用越强。',
        'Without updating model weights, an improver agent diagnoses trajectory flaws, proposes harness edits, probes them on the task, and composes stronger harnesses.'
      ),
      icon: Sparkles,
      color: 'text-amber-500 bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20',
    },
    {
      term: tx('OpenCode 与 Pi 双基座执行体系', 'OpenCode & Pi Dual-Substrate Architecture'),
      desc: tx(
        '基于 OpenCode (v2.2.7 Bun 运行时) 与 Pi Coding Agent (@earendil-works/pi-coding-agent) 的一等公民双执行底座，原生支持无锁并发与深度推理。',
        'First-class dual execution substrates powered by OpenCode (v2.2.7 Bun runtime) and Pi Coding Agent (@earendil-works/pi-coding-agent) with native concurrency and reasoning controls.'
      ),
      icon: Terminal,
      color: 'text-blue-500 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20',
    },
    {
      term: tx('诊断并提议', 'Diagnose & Propose Edits'),
      desc: tx(
        '优化器深入分析智能体在基线执行中的轨迹和交付物缺陷，提议通用规则修改 (INV) 或领域技能增强 (DOM)。',
        'Analyzes baseline rollout trajectories and deliverables to propose task-invariant rules (INV) and domain-specific enhancements (DOM).'
      ),
      icon: Wrench,
      color: 'text-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/20',
    },
    {
      term: tx('试跑探测', 'Probe Rollouts'),
      desc: tx(
        '在同一个具体任务中试运行被提议的候选套件，在无标注答案的情况下通过执行轨迹对比差异。',
        'Executes candidate harnesses on the same task without ground-truth labels, collecting empirical behavioral contrasts.'
      ),
      icon: Terminal,
      color: 'text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20',
    },
    {
      term: tx('融合提炼 (AGG / SEQ)', 'Compose & Distill (AGG / SEQ)'),
      desc: tx(
        '将通用改进与领域改进的高分亮点进行无缝融合，合成兼顾稳健性与专业能力的最终交付套件。',
        'Synthesizes validated invariant and domain edits into a final composed harness and records reusable lessons into the experience library.'
      ),
      icon: Layers,
      color: 'text-purple-500 bg-purple-50 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20',
    },
  ];

  const eightComponents = [
    {
      id: 'c1',
      name: tx('系统提示词', 'System Prompt'),
      role: tx('上下文', 'Context'),
      path: 'systemprompt.md',
      desc: tx(
        '设定智能体的角色定位、工作规范与第一性原理公理。',
        'Defines agent persona, core operating principles, and workflow axioms.'
      ),
    },
    {
      id: 'c2',
      name: tx('安全护栏', 'Guardrails'),
      role: tx('上下文', 'Context'),
      path: 'guardrails.md',
      desc: tx(
        '系统级与业务操作红线拦截，防止文件破坏与凭证泄漏。',
        'Hard safety invariants preventing destructive actions or credential leaks.'
      ),
    },
    {
      id: 'c3',
      name: tx('长期记忆', 'Long-Term Memory'),
      role: tx('上下文', 'Context'),
      path: 'LongTermMEMORY.md',
      desc: tx(
        '跨轮次与跨任务持久化保留的关键常识与状态。',
        'Persistent cross-task domain lessons, pitfalls, and verified heuristics.'
      ),
    },
    {
      id: 'c4',
      name: tx('工具指引', 'Tool Guidance'),
      role: tx('接口层', 'Interface'),
      path: 'tool_descriptions/tool_guidance.md',
      desc: tx(
        '规范 API 调用参数结构、异常重试与返回契约。',
        'Clarifies tool parameter contracts, retry protocols, and edge cases.'
      ),
    },
    {
      id: 'c5',
      name: tx('子智能体', 'Subagents'),
      role: tx('任务委派', 'Delegation'),
      path: 'sub_agents/<name>/AGENT.md',
      desc: tx(
        '定义委派分工体系与独立专家审查员子角色。',
        'Specialized delegated subagents (e.g., verifier, auditor, data analyst).'
      ),
    },
    {
      id: 'c6',
      name: tx('技能手册', 'Skills'),
      role: tx('上下文', 'Context'),
      path: 'skills/<name>/SKILL.md',
      desc: tx(
        '按需触发的专业技能规范文档与配套可执行脚本。',
        'On-demand domain playbooks and companion helper scripts.'
      ),
    },
    {
      id: 'c7',
      name: tx('独立脚本', 'Helper Scripts'),
      role: tx('接口层', 'Interface'),
      path: 'scripts/<name>.py',
      desc: tx(
        '直接供智能体调用的数据提取、格式清洗与语法校验脚本。',
        'Standalone CLI utilities for data parsing, validation, and verification.'
      ),
    },
    {
      id: 'c8',
      name: tx('事件钩子', 'Hooks / Plugins'),
      role: tx('中间件', 'Middleware'),
      path: 'plugins/<name>.ts',
      desc: tx(
        '网络拦截、调用前后耗时统计与执行沙箱安全插桩。',
        'Pre/post tool execution hooks, telemetry, and runtime policy enforcement.'
      ),
    },
    {
      id: 'c9',
      name: tx('MCP 协议服务', 'MCP Servers'),
      role: tx('协议层', 'Protocol'),
      path: 'mcp/servers.json + mcp/<name>.py',
      desc: tx(
        '跨轮次有状态工具服务、外部网安武器库桥接与三端基座原生 Tool Schema 挂载。',
        'Stateful protocol servers, security arsenal bridges, and cross-substrate native tool schemas.'
      ),
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/10 text-blue-600 dark:bg-blue-600/20 dark:text-blue-400 flex items-center justify-center">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                {tx('SecAgentHarness² 核心概念与图解指南', 'SecAgentHarness² Concepts & Architecture Guide')}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {tx(
                  '深入理解智能体套件递归自适应进化机制与 c1~c9 架构',
                  'Recursive Propose–Probe–Compose self-evolution and the c1..c9 harness surface'
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Core Concept Cards */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">
              {tx('核心运行机制', 'Core Evolution Mechanics')}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {coreConcepts.map((item, idx) => {
                const IconComponent = item.icon;
                return (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 flex flex-col"
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className={`p-1.5 rounded-lg border ${item.color}`}>
                        <IconComponent className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {item.term}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      {item.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 8 Components Grid */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">
              {tx(
                '可被自主定制与演进的 9 维 Harness 核心组件 (c1 ~ c9)',
                'The 9 Evolvable Harness Surface Components (c1 ~ c9)'
              )}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {eightComponents.map((comp) => (
                <div
                  key={comp.id}
                  className="p-3 rounded-xl border border-slate-200 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/30 flex items-start gap-2.5"
                >
                  <span className="text-[10px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded-md border border-blue-200 dark:border-blue-800 shrink-0 mt-0.5">
                    {comp.id.toUpperCase()}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                        {comp.name}
                      </p>
                      <span className="text-[10px] text-slate-400 font-mono">({comp.role})</span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {comp.desc}
                    </p>
                    <p className="text-[10px] text-slate-400 font-mono mt-1">
                      {tx('路径约定:', 'Surface Path:')} {comp.path}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors cursor-pointer"
          >
            {tx('知道了，返回控制台', 'Got it, back to Console')}
          </button>
        </div>
      </div>
    </div>
  );
};
