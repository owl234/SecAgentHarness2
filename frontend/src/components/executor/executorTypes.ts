import { ExecutorStatusResponse } from '../../types';

export type DrawerTabId = 'unified' | 'claude' | 'oc' | 'cx' | 'vertex';

export interface ExecutorFormValues {
  // 0. Unified API (SEC_AGENT_HARNESS2_API_*)
  unifiedBaseUrl: string;
  unifiedApiKey: string;
  unifiedModel: string;
  unifiedProtocol: string;
  // 1. Claude
  claudeModel: string;
  claudeEffort: 'low' | 'medium' | 'high';
  claudeBaseUrl: string;
  claudeApiKey: string;
  claudeProtocol: string;
  // 2. OpenCode
  ocModel: string;
  ocBaseUrl: string;
  ocApiKey: string;
  ocProtocol: string;
  // 3. Codex
  cxModel: string;
  cxBaseUrl: string;
  cxContainerUrl: string;
  cxApiKey: string;
  bridgeHost: '127.0.0.1' | '0.0.0.0';
  // 4. Improver / Judge / Vertex AI
  improverModel: string;
  judgeModel: string;
  judgeBaseUrl: string;
  judgeApiKey: string;
  vertexProject: string;
  vertexLocation: string;
}

export const INITIAL_EXECUTOR_FORM: ExecutorFormValues = {
  unifiedBaseUrl: '',
  unifiedApiKey: '',
  unifiedModel: '',
  unifiedProtocol: '',
  claudeModel: '',
  claudeEffort: 'high',
  claudeBaseUrl: '',
  claudeApiKey: '',
  claudeProtocol: '',
  ocModel: '',
  ocBaseUrl: '',
  ocApiKey: '',
  ocProtocol: '',
  cxModel: '',
  cxBaseUrl: '',
  cxContainerUrl: '',
  cxApiKey: '',
  bridgeHost: '127.0.0.1',
  improverModel: '',
  judgeModel: '',
  judgeBaseUrl: '',
  judgeApiKey: '',
  vertexProject: '',
  vertexLocation: 'global',
};

export function buildFormFromExecutorsData(
  data: ExecutorStatusResponse,
  prev: ExecutorFormValues
): ExecutorFormValues {
  const next = { ...prev };
  next.unifiedApiKey = '';
  next.judgeApiKey = '';

  if (data.unified_config) {
    next.unifiedBaseUrl = data.unified_config.base_url || '';
    const rawModel = data.unified_config.model || '';
    next.unifiedModel = rawModel.replace(/^sec_agent_harness2\//, '');
    next.unifiedProtocol = data.unified_config.protocol || '';
    next.improverModel = data.unified_config.improver_model || '';
    const rawJudgeModel = data.unified_config.judge_model || '';
    const bareJudge = rawJudgeModel.replace(/^sec_agent_harness2\//, '');
    next.judgeModel = bareJudge && bareJudge !== next.unifiedModel ? bareJudge : '';
    const rawJudgeBase = data.unified_config.judge_base_url || '';
    next.judgeBaseUrl = rawJudgeBase && rawJudgeBase !== next.unifiedBaseUrl ? rawJudgeBase : '';
    next.vertexProject = data.unified_config.vertex_project || '';
    next.vertexLocation = data.unified_config.vertex_location || 'global';
  }

  const claude = data.executors.find((e) => e.id === 'claude');
  if (claude) {
    next.claudeModel = claude.model_override || claude.current_model || '';
    if (claude.effort === 'low' || claude.effort === 'medium' || claude.effort === 'high') {
      next.claudeEffort = claude.effort;
    }
    next.claudeBaseUrl = claude.base_url || '';
    next.claudeProtocol = claude.protocol_override || '';
  }

  const oc = data.executors.find((e) => e.id === 'oc');
  if (oc) {
    next.ocModel = oc.model_override || oc.current_model || '';
    next.ocBaseUrl = oc.base_url || '';
    next.ocProtocol = oc.protocol_override || '';
  }

  const cx = data.executors.find((e) => e.id === 'cx');
  if (cx) {
    next.cxModel = cx.model_override || cx.current_model || '';
    next.cxBaseUrl = cx.base_url || '';
    next.cxContainerUrl = cx.container_url || '';
  }

  return next;
}
