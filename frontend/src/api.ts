import { dicts } from './i18n/en';
import {
  BenchmarkReport,
  ComponentTemplate,
  DiffResult,
  EndpointProbeResult,
  FetchModelsResult,
  ExecutorStatusResponse,
  HarnessComponent,
  LibraryEntry,
  PreflightStatus,
  RunItem,
  SystemStatus,
  TaskDetail,
  TaskItem,
} from './types';

const BASE = '/api';

/** Module-level translator: reads persisted lang (set by LangProvider). */
function t(key: keyof typeof dicts.zh): string {
  try {
    const lang = (localStorage.getItem('sec_agent_harness2_lang') === 'en' ? 'en' : 'zh') as 'zh' | 'en';
    return dicts[lang][key] ?? dicts.zh[key] ?? key;
  } catch { return dicts.zh[key] ?? key; }
}

export async function fetchStatus(): Promise<SystemStatus> {
  const res = await fetch(`${BASE}/status`);
  if (!res.ok) throw new Error(t('api.status'));
  return res.json();
}

export async function fetchPreflight(): Promise<PreflightStatus> {
  const res = await fetch(`${BASE}/preflight`);
  if (!res.ok) throw new Error(t('api.preflight'));
  return res.json();
}

export async function fetchLogs(limit: number = 300): Promise<string[]> {
  const res = await fetch(`${BASE}/logs?limit=${limit}`);
  if (!res.ok) throw new Error(t('api.logs'));
  const data = await res.json();
  return data.logs || [];
}

export async function fetchRuns(): Promise<RunItem[]> {
  const res = await fetch(`${BASE}/runs`);
  if (!res.ok) throw new Error(t('api.runs'));
  const data = await res.json();
  return data.runs || [];
}

export async function fetchTasks(runId: string): Promise<TaskItem[]> {
  const res = await fetch(`${BASE}/runs/${encodeURIComponent(runId)}/tasks`);
  if (!res.ok) throw new Error(`Failed to fetch tasks for run ${runId}`);
  const data = await res.json();
  return data.tasks || [];
}

export async function fetchTaskDetail(
  runId: string,
  taskId: string
): Promise<TaskDetail> {
  const res = await fetch(
    `${BASE}/runs/${encodeURIComponent(runId)}/tasks/${encodeURIComponent(
      taskId
    )}`
  );
  if (!res.ok) throw new Error(`Failed to fetch detail for task ${taskId}`);
  return res.json();
}

export async function fetchTaskHarness(
  runId: string,
  taskId: string,
  label: string
): Promise<Record<string, any>> {
  const res = await fetch(
    `${BASE}/runs/${encodeURIComponent(runId)}/tasks/${encodeURIComponent(
      taskId
    )}/harnesses/${encodeURIComponent(label)}`
  );
  if (!res.ok) throw new Error(`Failed to fetch harness ${label}`);
  return res.json();
}

export async function fetchDiff(
  runId: string,
  taskId: string,
  base: string,
  compare: string
): Promise<DiffResult> {
  const res = await fetch(
    `${BASE}/runs/${encodeURIComponent(runId)}/tasks/${encodeURIComponent(
      taskId
    )}/diff?base=${encodeURIComponent(base)}&compare=${encodeURIComponent(
      compare
    )}`
  );
  if (!res.ok) throw new Error(t('api.diff'));
  return res.json();
}

export async function fetchLibrary(runId: string): Promise<LibraryEntry[]> {
  const res = await fetch(`${BASE}/runs/${encodeURIComponent(runId)}/library`);
  if (!res.ok) throw new Error(t('api.library'));
  const data = await res.json();
  return data.entries || [];
}

export async function fetchBenchmark(runId: string): Promise<BenchmarkReport> {
  const res = await fetch(
    `${BASE}/runs/${encodeURIComponent(runId)}/benchmark`
  );
  if (!res.ok) throw new Error(t('api.benchmark'));
  return res.json();
}

export async function launchDemo(payload: {
  output?: string;
  k?: number;
  mode?: string;
}): Promise<any> {
  const res = await fetch(`${BASE}/execute/demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.launch_demo'));
  }
  return res.json();
}

export async function launchSweep(payload: {
  bench: string;
  subset?: string;
  substrate: string;
  k: number;
  modes: string;
  split?: string;
  workers?: number;
  max_tasks?: number | null;
  only_domains?: string | null;
  seed?: number | null;
  dry_run?: boolean;
  model?: string;
  effort?: string;
}): Promise<any> {
  const res = await fetch(`${BASE}/execute/sweep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.launch_sweep'));
  }
  return res.json();
}

