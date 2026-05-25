import { useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ChatBubble from '../components/ChatBubble';
import StatusPanel from '../components/StatusPanel';
import { abortBranch } from '../api/simulate';
import { useAppStore } from '../store/useAppStore';

export default function SimulatePage() {
  const navigate = useNavigate();
  const { branchId = '' } = useParams<{ branchId: string }>();
  const parseResult = useAppStore((s) => s.parseResult);
  const conversation = useAppStore((s) => s.conversations[branchId]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const branch = parseResult?.branches.find((b) => b.id === branchId);

  const lastTurnText = conversation?.turns[conversation.turns.length - 1]?.text ?? '';
  const lastTurnIndex = conversation?.turns.length ?? 0;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lastTurnText, lastTurnIndex]);

  if (!parseResult) {
    return (
      <div className="max-w-3xl mx-auto p-6 space-y-2">
        <div className="text-slate-500 text-sm">尚未解析任务指令。</div>
        <Link to="/config" className="text-indigo-600 underline text-sm">
          返回配置页
        </Link>
      </div>
    );
  }
  if (!branch) {
    return (
      <div className="max-w-3xl mx-auto p-6 space-y-2">
        <div className="text-slate-500 text-sm">未找到该分支：{branchId}</div>
        <Link to="/branches" className="text-indigo-600 underline text-sm">
          返回分支选择
        </Link>
      </div>
    );
  }
  if (!conversation) {
    return (
      <div className="max-w-3xl mx-auto p-6 space-y-2">
        <div className="text-slate-500 text-sm">
          该分支尚未运行。请回到分支选择页点击「▶ 运行」。
        </div>
        <Link to="/branches" className="text-indigo-600 underline text-sm">
          返回分支选择
        </Link>
      </div>
    );
  }

  const isRunning = conversation.status === 'running';
  const reportable =
    conversation.status === 'ended' || conversation.status === 'max_turns';

  return (
    <div className="max-w-3xl mx-auto p-6 flex flex-col h-screen">
      <header className="flex items-start justify-between flex-shrink-0 pb-4">
        <div>
          <div className="text-xs text-slate-500">
            <Link to="/branches" className="hover:underline">
              « 返回分支选择
            </Link>
          </div>
          <h1 className="text-xl font-bold text-slate-800 mt-1">
            分支 {branch.id} · {branch.name}
          </h1>
          <p className="text-xs text-slate-500 mt-1 line-clamp-1">{branch.description}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => abortBranch(branchId)}
            disabled={!isRunning}
            className="px-3 py-1.5 rounded-md bg-rose-600 text-white text-sm font-medium hover:bg-rose-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition"
          >
            ■ 终止运行
          </button>
          {reportable && (
            <button
              type="button"
              onClick={() => navigate(`/report/${branchId}`)}
              className="px-3 py-1.5 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition"
            >
              查看评测报告 →
            </button>
          )}
          {!isRunning && (
            <button
              type="button"
              onClick={() => navigate('/branches')}
              className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 text-sm hover:bg-slate-50 transition"
            >
              回到分支
            </button>
          )}
        </div>
      </header>

      <div className="flex-shrink-0 mb-3">
        <StatusPanel
          conversation={conversation}
          estimatedMaxTurns={branch.estimated_max_turns}
        />
      </div>

      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto bg-slate-50 rounded-xl p-4 space-y-3 border border-slate-200"
      >
        {conversation.turns.length === 0 && (
          <div className="text-center text-sm text-slate-400 py-8">等待数字人开场…</div>
        )}
        {conversation.turns.map((t) => (
          <ChatBubble key={t.turn} turn={t} />
        ))}
      </div>
    </div>
  );
}
