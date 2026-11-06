export interface RunItem {
  id: string;
  name: string;
  type: 'demo' | 'sweep' | 'adapt' | 'namespace';
  path: string;
  task_count: number;
  completed_count: number;
  failed_count: number;
  execution_count?: number;
  editor_calls?: number;
  updated_at: string;
  domain?: string;
  modes: string[];
  bench?: string | null;
  subset?: string | null;
  substrate?: string | null;
  k?: number;
  seed?: number | null;
  has_judged?: boolean;
}

export interface TaskStageSummary {
  label: string;
  dim: string;
  mode: string;
  usd: number;
  attempts: number;
  notes: string;
  fell_back: boolean;
  kept_base?: boolean;
  cached?: boolean;
  error?: string;
}

export interface TaskSelectionExperience {
  cue?: string;
  lesson?: string;
  evidence?: string;
  confidence?: string;
  edits?: string;
}

export interface TaskSelection {
  task_id?: string;
  mode?: string;
  k?: number;
  chosen_id?: string;
  chosen_label?: string;
  chosen_run_id?: string;
  chosen_is_base?: boolean;
  why?: string;
  has_experience?: boolean;
  experience?: TaskSelectionExperience;
}

export interface TaskItem {
  task_id: string;
  domain: string;
  status: string;
  k: number;
  run_path: string;
  modes: string[];
  base_count: number;
  stages_count: number;
  stages: TaskStageSummary[];
  total_usd: number;
  selections: Record<string, TaskSelection>;
  updated_at: string;
}

export interface DAGNode {
  id: string;
  label: string;
  type: 'base' | 'candidate' | 'composed' | 'sequential';
  dim?: string;
  mode?: string;
  status: 'completed' | 'failed' | 'running' | 'pending';
  fell_back?: boolean;
  kept_base?: boolean;
  notes?: string;
  error?: string;
  usd?: number;
  attempts?: number;
  deliverable?: string;
  has_trajectory?: boolean;
  is_chosen?: boolean;
}

export interface DAGEdge {
  source: string;
  target: string;
  label?: string;
}

export interface TaskDetail {
  task_id: string;
  domain: string;
  status: string;
  k: number;
  summary: Record<string, unknown>;
  available_harnesses: string[];
  stages: Record<string, TaskStageSummary>;
  rollouts: Record<string, Record<string, string>>;
  selections: Record<string, TaskSelection>;
  pipeline_graph: {
    nodes: DAGNode[];
    edges: DAGEdge[];
  };
  reflection: Record<string, unknown>;
}

export interface DiffFile {
  path: string;
  component?: string;
  status: 'added' | 'removed' | 'modified';
  additions: number;
  deletions: number;
  diff_text: string;
  old_content: string;
  new_content: string;
}

export interface ComponentStatus {
  status: 'unchanged' | 'modified' | 'added' | 'removed';
  label: string;
  changes: number;
}

export interface DiffResult {
  task_id: string;
  base_label: string;
  compare_label: string;
  has_changes?: boolean;
  total_files_changed: number;
  total_additions: number;
  total_deletions: number;
  intent_summary?: string[];
  components_summary?: Record<string, ComponentStatus>;
  files: DiffFile[];
}

export interface BenchmarkPrereq {
  available: boolean;
  label: string;
  status: 'ready' | 'not_installed' | 'need_credentials';
  message: string;
}

export interface PreflightStatus {
  status: 'ready' | 'demo_ready' | 'error';
  has_credentials: boolean;
  credentials: {
    project: string;
    solver_model: string;
    judge_model: string;
    message: string;
  };
  docker: {
    available: boolean;
    message: string;
  };
  benchmarks: {
    demo: BenchmarkPrereq;
    jb: BenchmarkPrereq;
    lab: BenchmarkPrereq;
    wb: BenchmarkPrereq;
  };
  tools: {
    pandoc: boolean;
    poppler: boolean;
    node: boolean;
  };
}

export interface LibraryEntry {
  task_id: string;
  domain: string;
  path: string;
  raw_text: string;
  cue: string;
  lesson: string;
  confidence: string;
}

export interface BenchmarkStats {
  count: number;
  graded: number;
  avg_score: number;
  all_pass_rate: number;
  all_pass_count?: number;
}

export interface BenchmarkJudgedRow {
  task_id: string;
  mode?: string;
  label?: string;
  n_passed: number;
  n_criteria: number;
  all_pass?: boolean;
  chosen_is_base?: boolean;
}

export interface BenchmarkReport {
  run_id: string;
  has_judged: boolean;
  has_base_judged: boolean;
  adapted_stats: BenchmarkStats;
  base_stats: BenchmarkStats;
  judged_rows: BenchmarkJudgedRow[];
  base_rows: BenchmarkJudgedRow[];
}