export async function launchJudge(payload: {
  run_id?: string;
  bench?: string;
  subset?: string;
  substrate?: string;
  k?: number;
  modes?: string;
  seed?: number | null;
  bases?: boolean;
}): Promise<any> {
  const res = await fetch(`${BASE}/execute/judge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to launch judge' }));
    throw new Error(err.detail || '启动评测判分失败');
  }
  return res.json();
}

export async function stopExecution(): Promise<any> {
  const res = await fetch(`${BASE}/execute/stop`, { method: 'POST' });
  if (!res.ok) throw new Error(t('api.stop'));
  return res.json();
}

// ----------------------------------------------------
// Harness Component Studio API
// ----------------------------------------------------
export async function fetchComponents(): Promise<HarnessComponent[]> {
  const res = await fetch(`${BASE}/components`);
  if (!res.ok) throw new Error(t('api.components'));
  const data = await res.json();
  return data.components || [];
}

export async function fetchComponentTemplates(): Promise<ComponentTemplate[]> {
  const res = await fetch(`${BASE}/components/templates`);
  if (!res.ok) throw new Error(t('api.templates'));
  const data = await res.json();
  return data.templates || [];
}

export async function saveComponent(
  comp: Partial<HarnessComponent>
): Promise<HarnessComponent> {
  const res = await fetch(`${BASE}/components`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(comp),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.save_component'));
  }
  const data = await res.json();
  return data.component;
}

export async function deleteComponent(compId: string): Promise<void> {
  const res = await fetch(`${BASE}/components/${encodeURIComponent(compId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(t('api.delete_component'));
}

export async function applyComponent(payload: {
  run_id: string;
  task_id: string;
  label: string;
  component: Partial<HarnessComponent>;
}): Promise<any> {
  const res = await fetch(`${BASE}/components/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.apply_component'));
  }
  return res.json();
}

// ----------------------------------------------------
// Executor & Model Engine API
// ----------------------------------------------------
export async function fetchExecutors(): Promise<ExecutorStatusResponse> {
  const res = await fetch(`${BASE}/executors`);
  if (!res.ok) throw new Error(t('api.executors'));
  return res.json();
}

export async function saveExecutorConfig(payload: {
  executor_id: string;
  base_url?: string;
  api_key?: string;
  model?: string;
  protocol?: string;
  effort?: string;
  container_url?: string;
  improver_model?: string;
  judge_model?: string;
  judge_base_url?: string;
  judge_api_key?: string;
  vertex_project?: string;
  vertex_location?: string;
  persist_dotenv?: boolean;
}): Promise<ExecutorStatusResponse> {
  const res = await fetch(`${BASE}/executors/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.update_executor'));
  }
  const data = await res.json();
  return data.executors;
}

export async function testExecutorEndpoint(payload: {
  target: string;
  base_url?: string;
  api_key?: string;
  protocol?: string;
  model?: string;
}): Promise<EndpointProbeResult> {
  const res = await fetch(`${BASE}/executors/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || 'Endpoint test failed');
  }
  return res.json();
}

export async function fetchAvailableModels(payload: {
  base_url?: string;
  api_key?: string;
  protocol?: string;
}): Promise<FetchModelsResult> {
  const res = await fetch(`${BASE}/executors/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || t('api.fetch_models'));
  }
  return res.json();
}

export async function startResponsesBridge(payload: {
  upstream?: string;
  api_key?: string;
  host?: string;
  port?: number;
}): Promise<{ status: string; bridge: any; executors: ExecutorStatusResponse }> {
  const res = await fetch(`${BASE}/executors/bridge/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || 'Failed to start Responses Bridge');
  }
  return res.json();
}

export async function stopResponsesBridge(): Promise<{
  status: string;
  executors: ExecutorStatusResponse;
}> {
  const res = await fetch(`${BASE}/executors/bridge/stop`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed' }));
    throw new Error(err.detail || 'Failed to stop Responses Bridge');
  }
  return res.json();
}
