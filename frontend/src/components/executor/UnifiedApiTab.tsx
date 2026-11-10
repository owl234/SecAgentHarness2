import React from 'react';
import { Globe, Key, Link2 } from 'lucide-react';
import { ExecutorStatusResponse } from '../../types';
import { ExecutorFormValues } from './executorTypes';
import { useLang } from '../../i18n/LangContext';

interface UnifiedApiTabProps {
  executorsData: ExecutorStatusResponse | null;
  form: ExecutorFormValues;
  updateForm: (patch: Partial<ExecutorFormValues>) => void;
  showApiKey: boolean;
  onToggleShowApiKey: () => void;
}

export const UnifiedApiTab: React.FC<UnifiedApiTabProps> = ({
  executorsData,
  form,
  updateForm,
  showApiKey,
  onToggleShowApiKey,
}) => {
  const { tx } = useLang();
  const unifiedCfg = executorsData?.unified_config;
  const isUnifiedReady = Boolean(unifiedCfg?.base_url && unifiedCfg?.api_key_configured);

  return (
    <div className="space-y-5">
      <div className="p-4 rounded-2xl border bg-gradient-to-r from-blue-500/10 via-indigo-500/5 to-transparent border-blue-500/30 text-slate-800 dark:text-slate-200">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
            <Globe className="w-4 h-4" />
            <span>{tx('统一 API 网关接入 (sec_agent_harness2/api.py)', 'Unified API Gateway (sec_agent_harness2/api.py)')}</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
              isUnifiedReady
                ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
            }`}
          >
            {isUnifiedReady
              ? tx('已激活统一接入', 'Unified Gateway Active')
              : tx('未设置统一端点', 'Unified Endpoint Not Set')}
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {tx(
            '只需填写一组 SEC_AGENT_HARNESS2_API_BASE_URL 与 SEC_AGENT_HARNESS2_API_KEY，系统会自动按各 CLI 的线协议完成适配：OpenCode 自动生成 harness2/<model> Provider 块，Pi Coding Agent 自动适配 models.json。',
            'Configure SEC_AGENT_HARNESS2_API_BASE_URL and SEC_AGENT_HARNESS2_API_KEY once: Harness² automatically adapts wire protocols across OpenCode (harness2/<model> provider block) and Pi Coding Agent (models.json).'
          )}
        </p>
      </div>

      {/* Base URL */}
      <div>
        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
          {tx('统一 API 端点地址 (SEC_AGENT_HARNESS2_API_BASE_URL)', 'Unified API Base URL (SEC_AGENT_HARNESS2_API_BASE_URL)')}
        </label>
        <input
          type="text"
          value={form.unifiedBaseUrl}
          onChange={(e) => updateForm({ unifiedBaseUrl: e.target.value })}
          placeholder="https://your-endpoint.example.com/v1"
          className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* API Key */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5 text-slate-400" />
            <span>{tx('统一 API 密钥 (SEC_AGENT_HARNESS2_API_KEY)', 'Unified API Key (SEC_AGENT_HARNESS2_API_KEY)')}</span>
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
          className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Unified Model + Protocol */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
            {tx('默认模型 ID (SEC_AGENT_HARNESS2_API_MODEL)', 'Default Model ID (SEC_AGENT_HARNESS2_API_MODEL)')}
          </label>
          <input
            type="text"
            value={form.unifiedModel}
            onChange={(e) => updateForm({ unifiedModel: e.target.value })}
            placeholder={tx('例如: gemini-2.5-pro 或 gpt-5.4', 'e.g. gemini-2.5-pro or gpt-5.4')}
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white font-mono focus:outline-none focus:border-blue-500"
          />
          <div className="flex flex-wrap gap-1.5 mt-2">
            {['gemini-2.5-pro', 'gpt-5.4', 'gpt-4o', 'deepseek-chat'].map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => updateForm({ unifiedModel: m })}
                className="px-2 py-0.5 text-[10px] font-mono rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-blue-500/10 hover:text-blue-500 border border-slate-200 dark:border-slate-700 cursor-pointer"
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
            {tx('协议覆盖 (SEC_AGENT_HARNESS2_API_PROTOCOL · 可选)', 'Protocol Override (SEC_AGENT_HARNESS2_API_PROTOCOL)')}
          </label>
          <select
            value={form.unifiedProtocol}
            onChange={(e) => updateForm({ unifiedProtocol: e.target.value })}
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">{tx('自动按基座适配 (默认推荐)', 'Auto-adapt per substrate (Recommended)')}</option>
            <option value="openai-chat">openai-chat (OpenAI Chat Completions)</option>
            <option value="openai-responses">openai-responses (OpenAI Responses)</option>
            <option value="anthropic">anthropic (Anthropic Messages)</option>
          </select>
          <p className="text-[10px] text-slate-400 mt-1.5 leading-relaxed">
            {tx(
              '留空时：OpenCode 与 Pi 默认走 openai-chat 协议。',
              'When blank: OpenCode and Pi default to openai-chat protocol.'
            )}
          </p>
        </div>
      </div>

      {/* Live Substrate Resolution Summary Table */}
      <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
            <Link2 className="w-3.5 h-3.5 text-blue-500" />
            <span>
              {tx('双基座实时协议解析预览 (api.describe)', 'Live Substrate Endpoint Resolution (api.describe)')}
            </span>
          </span>
        </div>
        <div className="space-y-1.5 text-[11px] font-mono">
          {executorsData?.executors
            .filter((e) => e.id !== 'vertex')
            .map((e) => (
              <div
                key={e.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800"
              >
                <div className="flex items-center gap-2 font-sans font-semibold text-slate-700 dark:text-slate-300">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      e.status === 'ready' ? 'bg-emerald-500' : 'bg-amber-500'
                    }`}
                  />
                  <span>{e.name}</span>
                  {e.using_unified && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400">
                      {tx('统一API', 'Unified')}
                    </span>
                  )}
                </div>
                <span className="text-slate-500 dark:text-slate-400 truncate max-w-md">
                  {e.resolved_endpoint || tx('(未配置端点)', '(Endpoint not configured)')}
                </span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};
