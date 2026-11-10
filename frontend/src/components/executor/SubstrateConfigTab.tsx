import React from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Terminal,
  Key,
  FileCode2,
} from 'lucide-react';
import { ExecutorItem, UnifiedApiConfig } from '../../types';
import { DrawerTabId, ExecutorFormValues } from './executorTypes';
import { useLang } from '../../i18n/LangContext';

interface SubstrateConfigTabProps {
  selectedTab: Exclude<DrawerTabId, 'unified'>;
  activeExecutor: ExecutorItem;
  unifiedCfg?: UnifiedApiConfig;
  form: ExecutorFormValues;
  updateForm: (patch: Partial<ExecutorFormValues>) => void;
  showApiKey: boolean;
  onToggleShowApiKey: () => void;
}

export const SubstrateConfigTab: React.FC<SubstrateConfigTabProps> = ({
  selectedTab,
  activeExecutor,
  unifiedCfg,
  form,
  updateForm,
  showApiKey,
  onToggleShowApiKey,
}) => {
  const { tx } = useLang();

  return (
    <>
      {/* Executor Status Banner */}
      <div
        className={`p-4 rounded-2xl border flex items-start gap-3 ${
          activeExecutor.status === 'ready'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-900 dark:text-emerald-300'
            : 'bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-300'
        }`}
      >
        {activeExecutor.status === 'ready' ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
        ) : (
          <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold uppercase tracking-wide">
              {activeExecutor.title}
            </span>
            {activeExecutor.using_unified && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30 font-semibold">
                {tx('正在复用统一 API', 'Inheriting Unified API')}
              </span>
            )}
          </div>
          <p className="text-xs mt-0.5 leading-relaxed break-all">
            {activeExecutor.status_message}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------- */}
      {/* OPENCODE SUBSTRATE CONFIGURATION                        */}
      {/* ------------------------------------------------------- */}
      {selectedTab === 'oc' && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              {tx(
                'OpenCode 求解器模型 (SEC_AGENT_HARNESS2_SOLVER_MODEL · 需带 provider/ 前缀)',
                'OpenCode Solver Model (SEC_AGENT_HARNESS2_SOLVER_MODEL · with provider/ prefix)'
              )}
            </label>
            <input
              type="text"
              value={form.ocModel}
              onChange={(e) => updateForm({ ocModel: e.target.value })}
              placeholder="sec_agent_harness2/gemini-2.5-pro"
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {activeExecutor.supported_models.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => updateForm({ ocModel: m })}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded-md border cursor-pointer ${
                    form.ocModel === m
                      ? 'bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-500/40 font-semibold'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-400 mt-1.5">
              {tx(
                '当配置了统一 API (SEC_AGENT_HARNESS2_API_BASE_URL) 时，系统会自动通过 OPENCODE_CONFIG_CONTENT 注入名为 sec_agent_harness2 的 Provider 块。',
                'When SEC_AGENT_HARNESS2_API_BASE_URL is set, Harness² automatically injects the "sec_agent_harness2" provider block via OPENCODE_CONFIG_CONTENT.'
              )}
            </p>
          </div>

          {/* Reasoning Effort Selector */}
          <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-blue-500" />
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  {tx(
                    '思考与推理强度 (SEC_AGENT_HARNESS2_OPENCODE_VARIANT · 传递为 --model <id>#<variant>)',
                    'Reasoning Effort (SEC_AGENT_HARNESS2_OPENCODE_VARIANT · passed as --model <id>#<variant>)'
                  )}
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 px-2.5 py-0.5 rounded-full border border-blue-500/20">
                {form.ocEffort.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(
                [
                  {
                    id: 'off',
                    label: tx('Off (关闭思考)', 'Off (No thinking)'),
                    desc: tx('基础模型直接输出', 'Raw model output'),
                  },
                  {
                    id: 'low',
                    label: tx('Low (轻量快速)', 'Low (Fast)'),
                    desc: tx('低延迟快速验证', 'Low-latency verification'),
                  },
                  {
                    id: 'medium',
                    label: tx('Medium (均衡)', 'Medium (Balanced)'),
                    desc: tx('兼顾速度与推理深度', 'Balanced speed & reasoning'),
                  },
                  {
                    id: 'high',
                    label: tx('High (推荐默认)', 'High (Recommended)'),
                    desc: tx('深度思考与严密自检', 'Deep thinking & verification'),
                  },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => updateForm({ ocEffort: opt.id })}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    form.ocEffort === opt.id
                      ? 'bg-blue-500/10 border-blue-500 text-blue-950 dark:text-blue-200 ring-1 ring-blue-500'
                      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  <div className="text-xs font-bold">{opt.label}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx(
                  '专属端点覆盖 (SEC_AGENT_HARNESS2_OPENCODE_BASE_URL)',
                  'Endpoint Override (SEC_AGENT_HARNESS2_OPENCODE_BASE_URL)'
                )}
              </label>
              <input
                type="text"
                value={form.ocBaseUrl}
                onChange={(e) => updateForm({ ocBaseUrl: e.target.value })}
                placeholder={
                  unifiedCfg?.base_url
                    ? tx(
                        `留空默认继承统一 API (${unifiedCfg.base_url})`,
                        `Blank inherits Unified API (${unifiedCfg.base_url})`
                      )
                    : 'https://your-openai-compatible.example.com/v1'
                }
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('SDK 协议包 (SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL)', 'SDK Protocol (SEC_AGENT_HARNESS2_OPENCODE_PROTOCOL)')}
              </label>
              <select
                value={form.ocProtocol}
                onChange={(e) => updateForm({ ocProtocol: e.target.value })}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">
                  {tx('默认 (openai-chat / @ai-sdk/openai-compatible)', 'Default (openai-chat / @ai-sdk/openai-compatible)')}
                </option>
                <option value="openai-chat">openai-chat (@ai-sdk/openai-compatible)</option>
                <option value="anthropic">anthropic (@ai-sdk/anthropic)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              {tx('专属 API Key 覆盖 (SEC_AGENT_HARNESS2_OPENCODE_API_KEY)', 'API Key Override (SEC_AGENT_HARNESS2_OPENCODE_API_KEY)')}
            </label>
            <input
              type={showApiKey ? 'text' : 'password'}
              value={form.ocApiKey}
              onChange={(e) => updateForm({ ocApiKey: e.target.value })}
              placeholder={
                activeExecutor.api_key_configured
                  ? tx(
                      `已配置 (${activeExecutor.api_key_masked || '继承自统一API / Vertex'}) · 留空保持不变`,
                      `Configured (${activeExecutor.api_key_masked || 'Inherited'}) · Leave blank to keep`
                    )
                  : tx('留空使用统一 API Key 或 Vertex ADC', 'Blank uses Unified API Key or Vertex ADC')
              }
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
            <div className="min-w-0 pr-2">
              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span>
                  {tx(
                    '项目隔离运行时 (packages/cli/src/index.ts · Bun 1.4.4)',
                    'Isolated CLI Runtime (packages/cli/src/index.ts · Bun 1.4.4)'
                  )}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                {activeExecutor.cli_available
                  ? activeExecutor.cli_path
                  : tx(
                      '未安装 · 请运行 sec-agent-harness2 setup <bench> --substrate oc',
                      'Not installed · Run sec-agent-harness2 setup <bench> --substrate oc'
                    )}
              </div>
            </div>
            <span
              className={`px-2 py-0.5 rounded-md text-[10px] font-semibold shrink-0 ${
                activeExecutor.cli_available
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
              }`}
            >
              {activeExecutor.cli_available ? tx('已就绪', 'Ready') : tx('待安装', 'Missing')}
            </span>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------- */}
      {/* PI CODING AGENT SUBSTRATE CONFIGURATION                */}
      {/* ------------------------------------------------------- */}
      {selectedTab === 'pi' && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              {tx(
                'Pi 模型 ID (SEC_AGENT_HARNESS2_PI_MODEL · 留空默认复用统一 API 模型)',
                'Pi Model ID (SEC_AGENT_HARNESS2_PI_MODEL · blank inherits Unified API model)'
              )}
            </label>
            <input
              type="text"
              value={form.piModel}
              onChange={(e) => updateForm({ piModel: e.target.value })}
              placeholder="gpt-5.4"
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {activeExecutor.supported_models.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => updateForm({ piModel: m })}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded-md border cursor-pointer ${
                    form.piModel === m
                      ? 'bg-pink-500/15 text-pink-600 dark:text-pink-300 border-pink-500/40 font-semibold'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-pink-400'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* Reasoning Effort Selector */}
          <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                  {tx(
                    '思考与推理强度 (SEC_AGENT_HARNESS2_PI_EFFORT · 传递为 pi --thinking)',
                    'Reasoning Effort (SEC_AGENT_HARNESS2_PI_EFFORT · passed as pi --thinking)'
                  )}
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-pink-600 dark:text-pink-400 bg-pink-500/10 px-2.5 py-0.5 rounded-full border border-pink-500/20">
                {form.piEffort.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(
                [
                  {
                    id: 'off',
                    label: tx('Off (关闭思考)', 'Off (No thinking)'),
                    desc: tx('禁用思维链扩展', 'Disable reasoning chain'),
                  },
                  {
                    id: 'low',
                    label: tx('Low (轻量快速)', 'Low (Fast)'),
                    desc: tx('低延迟快速验证', 'Low-latency verification'),
                  },
                  {
                    id: 'medium',
                    label: tx('Medium (均衡)', 'Medium (Balanced)'),
                    desc: tx('兼顾速度与推理深度', 'Balanced speed & reasoning'),
                  },
                  {
                    id: 'high',
                    label: tx('High (推荐默认)', 'High (Recommended)'),
                    desc: tx('深度思考与严密自检', 'Deep thinking & verification'),
                  },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => updateForm({ piEffort: opt.id })}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    form.piEffort === opt.id
                      ? 'bg-pink-500/10 border-pink-500 text-pink-950 dark:text-pink-200 ring-1 ring-pink-500'
                      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  <div className="text-xs font-bold">{opt.label}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('专属端点覆盖 (SEC_AGENT_HARNESS2_PI_BASE_URL)', 'Endpoint Override (SEC_AGENT_HARNESS2_PI_BASE_URL)')}
              </label>
              <input
                type="text"
                value={form.piBaseUrl}
                onChange={(e) => updateForm({ piBaseUrl: e.target.value })}
                placeholder={
                  unifiedCfg?.base_url
                    ? tx(
                        `留空默认继承统一 API (${unifiedCfg.base_url})`,
                        `Blank inherits Unified API (${unifiedCfg.base_url})`
                      )
                    : 'https://api.openai.com/v1'
                }
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('线协议 (SEC_AGENT_HARNESS2_PI_PROTOCOL)', 'Wire Protocol (SEC_AGENT_HARNESS2_PI_PROTOCOL)')}
              </label>
              <select
                value={form.piProtocol}
                onChange={(e) => updateForm({ piProtocol: e.target.value })}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">{tx('默认 (openai-chat Completions)', 'Default (openai-chat Completions)')}</option>
                <option value="openai-chat">openai-chat (OpenAI Chat / Completions)</option>
                <option value="openai-responses">openai-responses (OpenAI Responses API)</option>
                <option value="anthropic">anthropic (Anthropic Messages API)</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {tx(
                    '专属密钥覆盖 (SEC_AGENT_HARNESS2_PI_API_KEY)',
                    'API Key Override (SEC_AGENT_HARNESS2_PI_API_KEY)'
                  )}
                </span>
              </label>
              <button
                type="button"
                onClick={onToggleShowApiKey}
                className="text-[11px] text-blue-500 hover:underline cursor-pointer"
              >
                {showApiKey ? tx('隐藏密文', 'Hide Key') : tx('显示密文', 'Show Key')}
              </button>
            </div>
            <input
              type={showApiKey ? 'text' : 'password'}
              value={form.piApiKey}
              onChange={(e) => updateForm({ piApiKey: e.target.value })}
              placeholder={
                activeExecutor.api_key_configured
                  ? tx(
                      `已配置 (${activeExecutor.api_key_masked || '继承自统一API'}) · 留空保持不变`,
                      `Configured (${activeExecutor.api_key_masked || 'Inherited'}) · Leave blank to keep`
                    )
                  : 'sk-...'
              }
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
            <div className="min-w-0 pr-2">
              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span>
                  {tx(
                    '项目隔离运行时 (dependencies/pi/bin/pi)',
                    'Isolated CLI Runtime (dependencies/pi/bin/pi)'
                  )}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                {activeExecutor.cli_available
                  ? activeExecutor.cli_path
                  : tx(
                      '未安装 · 请运行 sec-agent-harness2 setup <bench> --substrate pi',
                      'Not installed · Run sec-agent-harness2 setup <bench> --substrate pi'
                    )}
              </div>
            </div>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold shrink-0 ${
                activeExecutor.cli_available
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
              }`}
            >
              {activeExecutor.cli_available ? tx('已就绪', 'Ready') : tx('待安装', 'Missing')}
            </span>
          </div>

          <div className="p-3 bg-pink-50/50 dark:bg-pink-950/20 border border-pink-200 dark:border-pink-800/50 rounded-xl text-xs space-y-1.5 text-slate-700 dark:text-slate-300">
            <div className="font-bold flex items-center gap-1.5 text-pink-700 dark:text-pink-300">
              <FileCode2 className="w-4 h-4 text-pink-500" />
              <span>{tx('Pi 原生 models.json 编译规范与无锁并发', 'Pi models.json Compilation Specification')}</span>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
              {tx(
                '通过独立 PI_CODING_AGENT_DIR 隔离 models.json，严格遵循 camelCase baseUrl 规范并写入 reasoning: true、maxTokens: 64000。',
                'Isolates models.json via distinct PI_CODING_AGENT_DIR, enforcing camelCase baseUrl, reasoning: true, and maxTokens: 64000.'
              )}
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------- */}
      {/* IMPROVER, JUDGE & VERTEX AI CONFIGURATION               */}
      {/* ------------------------------------------------------- */}
      {selectedTab === 'vertex' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('改进器模型 (SEC_AGENT_HARNESS2_IMPROVER_MODEL)', 'Improver Model (SEC_AGENT_HARNESS2_IMPROVER_MODEL)')}
              </label>
              <input
                type="text"
                value={form.improverModel}
                onChange={(e) => updateForm({ improverModel: e.target.value })}
                placeholder={
                  unifiedCfg?.effective_improver_model
                    ? tx(
                        `默认复用执行器 (${unifiedCfg.effective_improver_model})`,
                        `Defaults to solver (${unifiedCfg.effective_improver_model})`
                      )
                    : tx('留空默认复用 SOLVER_MODEL', 'Blank defaults to SOLVER_MODEL')
                }
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
              <p className="text-[10px] text-slate-400 mt-1">
                {tx(
                  '用于 Propose / Compose / Select 演进通道（OpenCode 语法需带 provider/ 前缀）。',
                  'Used for Propose / Compose / Select stages (include provider/ prefix for OpenCode).'
                )}
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('双盲裁判模型 (SEC_AGENT_HARNESS2_JUDGE_MODEL)', 'Blind Judge Model (SEC_AGENT_HARNESS2_JUDGE_MODEL)')}
              </label>
              <input
                type="text"
                value={form.judgeModel}
                onChange={(e) => updateForm({ judgeModel: e.target.value })}
                placeholder="gemini-2.5-pro"
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-purple-500"
              />
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {activeExecutor.supported_models.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => updateForm({ judgeModel: m })}
                    className="px-2 py-0.5 text-[10px] font-mono rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:border-purple-400 cursor-pointer"
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx(
                  '裁判专属端点 (SEC_AGENT_HARNESS2_JUDGE_BASE_URL · 可选)',
                  'Judge Endpoint (SEC_AGENT_HARNESS2_JUDGE_BASE_URL)'
                )}
              </label>
              <input
                type="text"
                value={form.judgeBaseUrl}
                onChange={(e) => updateForm({ judgeBaseUrl: e.target.value })}
                placeholder="https://your-judge-endpoint.example.com/v1"
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx(
                  '裁判专属密钥 (SEC_AGENT_HARNESS2_JUDGE_API_KEY · 可选)',
                  'Judge API Key (SEC_AGENT_HARNESS2_JUDGE_API_KEY)'
                )}
              </label>
              <input
                type={showApiKey ? 'text' : 'password'}
                value={form.judgeApiKey}
                onChange={(e) => updateForm({ judgeApiKey: e.target.value })}
                placeholder={
                  unifiedCfg?.judge_api_key_configured
                    ? tx(
                        `已配置 (${unifiedCfg.judge_api_key_masked}) · 留空保持不变`,
                        `Configured (${unifiedCfg.judge_api_key_masked}) · Leave blank to keep`
                      )
                    : tx('使用非 Vertex 裁判服务时填写', 'Optional key for non-Vertex judge')
                }
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-3">
            <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
              {tx(
                'Google Cloud Vertex AI 配置（仅在使用 google-vertex/* 模型或 Vertex 裁判时需要）',
                'Google Cloud Vertex AI Settings (Required only for google-vertex/* or Vertex Judge)'
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  {tx('GCP 项目 ID (GOOGLE_CLOUD_PROJECT)', 'GCP Project ID (GOOGLE_CLOUD_PROJECT)')}
                </label>
                <input
                  type="text"
                  value={form.vertexProject}
                  onChange={(e) => updateForm({ vertexProject: e.target.value })}
                  placeholder="your-gcp-project-id"
                  className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-white font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  {tx('Vertex 区域 (GOOGLE_CLOUD_LOCATION)', 'Vertex Location (GOOGLE_CLOUD_LOCATION)')}
                </label>
                <input
                  type="text"
                  value={form.vertexLocation}
                  onChange={(e) => updateForm({ vertexLocation: e.target.value })}
                  placeholder="global"
                  className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-white font-mono"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Capabilities List */}
      <div className="pt-3 border-t border-slate-200 dark:border-slate-800">
        <h4 className="text-xs font-bold text-slate-900 dark:text-white mb-2 uppercase tracking-wide">
          {tx('基座架构特性与能力边界', 'Substrate Surface & Capabilities')}
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
          {activeExecutor.capabilities.map((cap, idx) => (
            <div
              key={idx}
              className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800/80 text-slate-700 dark:text-slate-300"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />
              <span className="truncate" title={cap}>
                {cap}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
};
