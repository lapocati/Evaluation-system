import type { Conversation } from '../types';

interface Props {
  conversation: Conversation;
}

const STATUS_META: Record<Conversation['status'], { text: string; cls: string }> = {
  running: { text: '运行中', cls: 'bg-amber-100 text-amber-700' },
  ended: { text: '已完成（双方告别）', cls: 'bg-emerald-100 text-emerald-700' },
  max_turns: { text: '达到最大轮数', cls: 'bg-orange-100 text-orange-700' },
  user_aborted: { text: '已被用户终止', cls: 'bg-slate-200 text-slate-600' },
  llm_error: { text: 'LLM 调用出错', cls: 'bg-red-100 text-red-700' },
};

function agentTurnCount(conversation: Conversation): number {
  if (conversation.totalTurns !== undefined) {
    return conversation.totalTurns;
  }
  return conversation.turns.filter((t) => t.role === 'agent').length;
}

export default function StatusPanel({ conversation }: Props) {
  const meta = STATUS_META[conversation.status];
  const turnCount = agentTurnCount(conversation);

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 flex items-center gap-4 flex-wrap text-sm">
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${meta.cls}`}>
        {meta.text}
      </span>
      <span className="text-slate-500">
        轮次：
        <span className="font-semibold ml-1 text-slate-800">{turnCount}</span>
      </span>
      {conversation.error && (
        <span className="text-red-600 text-xs break-all">{conversation.error}</span>
      )}
    </div>
  );
}
