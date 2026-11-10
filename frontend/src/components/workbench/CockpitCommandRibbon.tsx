import React from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Cpu,
  BarChart3,
  HelpCircle,
  Activity,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { PreflightStatus, ExecutorStatusResponse, RunItem } from '../../types';
import { useLang } from '../../i18n/LangContext';

interface CockpitCommandRibbonProps {
  preflight: PreflightStatus | null;
  executorStatus: ExecutorStatusResponse | null;
  runs: RunItem[];
  isRunning: boolean;
  onOpenExecutorConfig?: () => void;
  onOpenTerminology?: () => void;
  onNavigateToDashboard?: () => void;
  onNavigateToOverview?: () => void;
}

export const CockpitCommandRibbon: React.FC<CockpitCommandRibbonProps> = ({
  preflight,
  executorStatus,
  runs,
  isRunning,
  onOpenExecutorConfig,
  onOpenTerminology,
  onNavigateToDashboard,
  onNavigateToOverview,
}) => {
  const { tx } = useLang();

  const totalCompleted = runs.reduce((acc, r) => acc + r.completed_count, 0);
  const totalTasks = runs.reduce((acc, r) => acc + r.task_count, 0);
  const passRate = totalTasks > 0 ? Math.round((totalCompleted / totalTasks) * 100) : 0;

  const isPreflightHealthy = Boolean(
    preflight?.has_credentials && preflight?.docker?.available
  );

  const activeExecutorLabel =
    executorStatus?.active_executor === 'pi'
      ? 'Pi Coding Agent (pi)'
      : 'OpenCode (oc)';

  const activeEffort =
    executorStatus?.executors.find(
      (e) => e.id === 'pi'
    )?.effort || 'high';

  return (
    <div className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 rounded-2xl px-4 py-2.5 shadow-sm transition-all flex flex-wrap items-center justify-between gap-3">
      {/* 1. Left: Brand & Concept */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <Activity className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/70 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                COCKPIT
              </span>
              <h2 className="text-sm font-black text-slate-900 dark:text-white tracking-tight">
                {tx('任务作战指挥舱', 'Mission Combat Cockpit')}
              </h2>
              {isRunning && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:block">
              {tx('双轨 12 步流程直驱 · 实时流光与嵌入式监控', 'Metro 12-Step Pipeline · Reactive Telemetry Hub')}
            </p>
          </div>
        </div>

        {onOpenTerminology && (
          <button
            type="button"
            onClick={onOpenTerminology}
            className="hidden md:flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
            title={tx('查看 SecAgentHarness² 架构概念百科', 'Open Architecture Guide')}
          >
            <HelpCircle className="w-3.5 h-3.5 text-blue-500" />
            <span>{tx('概念百科', 'Concepts')}</span>
          </button>
        )}
      </div>

      {/* 2. Middle: Preflight Status & Executor Pill */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Preflight Pill */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-medium ${
            isPreflightHealthy
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
              : 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
          }`}
          title={preflight ? `${preflight.credentials.message} | ${preflight.docker.message}` : tx('检测环境中...', 'Checking preflight...')}
        >
          {isPreflightHealthy ? (
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          ) : (
            <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
          )}
          <span>
            {isPreflightHealthy
              ? tx('环境探针就绪 (Docker+Key)', 'Preflight: OK')
              : tx('离线 Demo 就绪 (免Key)', 'Preflight: Demo Mode')}
          </span>
        </div>

        {/* Executor Config Pill */}
        <button
          type="button"
          onClick={onOpenExecutorConfig}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-blue-500/30 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 text-[11px] font-medium hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors cursor-pointer"
          title={tx('点击配置 Unified API / 执行器', 'Click to configure Unified API and Substrates')}
        >
          <Cpu className="w-3.5 h-3.5 text-blue-500" />
          <span className="font-semibold">{activeExecutorLabel}</span>
          {activeExecutorLabel.includes('Pi') && (
            <span className="text-[10px] px-1 rounded bg-pink-200 dark:bg-pink-900/60 font-bold uppercase text-pink-800 dark:text-pink-200">
              {activeEffort}
            </span>
          )}
        </button>
      </div>

      {/* 3. Right: Micro KPIs & Navigation */}
      <div className="flex items-center gap-3">
        {/* KPI Mini Badges */}
        <div className="hidden lg:flex items-center gap-3 border-l border-slate-200 dark:border-slate-800 pl-3">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 block leading-tight">
              {tx('累计任务', 'Total Tasks')}
            </span>
            <span className="text-xs font-bold font-mono text-slate-800 dark:text-slate-200">
              {totalTasks}
            </span>
          </div>

          <div className="text-right">
            <span className="text-[10px] text-slate-400 block leading-tight">
              {tx('演进胜率', 'Pass Rate')}
            </span>
            <span className="text-xs font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {passRate}%
            </span>
          </div>
        </div>

        {/* Quick Navigate Actions */}
        <div className="flex items-center gap-1.5">
          {onNavigateToOverview && (
            <button
              type="button"
              onClick={onNavigateToOverview}
              className="px-2.5 py-1 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center gap-1"
              title={tx('切换到全景大屏模式', 'Switch to Overview Showcase')}
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              <span className="hidden sm:inline">{tx('全景大屏', 'Showcase')}</span>
            </button>
          )}

          {onNavigateToDashboard && (
            <button
              type="button"
              onClick={onNavigateToDashboard}
              className="px-2.5 py-1 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center gap-1"
              title={tx('前往数据评测大盘', 'View Runs & Benchmark Dashboard')}
            >
              <BarChart3 className="w-3.5 h-3.5 text-blue-500" />
              <span className="hidden sm:inline">{tx('数据大盘', 'Dashboard')}</span>
              <ArrowRight className="w-3 h-3 text-slate-400" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
