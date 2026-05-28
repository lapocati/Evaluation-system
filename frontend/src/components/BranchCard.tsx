import type { Branch, Conversation } from '../types';

interface Props {
  branch: Branch;
  conversation?: Conversation;
  disabled: boolean;
  onRun: () => void;
  onView: () => void;
  onReport?: () => void;
}

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  running: { text: '运行中', cls: 'bg-amber-100 text-amber-700' },
  ended: { text: '已完成', cls: 'bg-emerald-100 text-emerald-700' },
  max_turns: { text: '达到最大轮数', cls: 'bg-orange-100 text-orange-700' },
  user_aborted: { text: '已终止', cls: 'bg-slate-200 text-slate-600' },
  llm_error: { text: '出错', cls: 'bg-red-100 text-red-700' },
};

export default function BranchCard({
  branch,
  conversation,
  disabled,
  onRun,
  onView,
  onReport,
}: Props) {
  const status = conversation?.status;
  const label = status ? STATUS_LABEL[status] : null;
  const finished = status && status !== 'running';
  const reportable = status === 'ended' || status === 'max_turns';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">
          {branch.id}
        </span>
        <span className="font-semibold text-slate-800">{branch.name}</span>
        {label && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${label.cls}`}>
            {label.text}
          </span>
        )}
      </div>

      <div className="text-sm text-slate-600">{branch.description}</div>
      <div className="text-xs text-slate-500 line-clamp-3">{branch.npc_persona}</div>

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={onRun}
          disabled={disabled || status === 'running'}
          className="px-3 py-1.5 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition"
        >
          {finished ? '↻ 重新运行' : '▶ 运行'}
        </button>
        {conversation && (
          <button
            type="button"
            onClick={onView}
            className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50 transition"
          >
            {status === 'running' ? '查看进度' : '查看对话'}
          </button>
        )}
        {reportable && onReport && (
          <button
            type="button"
            onClick={onReport}
            className="px-3 py-1.5 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition"
          >
            查看报告
          </button>
        )}
      </div>
    </div>
  );
}
