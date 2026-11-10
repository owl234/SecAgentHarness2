import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Cpu,
  X,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Bot,
  Zap,
  Globe,
  Activity,
  Key,
  ChevronDown,
  ChevronUp,
  Settings2,
  Scale,
  Search,
  Check,
  Layers,
  Sparkles,
} from 'lucide-react';
import {
  EndpointProbeResult,
  ExecutorStatusResponse,
} from '../types';
import {
  fetchExecutors,
  saveExecutorConfig,
  testExecutorEndpoint,
  fetchAvailableModels,
} from '../api';
import {
  ExecutorFormValues,
  INITIAL_EXECUTOR_FORM,
  buildFormFromExecutorsData,
} from './executor/executorTypes';
import { useLang } from '../i18n/LangContext';
import { useEscapeKey, useToast } from './ui/ToastContext';

interface ExecutorConfigDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onExecutorChanged?: () => void;
}

const DEFAULT_RECOMMENDED_MODELS = [
  'gemini-2.5-pro',
  'gpt-5.4',
  'deepseek-chat',
  'gpt-4o',
  'o3-mini',
  'qwen-2.5-coder-32b',
];

const RECOMMENDED_JUDGE_MODELS = [
  'gemini-2.5-pro',
  'gpt-4o',
  'o3-mini',
  'gpt-5.4',
];

