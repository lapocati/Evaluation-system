import { useRef } from 'react';
import type { DimensionKey, ReportProgress } from '../types';

/** 评测 Runtime 步骤 id：4 维度 + 效率 + 总结 */
export type StepId = DimensionKey | 'efficiency' | 'summary';
export type StepStatus = 'pending' | 'running' | 'completed';

export interface EvaluationStep {
  id: StepId;
  label: string;
  status: StepStatus;
}

/** selector 输出：供 Evaluation Runtime UI 消费 */
export interface EvaluationRuntimeState {
  completedSteps: EvaluationStep[];
  currentStep: EvaluationStep | null;
  /** 步级进度（6 步） */
  progress: { completed: number; total: number };
  /** SSE 子项进度，供底部 Overall Progress 展示 */
  itemProgress: { completed: number; total: number };
  stepStatus: Record<StepId, StepStatus>;
}

const STEP_ORDER: StepId[] = [
  'task_completion',
  'instruction_following',
  'naturalness',
  'branch_handling',
  'efficiency',
  'summary',
];

export const STEP_LABEL: Record<StepId, string> = {
  task_completion: '任务完成',
  instruction_following: '指令遵循',
  naturalness: '自然度',
  branch_handling: '分支处理',
  efficiency: '效率',
  summary: '生成建议',
};

/** 主区域「正在分析」标题用名 */
export const STEP_CURRENT_TITLE: Record<StepId, string> = {
  task_completion: '任务完成度',
  instruction_following: '指令遵循',
  naturalness: '自然度',
  branch_handling: '分支处理',
  efficiency: '效率',
  summary: '优势与改进建议',
};

/** 主区域副标题：真实步骤说明，非 LLM 推理文本 */
export const STEP_SUBTITLE: Record<StepId, string> = {
  task_completion: '检查关键任务是否真正完成…',
  instruction_following: '核对 Agent 是否遵循指令约束…',
  naturalness: '评估对话自然度与表达质量…',
  branch_handling: '验证分支场景处理是否正确…',
  efficiency: '计算无效轮次与对话效率…',
  summary: '汇总优势与改进建议…',
};

function buildSteps(stepStatus: Record<StepId, StepStatus>): EvaluationStep[] {
  return STEP_ORDER.map((id) => ({
    id,
    label: STEP_LABEL[id],
    status: stepStatus[id],
  }));
}

/** 从 SSE ReportProgress 派生 Runtime 四字段，不修改 store */
export function deriveEvaluationRuntime(progress?: ReportProgress): EvaluationRuntimeState {
  const totalSteps = STEP_ORDER.length;
  const stepStatus = Object.fromEntries(
    STEP_ORDER.map((id) => [id, 'pending' as StepStatus]),
  ) as Record<StepId, StepStatus>;

  const itemProgress = {
    completed: progress?.completedItems ?? 0,
    total: progress?.totalItems ?? 0,
  };

  if (!progress) {
    return {
      completedSteps: [],
      currentStep: null,
      progress: { completed: 0, total: totalSteps },
      itemProgress,
      stepStatus,
    };
  }

  const dimSteps = STEP_ORDER.slice(0, 4) as DimensionKey[];

  if (progress.phase === 'scoring') {
    let currentDim: StepId = 'task_completion';
    if (progress.currentDimension && dimSteps.includes(progress.currentDimension as DimensionKey)) {
      currentDim = progress.currentDimension as StepId;
    }

    const allItemsDone =
      progress.totalItems > 0 && progress.completedItems >= progress.totalItems;

    if (allItemsDone) {
      dimSteps.forEach((id) => {
        stepStatus[id] = 'completed';
      });
    } else {
      const currentIdx = dimSteps.indexOf(currentDim as DimensionKey);
      dimSteps.forEach((id, i) => {
        if (i < currentIdx) stepStatus[id] = 'completed';
        else if (i === currentIdx) stepStatus[id] = 'running';
      });
    }
  } else if (progress.phase === 'efficiency') {
    dimSteps.forEach((id) => {
      stepStatus[id] = 'completed';
    });
    stepStatus.efficiency = 'running';
  } else if (progress.phase === 'summary') {
    STEP_ORDER.slice(0, 5).forEach((id) => {
      stepStatus[id] = 'completed';
    });
    stepStatus.summary = 'running';
  }

  const steps = buildSteps(stepStatus);
  const completedSteps = steps.filter((s) => s.status === 'completed');
  const currentStep = steps.find((s) => s.status === 'running') ?? null;

  return {
    completedSteps,
    currentStep,
    progress: { completed: completedSteps.length, total: totalSteps },
    itemProgress,
    stepStatus,
  };
}

const DIM_STEPS = STEP_ORDER.slice(0, 4) as DimensionKey[];

/** 构建单调递增的历史步骤（并发评分时 currentDimension 会回退，历史不可收缩） */
function buildMonotonicCompletedSteps(
  progress: ReportProgress | undefined,
  maxDimIdx: number,
): EvaluationStep[] {
  if (!progress) return [];

  const ids: StepId[] = [];

  if (progress.phase === 'scoring') {
    const allDone =
      progress.totalItems > 0 && progress.completedItems >= progress.totalItems;
    if (allDone) {
      ids.push(...DIM_STEPS);
    } else if (maxDimIdx > 0) {
      // 仅展示已「经过」的维度（index < maxDimIdx），running 维度不进历史
      ids.push(...DIM_STEPS.slice(0, maxDimIdx));
    }
  } else if (progress.phase === 'efficiency') {
    ids.push(...DIM_STEPS);
  } else if (progress.phase === 'summary') {
    ids.push(...DIM_STEPS, 'efficiency');
  }

  return ids.map((id) => ({
    id,
    label: STEP_LABEL[id],
    status: 'completed' as const,
  }));
}

/**
 * 带单调历史的 Runtime hook：修复并发评分时 currentDimension 回退导致历史区闪烁消失。
 * deriveEvaluationRuntime 仍负责 currentStep；历史区用 maxDimIdx 高水位。
 */
export function useEvaluationRuntime(progress?: ReportProgress): EvaluationRuntimeState {
  const maxDimIdxRef = useRef(-1);
  const sessionTotalRef = useRef<number | null>(null);

  if (!progress) {
    maxDimIdxRef.current = -1;
    sessionTotalRef.current = null;
  } else if (
    sessionTotalRef.current !== progress.totalItems ||
    (progress.phase === 'scoring' && progress.completedItems === 0)
  ) {
    // 新一轮评测：重置高水位
    if (
      sessionTotalRef.current !== progress.totalItems ||
      (sessionTotalRef.current === progress.totalItems && progress.completedItems === 0)
    ) {
      maxDimIdxRef.current = -1;
    }
    sessionTotalRef.current = progress.totalItems;
  }

  if (progress?.phase === 'scoring' && progress.currentDimension) {
    const idx = DIM_STEPS.indexOf(progress.currentDimension as DimensionKey);
    if (idx >= 0) {
      maxDimIdxRef.current = Math.max(maxDimIdxRef.current, idx);
    }
  }

  const base = deriveEvaluationRuntime(progress);
  const completedSteps = buildMonotonicCompletedSteps(progress, maxDimIdxRef.current);

  return {
    ...base,
    completedSteps,
    progress: { completed: completedSteps.length, total: STEP_ORDER.length },
  };
}
