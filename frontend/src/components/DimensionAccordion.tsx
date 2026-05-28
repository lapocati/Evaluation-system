import { useState } from 'react';
import type { DimensionKey, DimensionScoreResult, EfficiencyResult } from '../types';

const DIM_LABEL: Record<DimensionKey, string> = {
  task_completion: '任务完成',
  instruction_following: '指令遵循',
  naturalness: '自然度',
  branch_handling: '分支处理',
};

const EVAL_TYPE_LABEL: Record<string, string> = {
  rule: '规则',
  keyword: '关键词',
  llm: 'LLM',
};

function colorForScore(score: number | null) {
  if (score === null) return 'bg-slate-200 text-slate-600';
  if (score >= 0.8) return 'bg-emerald-100 text-emerald-700';
  if (score >= 0.5) return 'bg-amber-100 text-amber-700';
  return 'bg-rose-100 text-rose-700';
}

function fmtPct(score: number | null): string {
  if (score === null) return '—';
  return `${Math.round(score * 100)}`;
}

interface DimRowProps {
  dimensionKey: DimensionKey | 'efficiency';
  label: string;
  weight: number;
  score: number | null;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

function DimensionRow({ label, weight, score, defaultOpen, children }: DimRowProps) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition"
      >
        <span className="font-semibold text-slate-800">{label}</span>
        <span className="text-xs text-slate-500">权重 {Math.round(weight * 100)}%</span>
        <span
          className={`ml-auto text-sm font-semibold px-2.5 py-0.5 rounded-md ${colorForScore(score)}`}
        >
          {fmtPct(score)}
        </span>
        <span className="text-slate-400 text-xs w-3">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="border-t border-slate-100 px-4 py-3 space-y-2">{children}</div>}
    </div>
  );
}

interface Props {
  dimensions: Record<DimensionKey, DimensionScoreResult>;
  efficiency: EfficiencyResult;
}

export default function DimensionAccordion({ dimensions, efficiency }: Props) {
  const dimKeys = Object.keys(DIM_LABEL) as DimensionKey[];

  return (
    <div className="space-y-3">
      {dimKeys.map((key) => {
        const dim = dimensions[key];
        if (!dim) return null;
        return (
          <DimensionRow
            key={key}
            dimensionKey={key}
            label={DIM_LABEL[key]}
            weight={dim.weight}
            score={dim.score}
          >
            {dim.items.length === 0 && (
              <div className="text-xs text-slate-500">该维度无评分子项</div>
            )}
            {dim.items.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2"
              >
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded ${colorForScore(item.applicable ? item.score : null)} flex-shrink-0`}
                >
                  {item.applicable ? fmtPct(item.score) : '不适用'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-800">{item.description}</div>
                  <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                    <span className="px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">
                      {EVAL_TYPE_LABEL[item.eval_type] ?? item.eval_type}
                    </span>
                    <span className="text-slate-400">{item.source}</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-1 leading-relaxed">
                    {item.reason || '—'}
                  </div>
                </div>
              </div>
            ))}
          </DimensionRow>
        );
      })}

      <DimensionRow
        dimensionKey="efficiency"
        label="效率"
        weight={efficiency.weight}
        score={efficiency.score}
      >
        <div className="text-sm text-slate-700 space-y-1">
          <div>
            无效 <b>{efficiency.invalid_turns}</b> / <b>{efficiency.actual_turns}</b> 轮：重复{' '}
            <b>{efficiency.invalid_breakdown.repeat ?? 0}</b>、空话{' '}
            <b>{efficiency.invalid_breakdown.filler ?? 0}</b>、兜圈{' '}
            <b>{efficiency.invalid_breakdown.circular ?? 0}</b>
          </div>
          <div className="text-xs text-slate-600">{efficiency.reason}</div>
        </div>
      </DimensionRow>
    </div>
  );
}
