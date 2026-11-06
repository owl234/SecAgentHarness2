import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Terminal,
  Key,
  FileCode2,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  ShieldCheck,
  Copy,
  Check,
} from 'lucide-react';
import { BridgeStatus, ExecutorItem, UnifiedApiConfig } from '../../types';
import { DrawerTabId, ExecutorFormValues } from './executorTypes';
import { useLang } from '../../i18n/LangContext';
import { reprobeCodexBridge } from '../../api';

interface SubstrateConfigTabProps {
  selectedTab: Exclude<DrawerTabId, 'unified'>;
  activeExecutor: ExecutorItem;
  unifiedCfg?: UnifiedApiConfig;
  bridge?: BridgeStatus;
  form: ExecutorFormValues;
  updateForm: (patch: Partial<ExecutorFormValues>) => void;
  showApiKey: boolean;
  onToggleShowApiKey: () => void;
  bridgeBusy: boolean;
  onStartBridge: () => void;
  onStopBridge: () => void;
  onReprobeBridge?: () => void;
}

export const SubstrateConfigTab: React.FC<SubstrateConfigTabProps> = ({
  selectedTab,
  activeExecutor,
  unifiedCfg,
  bridge,
  form,
  updateForm,
  showApiKey,
  onToggleShowApiKey,
  bridgeBusy,
  onStartBridge,
  onStopBridge,
  onReprobeBridge,
}) => {
  const { tx } = useLang();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [isReprobing, setIsReprobing] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const handleReprobe = async () => {
    if (onReprobeBridge) {
      onReprobeBridge();
      return;
    }
    setIsReprobing(true);
    try {
      await reprobeCodexBridge();
    } catch (err) {
      console.error('Reprobe error:', err);
    } finally {
      setIsReprobing(false);
    }
  };

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
      {/* CLAUDE SUBSTRATE CONFIGURATION                          */}
      {/* ------------------------------------------------------- */}
      {selectedTab === 'claude' && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              {tx(
                'Claude 模型 ID (SEC_AGENT_HARNESS2_CLAUDE_MODEL · 留空默认复用统一 API 模型)',
                'Claude Model ID (SEC_AGENT_HARNESS2_CLAUDE_MODEL · blank inherits Unified API model)'
              )}
            </label>
            <input
              type="text"
              value={form.claudeModel}
              onChange={(e) => updateForm({ claudeModel: e.target.value })}
              placeholder="claude-sonnet-4-6"
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {activeExecutor.supported_models.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => updateForm({ claudeModel: m })}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded-md border cursor-pointer ${
                    form.claudeModel === m
                      ? 'bg-orange-500/15 text-orange-600 dark:text-orange-300 border-orange-500/40 font-semibold'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-orange-400'
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
                    '推理强度档位 (SEC_AGENT_HARNESS2_CLAUDE_EFFORT · 传递为 clawgod --effort)',
                    'Reasoning Effort (SEC_AGENT_HARNESS2_CLAUDE_EFFORT · passed as clawgod --effort)'
                  )}
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-orange-600 dark:text-orange-400 bg-orange-500/10 px-2.5 py-0.5 rounded-full border border-orange-500/20">
                {form.claudeEffort.toUpperCase()}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {(
                [
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
                  onClick={() => updateForm({ claudeEffort: opt.id })}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                    form.claudeEffort === opt.id
                      ? 'bg-orange-500/10 border-orange-500 text-orange-950 dark:text-orange-200 ring-1 ring-orange-500'
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
                {tx('专属端点覆盖 (SEC_AGENT_HARNESS2_CLAUDE_BASE_URL)', 'Endpoint Override (SEC_AGENT_HARNESS2_CLAUDE_BASE_URL)')}
              </label>
              <input
                type="text"
                value={form.claudeBaseUrl}
                onChange={(e) => updateForm({ claudeBaseUrl: e.target.value })}
                placeholder={
                  unifiedCfg?.base_url
                    ? tx(
                        `留空默认继承统一 API (${unifiedCfg.base_url})`,
                        `Blank inherits Unified API (${unifiedCfg.base_url})`
                      )
                    : 'https://api.anthropic.com'
                }
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx('线协议 (SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL)', 'Wire Protocol (SEC_AGENT_HARNESS2_CLAUDE_PROTOCOL)')}
              </label>
              <select
                value={form.claudeProtocol}
                onChange={(e) => updateForm({ claudeProtocol: e.target.value })}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">{tx('默认 (anthropic 原生 Messages)', 'Default (Anthropic Messages)')}</option>
                <option value="anthropic">anthropic (Anthropic Messages API)</option>
                <option value="openai-chat">
                  {tx('openai-chat (启用 clawgod provider.json 转换代理)', 'openai-chat (clawgod provider.json proxy)')}
                </option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {tx(
                    '专属密钥覆盖 (SEC_AGENT_HARNESS2_CLAUDE_API_KEY / ANTHROPIC_API_KEY)',
                    'API Key Override (SEC_AGENT_HARNESS2_CLAUDE_API_KEY / ANTHROPIC_API_KEY)'
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
              value={form.claudeApiKey}
              onChange={(e) => updateForm({ claudeApiKey: e.target.value })}
              placeholder={
                activeExecutor.api_key_configured
                  ? tx(
                      `已配置 (${activeExecutor.api_key_masked || '继承自统一API'}) · 留空保持不变`,
                      `Configured (${activeExecutor.api_key_masked || 'Inherited'}) · Leave blank to keep`
                    )
                  : 'sk-ant-...'
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
                    '项目隔离运行时 (dependencies/claude/bin/clawgod)',
                    'Isolated CLI Runtime (dependencies/claude/bin/clawgod)'
                  )}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                {activeExecutor.cli_available
                  ? activeExecutor.cli_path
                  : tx(
                      '未安装 · 请运行 sec-agent-harness2 setup <bench> --substrate claude',
                      'Not installed · Run sec-agent-harness2 setup <bench> --substrate claude'
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
              {activeExecutor.cli_available
                ? tx('clawgod 已就绪', 'clawgod Ready')
                : tx('待安装', 'Missing')}
            </span>
          </div>
        </div>
      )}

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
              placeholder="sec_agent_harness2/claude-sonnet-4-6"
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
        </div>
      )}

      {/* ------------------------------------------------------- */}
      {/* CODEX SUBSTRATE & RESPONSES BRIDGE CONFIGURATION        */}
      {/* ------------------------------------------------------- */}
      {selectedTab === 'cx' && (
        <div className="space-y-4">
          {/* Adaptive Wire Mode & Auto-Bridge Capsule */}
          <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                {bridge?.wire_mode === 'native' ? (
                  <span className="text-xs px-2.5 py-1 rounded-full font-bold bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                    {tx('直连上游原生 Responses 端点', 'Direct Native Responses Upstream')}
                  </span>
                ) : (
                  <span className="text-xs px-2.5 py-1 rounded-full font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                    {tx(
                      `已自动托管转换桥 (:${bridge?.port || 8765} · 安全鉴权激活)`,
                      `Auto-managed Bridge (:${bridge?.port || 8765} · Bearer Auth Active)`
                    )}
                  </span>
                )}
              </div>

              <button
                type="button"
                disabled={bridgeBusy || isReprobing}
                onClick={handleReprobe}
                className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isReprobing ? 'animate-spin text-blue-500' : ''}`} />
                <span>{isReprobing ? tx('正在探测...', 'Probing...') : tx('重新探测协议', 'Re-probe Wire API')}</span>
              </button>
            </div>

            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              {bridge?.wire_mode === 'native'
                ? tx(
                    '上游端点原生支持 /v1/responses，Codex 发起原生直连会话，零转译损耗并完整保留模型思维链。',
                    'Upstream natively supports /v1/responses. Codex connects directly with zero translation overhead and full reasoning support.'
                  )
                : tx(
                    `Codex 0.144.6 严格要求 wire_api = "responses"。系统已自动在后台常驻托管双向协议桥（基线端口 :${bridge?.port || 8765}），入站流量通过本地生成的 Bearer Key 强鉴权保护，零感知支持宿主机与 WorkBuddy Docker 容器穿透。`,
                    `Codex 0.144.6 requires wire_api = "responses". The system transparently manages a local bridge on :${bridge?.port || 8765} with inbound Bearer Token security, supporting host and Docker container rollouts.`
                  )}
            </p>

            {/* Collapsible Accordion: Advanced Protocol Settings & Diagnostics */}
            <div className="pt-1 border-t border-slate-200 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                className="text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white flex items-center gap-1.5 cursor-pointer select-none py-1"
              >
                {isAdvancedOpen ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-500" />}
                <span>{tx('折叠式高级协议配置与极客调试', 'Advanced Protocol Settings & Diagnostics')}</span>
              </button>

              {isAdvancedOpen && (
                <div className="mt-2.5 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-300 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">{tx('本地端点:', 'Local URL:')}</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">{bridge?.local_url || `http://127.0.0.1:${bridge?.port || 8765}/v1`}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">{tx('容器内穿透端点:', 'Container URL:')}</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">{bridge?.container_url || `http://host.docker.internal:${bridge?.port || 8765}/v1`}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">{tx('上游端点:', 'Upstream Target:')}</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200 truncate max-w-[260px]">{bridge?.upstream || unifiedCfg?.base_url || '-'}</span>
                  </div>
                  {bridge?.local_key && (
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">{tx('本地鉴权 Token:', 'Inbound Bearer Token:')}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{bridge.local_key_masked || '••••••••'}</span>
                        <button
                          type="button"
                          onClick={() => {
                            if (bridge.local_key) {
                              navigator.clipboard.writeText(bridge.local_key);
                              setCopiedKey(true);
                              setTimeout(() => setCopiedKey(false), 2000);
                            }
                          }}
                          className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded cursor-pointer text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                          title={tx('复制本地鉴权密钥', 'Copy Local Key')}
                        >
                          {copiedKey ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                    {bridge?.running && (
                      <button
                        type="button"
                        disabled={bridgeBusy}
                        onClick={onStopBridge}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-500/30 text-[11px] font-semibold cursor-pointer"
                      >
                        {tx('停止转换桥', 'Stop Bridge')}
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={bridgeBusy}
                      onClick={onStartBridge}
                      className="px-2.5 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 text-[11px] font-semibold cursor-pointer"
                    >
                      {tx('重启转换桥', 'Restart Bridge')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Config TOML status */}
          <div className="bg-slate-50 dark:bg-slate-950 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
            <div className="min-w-0 pr-2">
              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <FileCode2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span>{tx('CODEX_HOME/config.toml 状态校验', 'CODEX_HOME/config.toml Sync Status')}</span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                {activeExecutor.config_toml_status === 'ok'
                  ? tx(
                      'dependencies/codex/home/config.toml 与当前环境变量完全一致',
                      'dependencies/codex/home/config.toml matches current environment'
                    )
                  : activeExecutor.config_toml_error ||
                    tx(
                      '保存配置时将自动重新生成 config.toml',
                      'config.toml will be regenerated upon saving'
                    )}
              </div>
            </div>
            <span
              className={`px-2 py-0.5 rounded-md text-[10px] font-semibold shrink-0 ${
                activeExecutor.config_toml_status === 'ok'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
              }`}
            >
              {activeExecutor.config_toml_status === 'ok'
                ? tx('已同步', 'Synced')
                : tx('待同步', 'Pending')}
            </span>
          </div>

          {/* Codex Model ID */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              {tx(
                'Codex 模型 ID (SEC_AGENT_HARNESS2_CODEX_MODEL · 不带 provider 前缀)',
                'Codex Model ID (SEC_AGENT_HARNESS2_CODEX_MODEL · without provider prefix)'
              )}
            </label>
            <input
              type="text"
              value={form.cxModel}
              onChange={(e) => updateForm({ cxModel: e.target.value })}
              placeholder="gpt-5.4"
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {activeExecutor.supported_models.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => updateForm({ cxModel: m })}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded-md border cursor-pointer ${
                    form.cxModel === m
                      ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/40 font-semibold'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-emerald-400'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
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
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
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
