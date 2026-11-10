import React, { useEffect, useMemo, useState } from 'react';
import {
  RunItem,
  SystemStatus,
  PreflightStatus,
  ExecutorStatusResponse,
  NavTabType,
  LiveStageStep,
} from '../types';
import {
  fetchPreflight,
  fetchExecutors,
} from '../api';
import { CockpitCommandRibbon } from './workbench/CockpitCommandRibbon';
import { CockpitLeftHUD } from './workbench/CockpitLeftHUD';
import { CockpitRightPipeline } from './workbench/CockpitRightPipeline';

interface WorkbenchViewProps {
  runs: RunItem[];
  selectedRunId: string;
  systemStatus: SystemStatus | null;
  logs: string[];
  executorRefreshVersion?: number;
  onSelectRun: (runId: string, targetTab?: NavTabType) => void;
  onNavigateToDashboard?: (runId?: string) => void;
  onOpenConsole: () => void;
  onNavigateToStudio?: () => void;
  onOpenExecutorConfig?: () => void;
  onOpenTerminology?: () => void;
  liveStep?: LiveStageStep | null;
  onNavigateToOverview?: () => void;
}

export const WorkbenchView: React.FC<WorkbenchViewProps> = ({
  runs,
  selectedRunId,
  systemStatus,
  logs,
  liveStep = null,
  executorRefreshVersion = 0,
  onSelectRun,
  onNavigateToDashboard,
  onNavigateToOverview,
  onOpenConsole,
  onNavigateToStudio,
  onOpenExecutorConfig,
  onOpenTerminology,
}) => {
  const [preflight, setPreflight] = useState<PreflightStatus | null>(null);
  const [executorStatus, setExecutorStatus] = useState<ExecutorStatusResponse | null>(null);

  // Dynamic Pipeline States
  const [pipelineMode, setPipelineMode] = useState<'parallel' | 'sequential'>('parallel');
  const [activeSubstrate, setActiveSubstrate] = useState<string>('OpenCode');

  // Local cleared log filter if user clears terminal in session
  const [clearedBeforeCount, setClearedBeforeCount] = useState<number>(0);

  // Status mapping
  const execStatus = systemStatus?.status.status || 'idle';
  const isRunning = execStatus === 'running';
  const [isCompletedState, setIsCompletedState] = useState(false);

  useEffect(() => {
    if (execStatus === 'completed') {
      setIsCompletedState(true);
    } else if (execStatus === 'running') {
      setIsCompletedState(false);
    }
  }, [execStatus]);

  const isCompleted = isCompletedState || execStatus === 'completed';
  const isFailed = execStatus === 'failed' || execStatus === 'terminated';

  // Fetch preflight & executor status on mount and when executor config changes
  useEffect(() => {
    fetchPreflight()
      .then((data) => setPreflight(data))
      .catch((err) => console.error('Failed to fetch preflight:', err));
    fetchExecutors()
      .then((data) => {
        setExecutorStatus(data);
        if (data.active_executor) {
          const exec = data.executors.find((e) => e.id === data.active_executor);
          const effortTag = exec?.effort ? ` (${exec.effort})` : '';
          setActiveSubstrate(`${exec?.name || data.active_executor}${effortTag}`);
        }
      })
      .catch((err) => console.error('Failed to fetch executors:', err));
  }, [executorRefreshVersion]);

  // Handle parameter synchronization from left HUD to right Pipeline
  const handleParameterChange = (params: {
    mode: 'parallel' | 'sequential';
    substrate: string;
    bench?: string;
  }) => {
    setPipelineMode(params.mode);
    setActiveSubstrate(params.substrate);
  };

  const handleGoToDashboard = () => {
    if (onNavigateToDashboard) {
      onNavigateToDashboard(selectedRunId);
    } else {
      onSelectRun(selectedRunId, 'dashboard');
    }
  };

  const visibleLogs = useMemo(() => {
    if (clearedBeforeCount > 0 && logs.length >= clearedBeforeCount) {
      return logs.slice(clearedBeforeCount);
    }
    return logs;
  }, [logs, clearedBeforeCount]);

  return (
    <div className="space-y-4">
      {/* 1. Top Command Ribbon (Compact Status, Preflight & Micro-KPIs) */}
      <CockpitCommandRibbon
        preflight={preflight}
        executorStatus={executorStatus}
        runs={runs}
        isRunning={isRunning}
        onOpenExecutorConfig={onOpenExecutorConfig}
        onOpenTerminology={onOpenTerminology}
        onNavigateToDashboard={handleGoToDashboard}
        onNavigateToOverview={onNavigateToOverview}
      />

      {/* 2. Symmetric Combat Cockpit (左右分栏作战指挥舱: 42% Left : 58% Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch min-h-[580px]">
        {/* Left Column: Mission Dispatcher & Multi-State HUD (~42% on LG) */}
        <div className="lg:col-span-5 flex flex-col">
          <CockpitLeftHUD
            systemStatus={systemStatus}
            isRunning={isRunning}
            isCompleted={isCompleted}
            isFailed={isFailed}
            executorStatus={executorStatus}
            liveStep={liveStep}
            runs={runs}
            selectedRunId={selectedRunId}
            onParameterChange={handleParameterChange}
            onOpenConsole={onOpenConsole}
            onNavigateToDashboard={handleGoToDashboard}
            onResetToIdle={() => setIsCompletedState(false)}
          />
        </div>

        {/* Right Column: 4-Phase Telemetry, Saved Runs & Embedded Live Terminal (~58% on LG) */}
        <div className="lg:col-span-7 flex flex-col">
          <CockpitRightPipeline
            logs={visibleLogs}
            isRunning={isRunning}
            isCompleted={isCompleted}
            liveStep={liveStep}
            mode={pipelineMode}
            onToggleMode={(m) => setPipelineMode(m)}
            activeSubstrate={activeSubstrate}
            onClearLogs={() => setClearedBeforeCount(logs.length)}
            runs={runs}
            selectedRunId={selectedRunId}
            onSelectRun={onSelectRun}
            onNavigateToTab={(tab) => {
              if (tab === 'studio' && onNavigateToStudio) onNavigateToStudio();
              else if (tab === 'dashboard') handleGoToDashboard();
            }}
          />
        </div>
      </div>
    </div>
  );
};
