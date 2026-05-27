import type { Turn } from '../types';

interface Props {
  turn: Turn;
}

export default function ChatBubble({ turn }: Props) {
  const isAgent = turn.role === 'agent';
  const align = isAgent ? 'justify-start' : 'justify-end';
  const bubbleCls = isAgent
    ? 'bg-white border border-slate-200 text-slate-800'
    : 'bg-indigo-600 text-white';
  const labelCls = isAgent ? 'text-slate-500' : 'text-indigo-500';

  return (
    <div className={`flex ${align}`}>
      <div className="max-w-[80%]">
        <div className={`text-xs mb-1 ${labelCls}`}>
          {isAgent ? `第 ${turn.turn} 轮 · 数字人` : '用户'}
        </div>
        <div className={`rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap leading-relaxed ${bubbleCls}`}>
          {turn.text || <span className="opacity-60">…</span>}
          {!turn.done && <span className="ml-1 inline-block animate-pulse">▍</span>}
        </div>
      </div>
    </div>
  );
}
