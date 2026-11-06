import React, { useState, useEffect } from 'react';
import {
  Play,
  Zap,
  RotateCcw,
  Square,
  ShieldAlert,
  Clock,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Terminal,
  Scale,
} from 'lucide-react';
import { ExecutorStatusResponse, SystemStatus, LiveStageStep, RunItem } from '../../types';
import { launchDemo, launchSweep, launchJudge, stopExecution } from '../../api';
import { useLang } from '../../i18n/LangContext';
import { useToast } from '../ui/ToastContext';

interface CockpitLeftHUDProps {
  systemStatus: SystemStatus | null;
  isRunning: boolean;
  isCompleted: boolean;
  isFailed: boolean;
  executorStatus: ExecutorStatusResponse | null;
  liveStep: LiveStageStep | null;
  runs?: RunItem[];
  selectedRunId?: string;
  onParameterChange?: (params: {
    mode: 'parallel' | 'sequential';
    substrate: string;
    bench?: string;
  }) => void;
  onOpenConsole: () => void;
  onNavigateToDashboard?: () => void;
  onResetToIdle?: () => void;
}

type PresetType = 'demo_30s' | 'jb_smoke' | 'wb_office' | 'sweep_full';

export const CockpitLeftHUD: React.FC<CockpitLeftHUDProps> = ({
  systemStatus,
  isRunning,
  isCompleted,
  isFailed,
  executorStatus,
  liveStep,
  runs = [],
  selectedRunId = '',
  onParameterChange,
  onOpenConsole,
  onNavigateToDashboard,
  onResetToIdle,
}) => {
  const { tx } = useLang();
  const { showToast } = useToast();

  // Preset Selection
  const [activePreset, setActivePreset] = useState<PresetType>('demo_30s');
  const [activeTab, setActiveTab] = useState<'presets' | 'custom'>('presets');

  // Form State
  const [launcherType, setLauncherType] = useState<'demo' | 'sweep' | 'judge'>('demo');
  const [demoK, setDemoK] = useState(2);
  const [demoMode, setDemoMode] = useState<'both' | 'aggregate' | 'sequential'>('both');

  const [sweepBench, setSweepBench] = useState<'jb' | 'wb' | 'lab'>('jb');
  const [sweepSubset, setSweepSubset] = useState<'office' | 'web' | 'code'>('office');
  const [sweepSubstrate, setSweepSubstrate] = useState('claude');
  const [sweepClaudeEffort, setSweepClaudeEffort] = useState<'low' | 'medium' | 'high'>('high');
  const [sweepK, setSweepK] = useState(1);
  const [sweepModes, setSweepModes] = useState<'both' | 'aggregate' | 'sequential'>('both');
  const [sweepWorkers, setSweepWorkers] = useState(1);
  const [sweepSplit, setSweepSplit] = useState<'all' | 'train' | 'test'>('all');
  const [sweepMaxTasks, setSweepMaxTasks] = useState<string>('');
  const [sweepOnlyDomains, setSweepOnlyDomains] = useState<string>('');
  const [sweepDryRun, setSweepDryRun] = useState(false);

  // Judge Specific State
  const [judgeRunId, setJudgeRunId] = useState<string>(selectedRunId || '');
  const [judgeBases, setJudgeBases] = useState<boolean>(false);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showRunningParams, setShowRunningParams] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Running Timer Stopwatch
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (selectedRunId) {
      setJudgeRunId(selectedRunId);
    }
  }, [selectedRunId]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isRunning) {
      timer = setInterval(() => {
        setElapsedSeconds((s) => s + 1);
      }, 1000);
    } else {
      setElapsedSeconds(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isRunning]);

  // Sync default substrate from executorStatus
  useEffect(() => {
    if (!executorStatus) return;
    if (executorStatus.active_executor) {
      setSweepSubstrate(executorStatus.active_executor);
    }
    const activeExec = executorStatus.executors.find(
      (e) => e.id === (executorStatus.active_executor === 'pi' ? 'pi' : 'claude')
    );
    if (activeExec?.effort && ['low', 'medium', 'high'].includes(activeExec.effort)) {
      setSweepClaudeEffort(activeExec.effort as 'low' | 'medium' | 'high');
    }
  }, [executorStatus]);

  // Notify parent whenever mode or substrate changes
  useEffect(() => {
    if (onParameterChange) {
      const mode =
        (launcherType === 'demo' ? demoMode : sweepModes) === 'sequential'
          ? 'sequential'
          : 'parallel';
      const substrate = launcherType === 'demo' ? 'mock_demo' : sweepSubstrate;
      const subLabel =
        substrate === 'claude'
          ? `Claude (${sweepClaudeEffort})`
          : substrate === 'pi'
          ? `Pi (${sweepClaudeEffort})`
          : substrate;
      onParameterChange({
        mode,
        substrate: subLabel,
        bench: launcherType === 'sweep' ? sweepBench : 'demo',
      });
    }
  }, [
    launcherType,
    demoMode,
    sweepModes,
    sweepSubstrate,
    sweepClaudeEffort,
    sweepBench,
    onParameterChange,
  ]);

  // Select Preset Handler
  const handleSelectPreset = (preset: PresetType) => {
    setActivePreset(preset);
    setErrorMsg('');
    if (preset === 'demo_30s') {
      setLauncherType('demo');
      setDemoK(2);
      setDemoMode('both');
    } else if (preset === 'jb_smoke') {
      setLauncherType('sweep');
      setSweepBench('jb');
      setSweepSubstrate(executorStatus?.active_executor || 'claude');
      setSweepClaudeEffort('high');
      setSweepK(1);
      setSweepModes('both');
      setSweepWorkers(1);
      setSweepSplit('all');
      setSweepMaxTasks('1');
      setSweepOnlyDomains('');
    } else if (preset === 'wb_office') {
      setLauncherType('sweep');
      setSweepBench('wb');
      setSweepSubset('office');
      setSweepSubstrate(executorStatus?.active_executor || 'claude');
      setSweepK(1);
      setSweepModes('both');
      setSweepWorkers(1);
      setSweepSplit('all');
      setSweepMaxTasks('1');
      setSweepOnlyDomains('');
    } else if (preset === 'sweep_full') {
      setLauncherType('sweep');
      setSweepBench('lab');
      setSweepSubstrate(executorStatus?.active_executor || 'claude');
      setSweepK(2);
      setSweepModes('both');
      setSweepWorkers(2);
      setSweepSplit('all');
      setSweepMaxTasks('');
      setSweepOnlyDomains('');
    }
  };

  // Launch Task Handlers
  const handleLaunch = async () => {
    setErrorMsg('');
    setLaunching(true);
    try {
      if (launcherType === 'demo') {
        await launchDemo({
          output: 'runs/demo',
          k: demoK,
          mode: demoMode,
        });
        showToast(tx('离线 Demo 演进任务已启动', 'Offline Demo pipeline launched'), 'info');
      } else if (launcherType === 'judge') {
        await launchJudge({
          run_id: judgeRunId || undefined,
          bench: sweepBench,
          subset: sweepBench === 'wb' ? sweepSubset : undefined,
          substrate: sweepSubstrate,
          k: sweepK,
          modes: sweepModes,
          bases: judgeBases,
        });
        showToast(
          tx('评测判分任务 (Judge) 已启动，完成后将更新大盘得分', 'Judge scoring job launched'),
          'info'
        );
      } else {
        const parsedMax = sweepMaxTasks.trim() ? parseInt(sweepMaxTasks.trim(), 10) : null;
        await launchSweep({
          bench: sweepBench,
          subset: sweepBench === 'wb' ? sweepSubset : undefined,
          substrate: sweepSubstrate,
          k: sweepK,
          modes: sweepModes,
          split: sweepSplit,
          workers: sweepWorkers,
          max_tasks: parsedMax && parsedMax > 0 ? parsedMax : null,
          only_domains: sweepOnlyDomains.trim() || null,
          dry_run: sweepDryRun,
          effort: (sweepSubstrate === 'claude' || sweepSubstrate === 'pi') ? sweepClaudeEffort : undefined,
        });
        showToast(tx('基准评测演进任务已启动', 'Benchmark Sweep pipeline launched'), 'info');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      showToast(tx(`启动失败: ${msg}`, `Launch failed: ${msg}`), 'error');
    } finally {
      setLaunching(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopExecution();
      showToast(tx('已发送急停指令', 'Emergency stop command dispatched'), 'info');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      showToast(tx(`停止失败: ${msg}`, `Failed to stop: ${msg}`), 'error');
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const benchmarkRuns = runs.filter((r) => r.type !== 'demo' && r.bench !== 'demo');

  // ==========================================
  // Render State 1: RUNNING (Active Job HUD)
  // ==========================================
  if (isRunning) {
    const activeStep = liveStep?.stepIndex ?? 0;
    const progressPercent = Math.min(100, Math.round(((activeStep + 1) / 12) * 100));

    return (
      <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-blue-500/30 rounded-2xl p-5 shadow-lg flex flex-col justify-between h-full gap-4 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-36 h-36 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
              <h3 className="text-sm font-black text-slate-900 dark:text-white uppercase tracking-wider">
                {tx('任务执行中枢 (Live HUD)', 'Mission Active HUD')}
              </h3>
            </div>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
              JOB ACTIVE
            </span>
          </div>

          <div className="bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/80 rounded-xl p-4 flex items-center justify-between gap-4">
            <div>
              <span className="text-[10px] text-slate-400 font-mono block">
                {tx('当前已执行耗时', 'Elapsed Time')}
              </span>
              <div className="text-2xl font-black font-mono text-blue-600 dark:text-blue-400 flex items-center gap-1.5 mt-0.5">
                <Clock className="w-5 h-5 text-blue-500" />
                <span>{formatTimer(elapsedSeconds)}</span>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] text-slate-400 font-mono block">
                {tx('生命周期进度', 'Lifecycle Progress')}
              </span>
              <div className="text-base font-black font-mono text-slate-800 dark:text-slate-100 mt-0.5">
                {activeStep + 1} / 12
                <span className="text-xs text-blue-500 font-bold ml-1">({progressPercent}%)</span>
              </div>
              {systemStatus?.status?.job?.job_id && (
                <span className="text-[9px] text-slate-400 font-mono block truncate max-w-[130px]">
                  {systemStatus.status.job.job_id}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-1">
            <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-600 to-indigo-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-400 font-mono">
              <span>S1 ColdStart</span>
              <span>S3 Materialize</span>
              <span>S5 Aggregation</span>
            </div>
          </div>

          <div className="bg-blue-50/60 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-900/40 rounded-xl p-3">
            <span className="text-[10px] font-bold text-blue-700 dark:text-blue-300 font-mono block uppercase">
              {tx('当前阶段与探针活动', 'Active Phase & Rollout')}
            </span>
            <p className="text-xs font-bold text-slate-900 dark:text-slate-100 mt-1">
              {liveStep?.title || tx('正在初始化演进套件与沙箱...', 'Initializing sandbox harness...')}
            </p>
            {liveStep?.line && (
              <p className="text-[11px] font-mono text-slate-600 dark:text-slate-300 mt-1 truncate">
                {liveStep.line}
              </p>
            )}
          </div>

          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowRunningParams(!showRunningParams)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 flex items-center justify-between text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-colors cursor-pointer"
            >
              <span className="font-semibold">{tx('查看本次运行参数快照', 'View Launch Spec')}</span>
              {showRunningParams ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showRunningParams && (
              <div className="p-3 bg-white dark:bg-slate-950 font-mono text-[10px] text-slate-600 dark:text-slate-400 space-y-1">
                <div>模式: {launcherType.toUpperCase()}</div>
                <div>基准: {launcherType === 'demo' ? 'Offline Demo' : sweepBench.toUpperCase()}</div>
                <div>Substrate: {launcherType === 'demo' ? 'Mock Demo' : sweepSubstrate}</div>
                <div>K 轮次: {launcherType === 'demo' ? demoK : sweepK}</div>
                <div>路由策略: {launcherType === 'demo' ? demoMode : sweepModes}</div>
              </div>
            )}
          </div>
        </div>

        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2">
          <button
            type="button"
            onClick={handleStop}
            className="flex-1 py-2.5 px-3 rounded-xl bg-rose-500 hover:bg-rose-600 text-white font-bold text-xs shadow-md shadow-rose-500/20 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            <span>{tx('终止当前作业', 'Stop Active Job')}</span>
          </button>
          <button
            type="button"
            onClick={onOpenConsole}
            className="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
            title={tx('打开独立控制台弹窗', 'Open Popout Console')}
          >
            <Terminal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // ==========================================
  // Render State 2: COMPLETED / FAILED (Scorecard)
  // ==========================================
  if (isCompleted || isFailed) {
    return (
      <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between h-full gap-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isCompleted ? (
                <div className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              ) : (
                <div className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-600 dark:text-rose-400 flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5" />
                </div>
              )}
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {isCompleted
                    ? tx('演进流水线执行完成', 'Evolution Completed')
                    : tx('任务执行中断或未达标', 'Execution Failed')}
                </h3>
                <span className="text-[11px] text-slate-500 dark:text-slate-400">
                  {isCompleted
                    ? tx('已提炼出候选套件组件与评测产物', 'Harness components & deliverables verified')
                    : tx('请在右侧终端检查报错堆栈', 'Check terminal logs for details')}
                </span>
              </div>
            </div>
          </div>

          {isCompleted && (
            <div className="bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 rounded-xl p-3.5 space-y-2">
              <span className="text-[10px] font-bold text-emerald-800 dark:text-emerald-300 font-mono block uppercase">
                {tx('本次提炼产出物', 'Generated Components')}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {['c1 提示词', 'c2 护栏', 'c3 长期记忆', 'c6 领域技能', 'c7 辅助脚本'].map((cmp) => (
                  <span
                    key={cmp}
                    className="px-2 py-0.5 rounded-md bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-800 text-[10px] font-mono text-emerald-700 dark:text-emerald-300 font-medium"
                  >
                    {cmp}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-2 pt-3 border-t border-slate-100 dark:border-slate-800">
          {onNavigateToDashboard && (
            <button
              type="button"
              onClick={onNavigateToDashboard}
              className="w-full py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-md shadow-blue-500/20 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>
                {tx('前往「评测与演进洞察」审阅 DAG 与 Diff ➔', 'Inspect DAG & Diff in Insights ➔')}
              </span>
            </button>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleLaunch}
              className="flex-1 py-2 px-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold text-xs border border-slate-200 dark:border-slate-700 transition-colors flex items-center justify-center gap-1 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{tx('同参再跑一次', 'Re-run')}</span>
            </button>

            {onResetToIdle && (
              <button
                type="button"
                onClick={onResetToIdle}
                className="py-2 px-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold text-xs border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
                title={tx('配置新任务', 'Configure New Job')}
              >
                <span>{tx('配置新任务', 'New Task')}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // Render State 3: IDLE (Preset Cards & Launcher)
  // ==========================================
  return (
    <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between h-full gap-4">
      <div className="space-y-3.5">
        {/* Launcher Header & Tab Switcher */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-500" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              {tx('任务调度与参数配置', 'Mission Dispatcher')}
            </h3>
          </div>

          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 text-[10px] font-medium">
            <button
              type="button"
              onClick={() => setActiveTab('presets')}
              className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                activeTab === 'presets'
                  ? 'bg-blue-600 text-white font-bold shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              {tx('场景预设', 'Presets')}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('custom')}
              className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                activeTab === 'custom'
                  ? 'bg-blue-600 text-white font-bold shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              {tx('全量调参 / 判分', 'Custom / Judge')}
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Tab 1: Presets View */}
        {activeTab === 'presets' && (
          <div className="space-y-2">
            {/* Preset 1: 30s Offline Demo */}
            <div
              onClick={() => handleSelectPreset('demo_30s')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                activePreset === 'demo_30s'
                  ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 shadow-sm ring-1 ring-blue-500/30'
                  : 'bg-slate-50/70 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">⚡</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    {tx('30 秒本地快速体验 (离线 Demo)', '30s Offline Quick Demo')}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                  {tx('免 API Key · K=2', 'No API · K=2')}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                {tx(
                  '运行 2 轮离线演进探针，验证基线对比、INV/DOM 双轴提议与双轨融合全闭环。',
                  'Runs 2-round offline probes to verify baseline, INV/DOM levers, and aggregation.'
                )}
              </p>
            </div>

            {/* Preset 2: JobBench Smoke Adaptation */}
            <div
              onClick={() => handleSelectPreset('jb_smoke')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                activePreset === 'jb_smoke'
                  ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 shadow-sm ring-1 ring-blue-500/30'
                  : 'bg-slate-50/70 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">🛡️</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    {tx('JobBench 单题冒烟快测 (JB · K=1)', 'JobBench 1-Task Smoke (JB)')}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-950/40 px-1.5 py-0.5 rounded border border-orange-200 dark:border-orange-800">
                  JobBench · max_tasks=1
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                {tx(
                  '在真实 JobBench 专业基准上执行单题快速演进验证，检验真实模型与沙箱联通性。',
                  'Quick 1-task smoke adaptation on JobBench with active executor.'
                )}
              </p>
            </div>

            {/* Preset 3: WorkBuddy Container Benchmark */}
            <div
              onClick={() => handleSelectPreset('wb_office')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                activePreset === 'wb_office'
                  ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 shadow-sm ring-1 ring-blue-500/30'
                  : 'bg-slate-50/70 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">🐳</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    {tx('WorkBuddy 容器沙箱演进 (WB · Office)', 'WorkBuddy Container Adaptation')}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-950/40 px-1.5 py-0.5 rounded border border-cyan-200 dark:border-cyan-800">
                  WB (office) · Docker
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                {tx(
                  '启动 Docker 隔离容器沙箱运行 WorkBuddy (office/web/code) 真实环境工具流演进。',
                  'Runs isolated Docker sandbox adaptation on WorkBuddy benchmark.'
                )}
              </p>
            </div>

            {/* Preset 4: LaB Full Multi-Round Sweep */}
            <div
              onClick={() => handleSelectPreset('sweep_full')}
              className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                activePreset === 'sweep_full'
                  ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 shadow-sm ring-1 ring-blue-500/30'
                  : 'bg-slate-50/70 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">🔬</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    {tx('LaB 多轮次全量 Sweep 探索 (K=2)', 'LaB Multi-Round Full Sweep (K=2)')}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40 px-1.5 py-0.5 rounded border border-purple-200 dark:border-purple-800">
                  LaB · Workers=2 · K=2
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                {tx(
                  '多进程并行跑完任务集，进行 K=2 深层候选探索与跨任务经验库沉淀。',
                  'Multi-worker parallel execution for K=2 deep search across task suites.'
                )}
              </p>
            </div>
          </div>
        )}

        {/* Tab 2: Custom Fine-tuning & Judge */}
        {activeTab === 'custom' && (
          <div className="space-y-3">
            {/* Launcher Type Switcher (3 modes: Demo / Sweep / Judge) */}
            <div>
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                {tx('作业类型', 'Job Type')}
              </label>
              <div className="grid grid-cols-3 gap-1.5">
                <button
                  type="button"
                  onClick={() => setLauncherType('demo')}
                  className={`py-1.5 px-2 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                    launcherType === 'demo'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  {tx('⚡ 离线 Demo', '⚡ Offline Demo')}
                </button>
                <button
                  type="button"
                  onClick={() => setLauncherType('sweep')}
                  className={`py-1.5 px-2 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                    launcherType === 'sweep'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  {tx('🚀 基准 Sweep', '🚀 Sweep')}
                </button>
                <button
                  type="button"
                  onClick={() => setLauncherType('judge')}
                  className={`py-1.5 px-2 rounded-lg border text-xs font-semibold transition-all cursor-pointer ${
                    launcherType === 'judge'
                      ? 'bg-purple-600 text-white border-purple-600'
                      : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  {tx('⚖️ 评测判分', '⚖️ Judge')}
                </button>
              </div>
            </div>

            {/* Judge Specific Mode */}
            {launcherType === 'judge' && (
              <div className="space-y-2.5 p-3 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800/50">
                <div>
                  <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 block mb-1">
                    {tx('选择待判分的基准 Run (自动推断参数)', 'Target Benchmark Run')}
                  </label>
                  <select
                    value={judgeRunId}
                    onChange={(e) => setJudgeRunId(e.target.value)}
                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                  >
                    <option value="">
                      {tx('-- 按下方手动指定的 (基准/执行器/K) 判分 --', '-- Use manual Bench/Substrate/K below --')}
                    </option>
                    {benchmarkRuns.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({r.completed_count}/{r.task_count}) {r.has_judged ? '✓已判分' : '·待判分'}
                      </option>
                    ))}
                  </select>
                </div>

                <label className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300 cursor-pointer pt-1">
                  <span>{tx('评判基线套件得分 (--bases 生成 base_judged.json)', 'Score Baseline Executions (--bases)')}</span>
                  <input
                    type="checkbox"
                    checked={judgeBases}
                    onChange={(e) => setJudgeBases(e.target.checked)}
                    className="rounded"
                  />
                </label>
              </div>
            )}

            {/* Sweep & Fallback Judge Controls: Benchmark + Subset + Substrate */}
            {(launcherType === 'sweep' || (launcherType === 'judge' && !judgeRunId)) && (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <div className={sweepBench === 'wb' ? 'col-span-1' : 'col-span-2'}>
                    <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                      {tx('评测基准集 (Benchmark)', 'Benchmark Suite')}
                    </label>
                    <select
                      value={sweepBench}
                      onChange={(e) => setSweepBench(e.target.value as 'jb' | 'wb' | 'lab')}
                      className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white font-semibold"
                    >
                      <option value="jb">JobBench (jb · 职业全栈任务)</option>
                      <option value="wb">WorkBuddy (wb · 容器沙箱基准)</option>
                      <option value="lab">LegalAgentBench (lab · 专业合规)</option>
                    </select>
                  </div>

                  {sweepBench === 'wb' && (
                    <div>
                      <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                        {tx('WB 任务子集 (Subset)', 'WB Subset')}
                      </label>
                      <select
                        value={sweepSubset}
                        onChange={(e) => setSweepSubset(e.target.value as 'office' | 'web' | 'code')}
                        className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                      >
                        <option value="office">office (文档流)</option>
                        <option value="web">web (前端与网页)</option>
                        <option value="code">code (软件工程)</option>
                      </select>
                    </div>
                  )}
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                    {tx('目标执行器 (Substrate)', 'Substrate Executor')}
                  </label>
                  <select
                    value={sweepSubstrate}
                    onChange={(e) => setSweepSubstrate(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white"
                  >
                    <option value="claude">Claude Code (Thinking 思考执行器)</option>
                    <option value="oc">OpenCode (oc 本地执行器)</option>
                    <option value="cx">Codex (cx 镜像执行器)</option>
                    <option value="pi">Pi Coding Agent (pi 极简原生执行器)</option>
                  </select>
                </div>

                {launcherType === 'sweep' && (sweepSubstrate === 'claude' || sweepSubstrate === 'pi') && (
                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                      {sweepSubstrate === 'pi'
                        ? tx('Pi 深度思考等级 (Thinking)', 'Pi Thinking Effort')
                        : tx('Claude 深度思考等级 (Effort)', 'Claude Thinking Effort')}
                    </label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(['low', 'medium', 'high'] as const).map((eff) => (
                        <button
                          key={eff}
                          type="button"
                          onClick={() => setSweepClaudeEffort(eff)}
                          className={`py-1 px-2 rounded-md text-[10px] font-mono font-bold uppercase transition-colors cursor-pointer ${
                            sweepClaudeEffort === eff
                              ? sweepSubstrate === 'pi'
                                ? 'bg-pink-600 text-white'
                                : 'bg-orange-500 text-white'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700'
                          }`}
                        >
                          {eff}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* K Rounds & Mode */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                  {tx('候选预算轮次 (K)', 'Candidate Budget (K)')}
                </label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={launcherType === 'demo' ? demoK : sweepK}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10) || 1;
                    if (launcherType === 'demo') setDemoK(val);
                    else setSweepK(val);
                  }}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 block mb-1">
                  {tx('演进策略 (Modes)', 'Recursion Mode')}
                </label>
                <select
                  value={launcherType === 'demo' ? demoMode : sweepModes}
                  onChange={(e) => {
                    const val = e.target.value as 'both' | 'aggregate' | 'sequential';
                    if (launcherType === 'demo') setDemoMode(val);
                    else setSweepModes(val);
                  }}
                  className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-white"
                >
                  <option value="both">双轨全跑 (agg + seq)</option>
                  <option value="aggregate">仅并行融合 (agg)</option>
                  <option value="sequential">仅串行精炼 (seq)</option>
                </select>
              </div>
            </div>

            {/* Collapsible Advanced Options for Sweep */}
            {launcherType === 'sweep' && (
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-1 text-[11px] text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
                >
                  <span>
                    {tx(
                      '展开任务过滤 (max_tasks / split / domains) 与并发参数',
                      'Task Filtering & Concurrency Flags'
                    )}
                  </span>
                  {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>

                {showAdvanced && (
                  <div className="mt-2 p-2.5 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <span className="text-[10px] text-slate-500 block mb-0.5">并发 Workers</span>
                        <input
                          type="number"
                          min={1}
                          max={8}
                          value={sweepWorkers}
                          onChange={(e) => setSweepWorkers(parseInt(e.target.value, 10) || 1)}
                          className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-2 py-1 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block mb-0.5">每域上限 (max_tasks)</span>
                        <input
                          type="number"
                          min={1}
                          placeholder={tx('不限', 'All')}
                          value={sweepMaxTasks}
                          onChange={(e) => setSweepMaxTasks(e.target.value)}
                          className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-2 py-1 text-xs font-mono"
                        />
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-500 block mb-0.5">数据划分 (split)</span>
                        <select
                          value={sweepSplit}
                          onChange={(e) => setSweepSplit(e.target.value as 'all' | 'train' | 'test')}
                          className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-2 py-1 text-xs font-mono"
                        >
                          <option value="all">all</option>
                          <option value="train">train</option>
                          <option value="test">test</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] text-slate-500 block mb-0.5">
                        {tx('指定领域过滤 (--only-domains，逗号分隔)', 'Only Domains (comma-separated)')}
                      </span>
                      <input
                        type="text"
                        placeholder="e.g. biostatisticians,antitrust-competition"
                        value={sweepOnlyDomains}
                        onChange={(e) => setSweepOnlyDomains(e.target.value)}
                        className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-2 py-1 text-xs font-mono"
                      />
                    </div>

                    <label className="flex items-center justify-between pt-1 cursor-pointer">
                      <span className="text-slate-600 dark:text-slate-400">
                        {tx('Dry-Run (仅验证任务流，不启动沙箱执行)', 'Dry-Run (Preview task stream only)')}
                      </span>
                      <input
                        type="checkbox"
                        checked={sweepDryRun}
                        onChange={(e) => setSweepDryRun(e.target.checked)}
                        className="rounded"
                      />
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Launch Action Button */}
      <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
        <button
          type="button"
          onClick={handleLaunch}
          disabled={launching}
          className={`w-full py-3 px-4 rounded-xl text-white font-bold text-xs shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 ${
            launcherType === 'judge'
              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-500/20'
              : 'bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 shadow-blue-500/20'
          }`}
        >
          {launching ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>{tx('调度下发中...', 'Dispatching job...')}</span>
            </>
          ) : launcherType === 'judge' ? (
            <>
              <Scale className="w-3.5 h-3.5" />
              <span>
                {tx(
                  judgeBases ? '⚖️ 立即启动基线判分 (--bases)' : '⚖️ 立即启动评测判分 (Judge)',
                  'Launch Benchmark Judge'
                )}
              </span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{tx('🚀 立即启动演进流水线', 'Launch Evolution Pipeline')}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
