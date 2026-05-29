import type { ReportProgress } from '../types';
import {
  STEP_CURRENT_TITLE,
  STEP_SUBTITLE,
  useEvaluationRuntime,
  type StepId,
} from '../lib/evaluationRuntime';

interface Props {
  progress?: ReportProgress;
}

/** 评测运行时 UI：基于真实 SSE 步骤，非聊天式输出 */
export default function EvaluationRuntimePanel({ progress }: Props) {
  const runtime = useEvaluationRuntime(progress);
  const { completedSteps, currentStep, itemProgress } = runtime;

  // 底部进度：优先展示 SSE 子项计数（如 7/15），无子项时回退步级进度
  const showItemProgress = itemProgress.total > 0;
  const bottomCompleted = showItemProgress
    ? itemProgress.completed
    : runtime.progress.completed;
  const bottomTotal = showItemProgress ? itemProgress.total : runtime.progress.total;
  const barPct =
    bottomTotal > 0 ? Math.min(100, (bottomCompleted / bottomTotal) * 100) : 0;

  const currentId: StepId = currentStep?.id ?? 'task_completion';
  const currentTitle = STEP_CURRENT_TITLE[currentId];
  const currentSubtitle = STEP_SUBTITLE[currentId];

  return (
    <div className="space-y-8">
      {/* 顶部：固定提示白框，位置与原先 LoadingPanel 一致 */}
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
        <div className="inline-block w-5 h-5 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin mr-2 align-middle" />
        涉及多次 LLM 调用，预计用时 10~30 秒
      </div>

      {/* 中间：当前正在执行的分析项（视觉中心） */}
      <div className="py-10 text-center space-y-3">
        <div className="flex items-center justify-center gap-2.5">
          {/* 轻微 spinner，与 ◌ 语义一致 */}
          <span
            className="inline-block w-2 h-2 rounded-full border border-indigo-500 border-t-transparent animate-spin shrink-0"
            aria-hidden
          />
          <p className="text-xl sm:text-2xl font-semibold text-slate-800 tracking-tight">
            正在分析：{currentTitle}
          </p>
        </div>
        <p className="text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
          {currentSubtitle}
        </p>
      </div>

      {/* 历史记录：已完成步骤锚定底部，新项在下、旧项向上渐淡 */}
      {completedSteps.length > 0 && (
        <div className="relative min-h-[5rem] px-2">
          <div className="absolute inset-x-2 bottom-0 flex flex-col-reverse gap-2">
            {[...completedSteps].reverse().map((step, revIndex) => {
              const opacity = Math.max(0.35, 1 - revIndex * 0.22);
              return (
                <div
                  key={step.id}
                  className="flex items-center gap-2 text-sm text-slate-600 transition-all duration-500 ease-out"
                  style={{
                    opacity,
                    transform: `translateY(-${revIndex * 3}px)`,
                  }}
                >
                  <span className="text-emerald-600 font-medium shrink-0">✓</span>
                  <span>{step.label}分析完成</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 底部：整体评测进度 */}
      <div className="pt-2 space-y-2 border-t border-slate-100">
        <div className="flex items-baseline justify-between text-xs text-slate-500">
          <span className="uppercase tracking-wide font-medium">
            Overall Evaluation Progress
          </span>
          <span className="tabular-nums text-slate-700 font-semibold">
            {bottomCompleted} / {bottomTotal}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-indigo-600 transition-all duration-500 ease-out"
            style={{ width: `${barPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
