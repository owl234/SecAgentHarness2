import { ExecutorStatusResponse } from '../../types';

export type DrawerTabId = 'unified' | 'oc' | 'pi' | 'vertex';
export type SubstrateType = 'oc' | 'pi';

export interface ExecutorFormValues {
  // 0. Unified API (SEC_AGENT_HARNESS2_API_*)
  unifiedBaseUrl: string;
  unifiedApiKey: string;
  unifiedModel: string;
  unifiedProtocol: string;
  // 1. OpenCode
  ocModel: string;
  ocEffort: 'off' | 'low' | 'medium' | 'high';
  ocBaseUrl: string;
  ocApiKey: string;
  ocProtocol: string;
  // 2. Pi Coding Agent
  piModel: string;
  piEffort: 'off' | 'low' | 'medium' | 'high';
  piBaseUrl: string;
  piApiKey: string;
  piProtocol: string;
  // 3. Improver / Judge / Vertex AI
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
  ocModel: '',
  ocEffort: 'high',
  ocBaseUrl: '',
  ocApiKey: '',
  ocProtocol: '',
  piModel: '',
  piEffort: 'high',
  piBaseUrl: '',
  piApiKey: '',
  piProtocol: '',
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
    if (data.unified_config.judge_model_override !== undefined) {
      const bareOverride = data.unified_config.judge_model_override.replace(/^sec_agent_harness2\//, '').trim();
      next.judgeModel = bareOverride;
    } else {
      next.judgeModel = bareJudge && bareJudge !== next.unifiedModel ? bareJudge : '';
    }
    const rawJudgeBase = data.unified_config.judge_base_url || '';
    next.judgeBaseUrl = rawJudgeBase && rawJudgeBase !== next.unifiedBaseUrl ? rawJudgeBase : '';
    next.vertexProject = data.unified_config.vertex_project || '';
    next.vertexLocation = data.unified_config.vertex_location || 'global';
  }

  const oc = data.executors.find((e) => e.id === 'oc');
  if (oc) {
    next.ocModel = oc.model_override || oc.current_model || '';
    const ocEff = (oc.effort || '').toLowerCase();
    if (ocEff === 'off' || ocEff === 'low' || ocEff === 'medium' || ocEff === 'high') {
      next.ocEffort = ocEff;
    }
    next.ocBaseUrl = oc.base_url || '';
    next.ocProtocol = oc.protocol_override || '';
  }

  const pi = data.executors.find((e) => e.id === 'pi');
  if (pi) {
    next.piModel = pi.model_override || pi.current_model || '';
    const piEff = (pi.effort || '').toLowerCase();
    if (piEff === 'off' || piEff === 'low' || piEff === 'medium' || piEff === 'high') {
      next.piEffort = piEff;
    }
    next.piBaseUrl = pi.base_url || '';
    next.piProtocol = pi.protocol_override || '';
  }

  return next;
}