export const ExecutorConfigDrawer: React.FC<ExecutorConfigDrawerProps> = ({
  isOpen,
  onClose,
  onExecutorChanged,
}) => {
  const { tx } = useLang();
  const { showToast } = useToast();
  useEscapeKey(onClose, isOpen);

  const [executorsData, setExecutorsData] = useState<ExecutorStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchedModels, setFetchedModels] = useState<string[]>([]);
  const [modelFetchMsg, setModelFetchMsg] = useState<{
    ok: boolean;
    message: string;
    latency_ms?: number;
  } | null>(null);

  const [probeResult, setProbeResult] = useState<EndpointProbeResult | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showJudgeApiKey, setShowJudgeApiKey] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // Unified model combobox dropdown state
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const [comboboxFilter, setComboboxFilter] = useState('');
  const comboboxRef = useRef<HTMLDivElement>(null);

  // Judge model combobox dropdown state
  const [judgeComboboxOpen, setJudgeComboboxOpen] = useState(false);
  const [judgeComboboxFilter, setJudgeComboboxFilter] = useState('');
  const judgeComboboxRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState<ExecutorFormValues>(INITIAL_EXECUTOR_FORM);

  const updateForm = useCallback((patch: Partial<ExecutorFormValues>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const applyExecutorsData = useCallback((data: ExecutorStatusResponse) => {
    setExecutorsData(data);
    setForm((prev) => buildFormFromExecutorsData(data, prev));
  }, []);

  const loadExecutors = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchExecutors();
      applyExecutorsData(data);
    } catch (err) {
      console.error('Failed to load executors:', err);
    } finally {
      setLoading(false);
    }
  }, [applyExecutorsData]);

  useEffect(() => {
    if (isOpen) {
      setProbeResult(null);
      setModelFetchMsg(null);
      loadExecutors();
    }
  }, [isOpen, loadExecutors]);

  // Click outside listener for the model & judge Comboboxes
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (comboboxRef.current && !comboboxRef.current.contains(event.target as Node)) {
        setComboboxOpen(false);
      }
      if (judgeComboboxRef.current && !judgeComboboxRef.current.contains(event.target as Node)) {
        setJudgeComboboxOpen(false);
      }
    };
    if (comboboxOpen || judgeComboboxOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [comboboxOpen, judgeComboboxOpen]);

  if (!isOpen) return null;

  const unifiedCfg = executorsData?.unified_config;
  const ocSub = executorsData?.executors.find((e) => e.id === 'oc');
  const piSub = executorsData?.executors.find((e) => e.id === 'pi');

  const hasApiKey = Boolean(form.unifiedApiKey || unifiedCfg?.api_key_configured);
  const isBaseReady = Boolean(form.unifiedBaseUrl && hasApiKey);

  const bareCurrentModel = form.unifiedModel.trim().replace(/^sec_agent_harness2\//, '');
  const bareCurrentJudge = form.judgeModel.trim().replace(/^sec_agent_harness2\//, '');
  // Shared candidate models pool for unified and judge comboboxes
  const candidateModels = Array.from(
    new Set([
      ...(bareCurrentModel ? [bareCurrentModel] : []),
      ...(bareCurrentJudge ? [bareCurrentJudge] : []),
      ...fetchedModels,
      ...DEFAULT_RECOMMENDED_MODELS,
      ...RECOMMENDED_JUDGE_MODELS,
    ])
  );
  const filteredModels = candidateModels.filter((m) =>
    m.toLowerCase().includes(comboboxFilter.toLowerCase())
  );
  const judgeFilteredModels = candidateModels.filter((m) =>
    m.toLowerCase().includes(judgeComboboxFilter.toLowerCase())
  );

  const handleFetchModels = async () => {
    if (!form.unifiedBaseUrl && !unifiedCfg?.base_url) {
      showToast(
        tx('请先填写统一 API 端点地址 (Base URL)', 'Please enter the Unified API Base URL first'),
        'error'
      );
      return;
    }
    setFetchingModels(true);
    setModelFetchMsg(null);
    try {
      const res = await fetchAvailableModels({
        base_url: form.unifiedBaseUrl || undefined,
        api_key: form.unifiedApiKey || undefined,
        protocol: form.unifiedProtocol || undefined,
      });
      setModelFetchMsg({
        ok: res.ok,
        message: res.message,
        latency_ms: res.latency_ms,
      });
      if (res.ok && res.models.length > 0) {
        setFetchedModels(res.models);
        setComboboxFilter('');
        setComboboxOpen(true);
        showToast(
          tx(
            `成功拉取 ${res.models.length} 个可用模型 (${res.latency_ms}ms)！`,
            `Successfully fetched ${res.models.length} models (${res.latency_ms}ms)!`
          ),
          'success'
        );
      } else if (res.ok) {
        showToast(res.message, 'info');
      } else {
        showToast(res.message, 'error');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setModelFetchMsg({
        ok: false,
        message: tx(`拉取模型失败: ${message}`, `Fetch models failed: ${message}`),
      });
      showToast(tx(`拉取模型失败: ${message}`, `Fetch models failed: ${message}`), 'error');
    } finally {
      setFetchingModels(false);
    }
  };

  const handleTestEndpoint = async () => {
    setTesting(true);
    setProbeResult(null);
    try {
      const res = await testExecutorEndpoint({
        target: 'unified',
        base_url: form.unifiedBaseUrl || undefined,
        api_key: form.unifiedApiKey || undefined,
        protocol: form.unifiedProtocol || undefined,
        model: form.unifiedModel || undefined,
      });
      setProbeResult(res);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setProbeResult({
        ok: false,
        target: 'unified',
        endpoint: form.unifiedBaseUrl || '',
        protocol: form.unifiedProtocol || '',
        status_code: null,
        latency_ms: 0,
        message: tx(`测试请求失败: ${message}`, `Endpoint probe failed: ${message}`),
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveUnifiedConfig = async () => {
    if (!form.unifiedModel.trim()) {
      showToast(
        tx('请选择或输入要应用的统一模型名称', 'Please select or enter a model name'),
        'error'
      );
      return;
    }
    const bareModel = form.unifiedModel.trim().replace(/^sec_agent_harness2\//, '');
    setSaving(true);
    try {
      const updated = await saveExecutorConfig({
        executor_id: 'unified',
        base_url: form.unifiedBaseUrl.trim(),
        api_key: form.unifiedApiKey ? form.unifiedApiKey.trim() : undefined,
        model: bareModel,
        protocol: form.unifiedProtocol !== undefined ? form.unifiedProtocol.trim() : '',
        effort: form.piEffort,
        oc_variant: form.ocEffort,
        judge_model: form.judgeModel.trim(),
        judge_base_url: form.judgeBaseUrl !== undefined ? form.judgeBaseUrl.trim() : '',
        judge_api_key: form.judgeApiKey ? form.judgeApiKey.trim() : undefined,
        persist_dotenv: true,
      });
      updateForm({ unifiedApiKey: '', judgeApiKey: '' });
      applyExecutorsData(updated);
      showToast(
        tx(
          `模型 "${bareModel}" 已成功同步应用至所有执行基座！`,
          `Model "${bareModel}" successfully applied to all substrates!`
        ),
        'success'
      );
      if (onExecutorChanged) onExecutorChanged();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      showToast(tx(`配置保存失败: ${message}`, `Save failed: ${message}`), 'error');
    } finally {
      setSaving(false);
    }
  };

  const bareModel = form.unifiedModel.trim().replace(/^sec_agent_harness2\//, '');
  const activeModelDisplay = bareModel || tx('(未选定模型)', '(No model selected)');
  const ocDerivedModel = bareModel ? `sec_agent_harness2/${bareModel}` : tx('(未选定)', '(None)');
  const isJudgeOverridden = Boolean(form.judgeModel.trim());

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 w-full max-w-2xl h-full flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-blue-500/20 via-indigo-500/20 to-orange-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 dark:text-white">
                  {tx('统一 API 与执行基座配置中心', 'Unified API & Executor Control Center')}
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  {tx('全基座一键对齐', 'All-Harness Live Alignment')}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                {tx(
                  '配置一组统一 API 与模型，自动编译分发至项目支持的所有执行套件（OpenCode / Pi / 改进器 / 裁判）',
                  'Configure one unified API and model to automatically compile & dispatch to all supported harnesses'
                )}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body - Scrollable */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Top Info Banner */}
          <div className="p-4 rounded-2xl border bg-gradient-to-r from-blue-500/10 via-indigo-500/5 to-transparent border-blue-500/30 text-slate-800 dark:text-slate-200">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
                <Globe className="w-4 h-4" />
                <span>{tx('极简统一网关驱动机制', 'Unified Gateway Architecture')}</span>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                  isBaseReady
                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                    : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                }`}
              >
                {isBaseReady
                  ? tx('端点凭据已就绪', 'Credentials Configured')
                  : tx('待填写端点与密钥', 'Needs Base URL & Key')}
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              {tx(
                '只需配置统一 Base URL 与 API Key，点击「获取模型」通过 API 动态检索上游支持的模型清单。选定模型后点击保存，系统将自动对齐所有基座环境变量并重编译物理配置，彻底消除历史旧配置屏蔽问题。',
                'Enter your Base URL and Key, then click "Fetch Models" to query the upstream catalog via API. Saving aligns all substrate environment variables and compiles physical configs seamlessly.'
              )}
            </p>
          </div>

          {/* Section 1: Endpoint & Key */}
          <div className="space-y-4 bg-slate-50 dark:bg-slate-950/60 p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
            {/* Base URL */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx(
                  '统一 API 端点地址 (SEC_AGENT_HARNESS2_API_BASE_URL)',
                  'Unified API Base URL (SEC_AGENT_HARNESS2_API_BASE_URL)'
                )}
              </label>
              <input
                type="text"
                value={form.unifiedBaseUrl}
                onChange={(e) => updateForm({ unifiedBaseUrl: e.target.value })}
                placeholder="https://your-endpoint.example.com/v1"
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* API Key */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-400" />
                  <span>
                    {tx(
                      '统一 API 密钥 (SEC_AGENT_HARNESS2_API_KEY)',
                      'Unified API Key (SEC_AGENT_HARNESS2_API_KEY)'
                    )}
                  </span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowApiKey((v) => !v)}
                  className="text-[11px] text-blue-500 hover:underline cursor-pointer"
                >
                  {showApiKey ? tx('隐藏密文', 'Hide Key') : tx('显示密文', 'Show Key')}
                </button>
              </div>
              <input
                type={showApiKey ? 'text' : 'password'}
                value={form.unifiedApiKey}
                onChange={(e) => updateForm({ unifiedApiKey: e.target.value })}
                placeholder={
                  unifiedCfg?.api_key_configured
                    ? tx(
                        `已配置 (${unifiedCfg.api_key_masked}) · 输入新密钥可覆盖，留空保持不变`,
                        `Configured (${unifiedCfg.api_key_masked}) · Enter new key to override, leave blank to keep`
                      )
                    : 'sk-...'
                }
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Protocol Override */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                {tx(
                  '协议模式 (SEC_AGENT_HARNESS2_API_PROTOCOL · 留空自动适配)',
                  'Protocol Mode (SEC_AGENT_HARNESS2_API_PROTOCOL)'
                )}
              </label>
              <select
                value={form.unifiedProtocol}
                onChange={(e) => updateForm({ unifiedProtocol: e.target.value })}
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">{tx('自动按基座线协议适配 (推荐)', 'Auto-adapt per substrate (Recommended)')}</option>
                <option value="openai-chat">openai-chat (OpenAI Chat Completions)</option>
                <option value="anthropic">anthropic (Anthropic Messages)</option>
                <option value="openai-responses">openai-responses (OpenAI Responses)</option>
              </select>
            </div>

            {/* Action Bar: Fetch Models & Test Endpoint */}
            <div className="flex flex-wrap items-center gap-2.5 pt-1">
              <button
                type="button"
                disabled={fetchingModels}
                onClick={handleFetchModels}
                className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-xl shadow-sm transition-all cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${fetchingModels ? 'animate-spin' : ''}`} />
                <span>
                  {fetchingModels
                    ? tx('正在通过 API 获取模型...', 'Fetching Models via API...')
                    : tx('获取可用模型清单', 'Fetch Models via API')}
                </span>
              </button>

              <button
                type="button"
                disabled={testing}
                onClick={handleTestEndpoint}
                className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl transition-all cursor-pointer disabled:opacity-50"
              >
                <Activity className={`w-3.5 h-3.5 text-blue-500 ${testing ? 'animate-pulse' : ''}`} />
                <span>
                  {testing
                    ? tx('探测连通性中...', 'Testing Connectivity...')
                    : tx('测试端点连通性', 'Test Connectivity')}
                </span>
              </button>

              {modelFetchMsg && (
                <div
                  className={`text-xs px-2.5 py-1.5 rounded-lg border flex items-center gap-1.5 font-medium ${
                    modelFetchMsg.ok
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-700 dark:text-rose-300'
                  }`}
                >
                  {modelFetchMsg.ok ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                  )}
                  <span>{modelFetchMsg.message}</span>
                </div>
              )}
            </div>

            {/* Endpoint Probe Result Card */}
            {probeResult && (
              <div
                className={`p-3 rounded-xl border flex items-start justify-between gap-3 text-xs ${
                  probeResult.ok
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-900 dark:text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-900 dark:text-rose-300'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {probeResult.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <div className="font-bold">
                      {probeResult.ok
                        ? tx('端点连通性探测通过', 'Endpoint Connectivity Probe Passed')
                        : tx('端点连通性探测异常', 'Endpoint Connectivity Probe Failed')}
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] opacity-90">
                      {probeResult.message}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setProbeResult(null)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Section 2: Searchable Combobox Model Selector */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <span>
                  {tx(
                    '统一模型选择 (SEC_AGENT_HARNESS2_API_MODEL)',
                    'Unified Model (SEC_AGENT_HARNESS2_API_MODEL)'
                  )}
                </span>
              </label>
              <span className="text-[11px] text-slate-500 dark:text-slate-400">
                {fetchedModels.length > 0
                  ? tx(`已从 API 检索 ${fetchedModels.length} 个模型`, `${fetchedModels.length} models retrieved via API`)
                  : tx('支持自由输入或从下拉选择', 'Freeform input or pick from dropdown')}
              </span>
            </div>

            {/* Combobox Input with Dropdown Toggle */}
            <div className="relative" ref={comboboxRef}>
              <div className="flex items-center relative">
                <input
                  type="text"
                  value={form.unifiedModel}
                  onChange={(e) => {
                    updateForm({ unifiedModel: e.target.value });
                    setComboboxFilter(e.target.value);
                    setComboboxOpen(true);
                  }}
                  onFocus={() => {
                    setComboboxFilter('');
                    setComboboxOpen(true);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape' && comboboxOpen) {
                      e.stopPropagation();
                      setComboboxOpen(false);
                    } else if (e.key === 'Enter' && comboboxOpen) {
                      setComboboxOpen(false);
                    }
                  }}
                  placeholder={tx('输入或选择模型，例如: gemini-2.5-pro', 'Type or select model, e.g. gemini-2.5-pro')}
                  className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl pl-3.5 pr-10 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500 shadow-sm"
                />
                <button
                  type="button"
                  onClick={() => {
                    setComboboxFilter('');
                    setComboboxOpen((v) => !v);
                  }}
                  className="absolute right-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded cursor-pointer"
                  title={tx('切换模型列表', 'Toggle model dropdown')}
                >
                  {comboboxOpen ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Combobox Dropdown Menu */}
              {comboboxOpen && (
                <div className="absolute z-30 left-0 right-0 mt-1.5 max-h-60 overflow-y-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-1.5 space-y-1">
                  <div className="px-2.5 py-1.5 text-[10px] text-slate-400 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 mb-1">
                    <span className="flex items-center gap-1">
                      <Search className="w-3 h-3" />
                      <span>{tx('过滤匹配模型', 'Filter Models')}</span>
                    </span>
                    <span>
                      {filteredModels.length} / {candidateModels.length}
                    </span>
                  </div>

                  {filteredModels.map((m) => {
                    const isSelected = form.unifiedModel === m;
                    const isFetched = fetchedModels.includes(m);
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => {
                          updateForm({ unifiedModel: m });
                          setComboboxOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 text-left rounded-lg text-xs font-mono transition-colors cursor-pointer ${
                          isSelected
                            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-semibold'
                            : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          {isSelected && <Check className="w-3.5 h-3.5 text-blue-500 shrink-0" />}
                          <span className="truncate">{m}</span>
                        </div>
                        <span className="text-[10px] text-slate-400 font-sans shrink-0 ml-2">
                          {isFetched ? tx('API 端点', 'API Endpoint') : tx('推荐预设', 'Preset')}
                        </span>
                      </button>
                    );
                  })}

                  {filteredModels.length === 0 && (
                    <div className="px-3 py-3 text-center text-xs text-slate-500 dark:text-slate-400">
                      <div>{tx('未找到匹配的已知模型', 'No matching preset models found')}</div>
                      <button
                        type="button"
                        onClick={() => setComboboxOpen(false)}
                        className="mt-1.5 text-[11px] text-blue-500 hover:underline cursor-pointer"
                      >
                        {tx(`直接使用输入的 "${form.unifiedModel}"`, `Use typed "${form.unifiedModel}"`)}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Quick Recommended Chips */}
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[11px] text-slate-400 mr-1 flex items-center gap-1">
                <span>{tx('快速填选:', 'Quick Pick:')}</span>
              </span>
              {DEFAULT_RECOMMENDED_MODELS.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => updateForm({ unifiedModel: m })}
                  className={`px-2.5 py-1 text-[11px] font-mono rounded-lg border transition-all cursor-pointer ${
                    form.unifiedModel === m
                      ? 'bg-blue-500 text-white border-blue-500 shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 hover:bg-blue-500/10 hover:text-blue-500 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            {/* Sub-Section 2.2: 独立评估裁判模型 Combobox (Ghost Sync) */}
            <div className="pt-3 border-t border-slate-200/70 dark:border-slate-800/70 space-y-2.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  <Scale className="w-4 h-4 text-indigo-500" />
                  <span>
                    {tx(
                      '独立评估裁判模型 (SEC_AGENT_HARNESS2_JUDGE_MODEL)',
                      'Independent Judge Model (SEC_AGENT_HARNESS2_JUDGE_MODEL)'
                    )}
                  </span>
                  {isJudgeOverridden && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded font-mono font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                      {tx('独立覆盖', 'Override')}
                    </span>
                  )}
                </label>
                <div className="flex items-center gap-2">
                  {form.judgeModel.trim() && (
                    <button
                      type="button"
                      onClick={() => {
                        updateForm({ judgeModel: '' });
                        showToast(
                          tx('已复位裁判模型为跟随统一模型', 'Judge model reset to sync with unified model'),
                          'info'
                        );
                      }}
                      className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer font-medium"
                      title={tx('清除独立裁判模型设置，默认与统一模型保持一致', 'Clear override and follow unified model')}
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>{tx('一键复位跟随统一模型', 'Reset to Unified')}</span>
                    </button>
                  )}
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    {form.judgeModel.trim()
                      ? tx('专有裁判模型已生效', 'Custom judge model active')
                      : tx('留空默认跟随统一模型', 'Default: Follows Unified Model')}
                  </span>
                </div>
              </div>

              {/* Judge Combobox Input with Dropdown Toggle */}
              <div className="relative" ref={judgeComboboxRef}>
                <div className="flex items-center relative">
                  <input
                    type="text"
                    value={form.judgeModel}
                    onChange={(e) => {
                      updateForm({ judgeModel: e.target.value });
                      setJudgeComboboxFilter(e.target.value);
                      setJudgeComboboxOpen(true);
                    }}
                    onFocus={() => {
                      setJudgeComboboxFilter('');
                      setJudgeComboboxOpen(true);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape' && judgeComboboxOpen) {
                        e.stopPropagation();
                        setJudgeComboboxOpen(false);
                      } else if (e.key === 'Enter' && judgeComboboxOpen) {
                        setJudgeComboboxOpen(false);
                      }
                    }}
                    placeholder={
                      form.judgeModel.trim()
                        ? ''
                        : tx(
                            `跟随统一模型 (当前: ${bareModel || tx('未选定', 'None')})`,
                            `Sync with Unified Model (Current: ${bareModel || 'None'})`
                          )
                    }
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl pl-3.5 pr-10 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-indigo-500 shadow-sm placeholder:text-slate-400 dark:placeholder:text-slate-500 placeholder:font-sans"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setJudgeComboboxFilter('');
                      setJudgeComboboxOpen((v) => !v);
                    }}
                    className="absolute right-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded cursor-pointer"
                    title={tx('切换裁判模型列表', 'Toggle judge model dropdown')}
                  >
                    {judgeComboboxOpen ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                </div>

                {/* Judge Combobox Dropdown Menu */}
                {judgeComboboxOpen && (
                  <div className="absolute z-30 left-0 right-0 mt-1.5 max-h-60 overflow-y-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl p-1.5 space-y-1">
                    <div className="px-2.5 py-1.5 text-[10px] text-slate-400 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 mb-1">
                      <span className="flex items-center gap-1">
                        <Search className="w-3 h-3" />
                        <span>{tx('过滤匹配裁判模型', 'Filter Judge Models')}</span>
                      </span>
                      <span>
                        {judgeFilteredModels.length} / {candidateModels.length}
                      </span>
                    </div>

                    {/* Sync Option (Ghost Sync Option) */}
                    <button
                      type="button"
                      onClick={() => {
                        updateForm({ judgeModel: '' });
                        setJudgeComboboxOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3 py-2 text-left rounded-lg text-xs font-mono transition-colors cursor-pointer ${
                        !form.judgeModel.trim()
                          ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-semibold'
                          : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200'
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        {!form.judgeModel.trim() && <Check className="w-3.5 h-3.5 text-indigo-500 shrink-0" />}
                        <span className="font-sans font-medium text-slate-900 dark:text-white">
                          {tx(
                            `跟随统一模型 (当前: ${bareModel || tx('未选定', 'None')})`,
                            `Sync with Unified Model (Current: ${bareModel || 'None'})`
                          )}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-sans shrink-0 ml-2">
                        {tx('默认联动', 'Default Sync')}
                      </span>
                    </button>

                    {judgeFilteredModels.map((m) => {
                      const isSelected = form.judgeModel === m;
                      const isFetched = fetchedModels.includes(m);
                      return (
                        <button
                          key={m}
                          type="button"
                          onClick={() => {
                            updateForm({ judgeModel: m });
                            setJudgeComboboxOpen(false);
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2 text-left rounded-lg text-xs font-mono transition-colors cursor-pointer ${
                            isSelected
                              ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-semibold'
                              : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            {isSelected && <Check className="w-3.5 h-3.5 text-indigo-500 shrink-0" />}
                            <span className="truncate">{m}</span>
                          </div>
                          <span className="text-[10px] text-slate-400 font-sans shrink-0 ml-2">
                            {isFetched ? tx('API 端点', 'API Endpoint') : tx('推荐预设', 'Preset')}
                          </span>
                        </button>
                      );
                    })}

                    {judgeFilteredModels.length === 0 && (
                      <div className="px-3 py-3 text-center text-xs text-slate-500 dark:text-slate-400">
                        <div>{tx('未找到匹配的已知模型', 'No matching preset models found')}</div>
                        <button
                          type="button"
                          onClick={() => setJudgeComboboxOpen(false)}
                          className="mt-1.5 text-[11px] text-indigo-500 hover:underline cursor-pointer"
                        >
                          {tx(`直接使用输入的 "${form.judgeModel}"`, `Use typed "${form.judgeModel}"`)}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Quick Recommended Judge Chips */}
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-[11px] text-slate-400 mr-1 flex items-center gap-1">
                  <span>{tx('推荐裁判:', 'Recommended Judges:')}</span>
                </span>
                {RECOMMENDED_JUDGE_MODELS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => updateForm({ judgeModel: m })}
                    className={`px-2.5 py-1 text-[11px] font-mono rounded-lg border transition-all cursor-pointer ${
                      form.judgeModel === m
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                        : 'bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 hover:bg-indigo-500/10 hover:text-indigo-500 border-slate-200 dark:border-slate-700'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Section 3: 全基座生效联动矩阵 (Harness Live Matrix) */}
          <div className="space-y-3 bg-slate-50 dark:bg-slate-950 p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-900 dark:text-white">
                <Layers className="w-4 h-4 text-blue-500" />
                <span>{tx('全基座生效联动矩阵 (Harness Live Matrix)', 'All-Harness Live Alignment Matrix')}</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-medium">
                {tx('保存时自动分发更新', 'Auto-dispatched on save')}
              </span>
            </div>

            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {tx(
                '保存后，所选模型将一次性编译并分发至项目所支持的全部 4 大基座与角色通道：',
                'Upon save, the selected model compiles and dispatches to all 4 substrates & role channels:'
              )}
            </p>

            {/* Matrix Cards */}
            <div className="grid grid-cols-1 gap-2 text-xs">
              {/* 1. OpenCode */}
              <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <span>OpenCode (oc)</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        openai-chat (virtual provider)
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {tx('派生模型: ', 'Mapped model: ')}
                      <span className="font-mono text-blue-600 dark:text-blue-400 font-semibold">
                        {ocDerivedModel}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      ocSub?.status === 'ready' ? 'bg-emerald-500' : 'bg-emerald-400'
                    }`}
                  />
                  <span className="text-slate-600 dark:text-slate-400 font-medium">
                    {tx('就绪', 'Ready')}
                  </span>
                </div>
              </div>

              {/* 2. Pi Coding Agent */}
              <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-pink-500/10 text-pink-500 border border-pink-500/20">
                    <Activity className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <span>Pi Coding Agent (pi)</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {form.unifiedProtocol === 'anthropic' ? 'anthropic-messages' : 'openai-completions'}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {tx('派生模型: ', 'Mapped model: ')}
                      <span className="font-mono text-blue-600 dark:text-blue-400 font-semibold">
                        {activeModelDisplay}
                      </span>
                      <span className="text-slate-400 text-[10px] ml-1.5">
                        {tx('→ 自动写入 models.json', '→ Written to models.json')}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      piSub?.status === 'ready' ? 'bg-emerald-500' : 'bg-slate-400'
                    }`}
                  />
                  <span className="text-slate-600 dark:text-slate-400 font-medium">
                    {piSub?.status === 'ready' ? tx('就绪', 'Ready') : tx('待配置', 'Pending')}
                  </span>
                </div>
              </div>

              {/* 3. Improver */}
              <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-500 border border-purple-500/20">
                    <Zap className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <span>{tx('提议改进器 (Improver)', 'Proposer & Improver')}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        channel-adapted
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {tx('派生模型: ', 'Mapped model: ')}
                      <span className="font-mono text-blue-600 dark:text-blue-400 font-semibold">
                        {ocDerivedModel}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-slate-600 dark:text-slate-400 font-medium">
                    {tx('联动就绪', 'Aligned')}
                  </span>
                </div>
              </div>

              {/* 4. Judge */}
              <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                    <Scale className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                      <span>{tx('评估裁判 (Judge)', 'Benchmark Judge')}</span>
                      {form.judgeBaseUrl && form.judgeBaseUrl.trim() && form.judgeBaseUrl.trim() !== form.unifiedBaseUrl.trim() ? (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-medium">
                          {tx('独立专有端点 (custom-url)', 'Dedicated (custom-url)')}
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium">
                          {tx('共享统一 API (shared-endpoint)', 'Shared (shared-endpoint)')}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] mt-0.5 flex items-center gap-1">
                      {isJudgeOverridden ? (
                        <>
                          <span className="text-slate-400">{tx('独立评估裁判: ', 'Independent Judge: ')}</span>
                          <span className="font-mono text-purple-600 dark:text-purple-400 font-semibold">
                            {form.judgeModel.trim()}
                          </span>
                          <span className="text-amber-500 text-[10px] ml-1">
                            {tx('(独立覆盖)', '(Override)')}
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="text-slate-400">{tx('同步基座模型: ', 'Synced with Base: ')}</span>
                          <span className="font-mono text-blue-600 dark:text-blue-400 font-semibold">
                            {activeModelDisplay}
                          </span>
                          <span className="text-emerald-500 text-[10px] ml-1">
                            {tx('(跟随统一)', '(Synced)')}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-slate-600 dark:text-slate-400 font-medium">
                    {tx('就绪', 'Ready')}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Section 4: Collapsible Advanced Substrate Overrides Accordion */}
          <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden bg-white dark:bg-slate-900">
            <button
              type="button"
              onClick={() => setIsAdvancedOpen((v) => !v)}
              className="w-full flex items-center justify-between p-4 bg-slate-50/70 dark:bg-slate-950/70 hover:bg-slate-100/70 dark:hover:bg-slate-950 text-left cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Settings2 className="w-4 h-4 text-slate-500" />
                <div>
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
                    {tx('基座高级微调与裁判专有配置 (可选)', 'Advanced Substrate Overrides & Judge Endpoints (Optional)')}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    {tx(
                      'OpenCode 与 Pi 思考强度及可选裁判专有端点/密钥（默认共享统一 API）',
                      'OpenCode & Pi reasoning effort and optional judge endpoint/key (shares unified API by default)'
                    )}
                  </div>
                </div>
              </div>
              <div className="text-slate-400">
                {isAdvancedOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </button>

            {isAdvancedOpen && (
              <div className="p-4 space-y-4 border-t border-slate-200 dark:border-slate-800">
                {/* 1. OpenCode Effort */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      {tx(
                        'OpenCode 思考变体与推理强度 (SEC_AGENT_HARNESS2_OPENCODE_VARIANT · 传递为 --model <id>#<variant>)',
                        'OpenCode Reasoning Effort (SEC_AGENT_HARNESS2_OPENCODE_VARIANT · passed as --model <id>#<variant>)'
                      )}
                    </label>
                    <span className="text-[10px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
                      {form.ocEffort.toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {(['off', 'low', 'medium', 'high'] as const).map((eff) => (
                      <button
                        key={eff}
                        type="button"
                        onClick={() => updateForm({ ocEffort: eff })}
                        className={`py-1.5 text-xs font-medium rounded-xl border transition-all cursor-pointer ${
                          form.ocEffort === eff
                            ? 'bg-blue-600 text-white border-blue-600 shadow-sm font-semibold'
                            : 'bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-slate-300'
                        }`}
                      >
                        {eff.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    {tx(
                      '非 OFF 时自动拼装为 #variant 并开启 --thinking 开关。',
                      'Appends #variant to model and enables --thinking unless set to OFF.'
                    )}
                  </p>
                </div>

                {/* 2. Pi Effort */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      {tx('Pi Coding Agent 推理与思考强度 (SEC_AGENT_HARNESS2_PI_EFFORT · 传递为 pi --thinking)', 'Pi Coding Agent Reasoning & Thinking (SEC_AGENT_HARNESS2_PI_EFFORT · passed as pi --thinking)')}
                    </label>
                    <span className="text-[10px] font-mono font-bold text-pink-600 dark:text-pink-400 bg-pink-500/10 px-2 py-0.5 rounded-full border border-pink-500/20">
                      {form.piEffort.toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {(['off', 'low', 'medium', 'high'] as const).map((eff) => (
                      <button
                        key={eff}
                        type="button"
                        onClick={() => updateForm({ piEffort: eff })}
                        className={`py-1.5 text-xs font-medium rounded-xl border transition-all cursor-pointer ${
                          form.piEffort === eff
                            ? 'bg-pink-600 text-white border-pink-600 shadow-sm font-semibold'
                            : 'bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-slate-300'
                        }`}
                      >
                        {eff.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    {tx(
                      '控制 Pi 在思考模式下的推理深度与思考预算。OFF 档位彻底关闭思维链。',
                      'Controls the reasoning depth and thinking budget for Pi. OFF completely disables reasoning.'
                    )}
                  </p>
                </div>

                {/* 3. Judge Endpoint & API Key Overrides (Model selection is unified in Section 2) */}
                <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                      {tx(
                        '裁判专有 API 端点与密钥覆盖 (可选 · 留空默认共享统一 API)',
                        'Judge Endpoint & Key Overrides (Optional · Shares Unified API by Default)'
                      )}
                    </label>
                    <span className="text-[10px] text-slate-400">
                      {tx('留空即共享统一 API', 'Leave blank to share unified API')}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-relaxed">
                    {tx(
                      '裁判模型已直接在上方「统一模型选择」区域统筹管理。若裁判需要使用专有独立端点或不同 API 密钥，可在此单独覆盖；留空时自动复用统一 API 的 Base URL 和 Key。',
                      'Judge model selection is directly managed in Section 2 above. If the judge requires a dedicated endpoint or separate API key, configure them here; leaving blank automatically shares the unified API Base URL and Key.'
                    )}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                        {tx('裁判专属端点 (SEC_AGENT_HARNESS2_JUDGE_BASE_URL · 可选)', 'Custom Judge Base URL (Optional)')}
                      </label>
                      <input
                        type="text"
                        value={form.judgeBaseUrl}
                        onChange={(e) => updateForm({ judgeBaseUrl: e.target.value })}
                        placeholder={
                          unifiedCfg?.judge_base_url && unifiedCfg.judge_base_url !== (unifiedCfg.base_url || '')
                            ? tx(`当前专有端点: ${unifiedCfg.judge_base_url}`, `Custom endpoint: ${unifiedCfg.judge_base_url}`)
                            : tx('留空默认共享统一 Base URL', 'Leave blank to share Unified Base URL')
                        }
                        className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                          {tx('裁判专属密钥 (SEC_AGENT_HARNESS2_JUDGE_API_KEY · 可选)', 'Custom Judge API Key (Optional)')}
                        </label>
                        <button
                          type="button"
                          onClick={() => setShowJudgeApiKey((v) => !v)}
                          className="text-[10px] text-blue-500 hover:underline cursor-pointer"
                        >
                          {showJudgeApiKey ? tx('隐藏', 'Hide') : tx('显示', 'Show')}
                        </button>
                      </div>
                      <input
                        type={showJudgeApiKey ? 'text' : 'password'}
                        value={form.judgeApiKey}
                        onChange={(e) => updateForm({ judgeApiKey: e.target.value })}
                        placeholder={
                          unifiedCfg?.judge_api_key_configured
                            ? tx(`已配置 (${unifiedCfg.judge_api_key_masked})`, `Configured (${unifiedCfg.judge_api_key_masked})`)
                            : tx('留空默认共享统一密钥', 'Leave blank to share Unified Key')
                        }
                        className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadExecutors}
              className="flex items-center gap-1.5 px-3 py-2 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{tx('刷新状态', 'Refresh')}</span>
            </button>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl cursor-pointer"
            >
              {tx('关闭', 'Close')}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSaveUnifiedConfig}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-500/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {saving ? (
                <span>{tx('全基座编译分发中...', 'Applying to all harnesses...')}</span>
              ) : (
                <span>{tx('保存并应用到所有基座', 'Save & Apply to All Harnesses')}</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