export type NavTabType = 'overview' | 'workbench' | 'dashboard' | 'studio' | 'pipeline' | 'library' | 'benchmark';

export type DashboardSubView = 'diff' | 'benchmark';

export type ComponentCategory = 'c1' | 'c2' | 'c3' | 'c4' | 'c5' | 'c6' | 'c7' | 'c8' | 'c9';

export interface HarnessComponent {
  id: string;
  name: string;
  category: ComponentCategory;
  type: string;
  label: string;
  path: string;
  description: string;
  tags: string[];
  content: string;
  extra_files?: Record<string, string>;
  source: 'preset' | 'custom' | 'run';
  updated_at: string;
}

export interface ComponentTemplate {
  id: string;
  category: ComponentCategory;
  type: string;
  name: string;
  label: string;
  path: string;
  description: string;
  tags: string[];
  content: string;
  extra_files?: Record<string, string>;
}

export interface SandboxCategorySnapshot {
  category: ComponentCategory;
  exists: boolean;
  file_count: number;
  char_count: number;
  primary_path: string;
  primary_content: string;
  base_primary_content?: string;
  files: Record<string, string>;
  base_files?: Record<string, string>;
  diff_from_base: boolean;
}

export interface HarnessSnapshot {
  run_id?: string;
  task_id?: string;
  label?: string;
  systemprompt?: string;
  guardrails?: string;
  memory?: string;
  tool_guidance?: string;
  subagents?: Record<string, string | Record<string, unknown>>;
  skills?: Record<string, string | Record<string, string>>;
  plugins?: Record<string, string>;
  scripts?: Record<string, string>;
  mcp?: Record<string, string>;
  raw_files?: Record<string, string>;
  by_category?: Partial<Record<ComponentCategory, SandboxCategorySnapshot>>;
  [key: string]: unknown;
}

export interface UnifiedApiConfig {
  base_url: string;
  api_key_configured: boolean;
  api_key_masked: string;
  model: string;
  protocol: string;
  improver_model: string;
  effective_improver_model: string;
  judge_model: string;
  judge_base_url: string;
  judge_api_key_configured: boolean;
  judge_api_key_masked: string;
  vertex_project: string;
  vertex_location: string;
}

export interface BridgeStatus {
  running: boolean;
  port?: number;
  host: string;
  upstream: string;
  local_url: string;
  container_url: string;
  key_configured: boolean;
  managed: boolean;
}

export interface EndpointProbeResult {
  ok: boolean;
  target: string;
  endpoint: string;
  protocol: string;
  status_code: number | null;
  latency_ms: number;
  message: string;
}

export interface FetchModelsResult {
  ok: boolean;
  models: string[];
  latency_ms: number;
  message: string;
}

export interface ExecutorItem {
  id: string;
  name: string;
  title: string;
  category: string;
  status: 'ready' | 'needs_config' | 'missing_deps' | 'optional' | 'needs_project';
  status_message: string;
  cli_available: boolean;
  cli_path: string;
  api_key_configured: boolean;
  api_key_masked?: string;
  current_model: string;
  model_override?: string;
  effort?: 'low' | 'medium' | 'high' | string;
  base_url?: string;
  container_url?: string;
  effective_base_url?: string;
  protocol?: string;
  protocol_override?: string;
  using_unified?: boolean;
  resolved_endpoint?: string;
  config_toml_status?: 'ok' | 'stale';
  config_toml_error?: string;
  improver_model?: string;
  effective_improver_model?: string;
  judge_model?: string;
  judge_base_url?: string;
  effective_judge_base_url?: string;
  vertex_project?: string;
  vertex_location?: string;
  supported_models: string[];
  capabilities: string[];
}

export interface ExecutorStatusResponse {
  active_executor: string;
  unified_config?: UnifiedApiConfig;
  bridge?: BridgeStatus;
  executors: ExecutorItem[];
}

export interface ExecutionJobInfo {
  job_id?: string;
  type?: string;
  command?: string[];
  exit_code?: number | null;
  started_at?: string;
  finished_at?: string;
  current_step_index?: number;
  current_node_id?: string;
}

export interface LiveStageStep {
  stepIndex: number;
  nodeId: string;
  stage: number;
  status: 'active' | 'completed';
  title?: string;
  line?: string;
  timestamp?: string;
}

export interface SystemStatus {
  status: {
    status: 'idle' | 'running' | 'completed' | 'failed' | 'terminated';
    job: ExecutionJobInfo | null;
    recent_logs_count: number;
  };
  workspace_root: string;
  runs_root: string;
}
