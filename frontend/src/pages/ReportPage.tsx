import { useEffect, useState } from 'react';

import type { DimensionKey, ReportProgress } from '../types';

import { Link, useNavigate, useParams } from 'react-router-dom';

import ChatBubble from '../components/ChatBubble';

import DimensionAccordion from '../components/DimensionAccordion';

import ScoreRadar from '../components/ScoreRadar';

import { runEvaluate } from '../api/evaluate';

import { useAppStore } from '../store/useAppStore';

import type { Conversation, Report } from '../types';



type ReportView = 'report' | 'conversation' | 'instruction';



const VIEW_TABS: { id: ReportView; label: string }[] = [

  { id: 'report', label: '评测报告' },

  { id: 'conversation', label: '完整对话记录' },

  { id: 'instruction', label: '任务指令' },

];



function colorForOverall(score: number) {

  if (score >= 0.8) return { bar: 'bg-emerald-500', text: 'text-emerald-700' };

  if (score >= 0.5) return { bar: 'bg-amber-500', text: 'text-amber-700' };

  return { bar: 'bg-rose-500', text: 'text-rose-700' };

}



export default function ReportPage() {

  const navigate = useNavigate();

  const { branchId = '' } = useParams<{ branchId: string }>();

  const [activeView, setActiveView] = useState<ReportView>('report');



  const parseResult = useAppStore((s) => s.parseResult);

  const instruction = useAppStore((s) => s.instruction);

  const evaluatorKey = useAppStore((s) => s.evaluatorKey);

  const conversations = useAppStore((s) => s.conversations);

  const conversation = conversations[branchId];

  const reportEntry = useAppStore((s) => s.reports[branchId]);



  const branch = parseResult?.branches.find((b) => b.id === branchId);



  useEffect(() => {

    if (!parseResult || !branch || !conversation) return;

    if (reportEntry) return;

    if (conversation.status === 'running') return;

    void runEvaluate({

      branch,

      conversation,

      scoring_criteria: parseResult.scoring_criteria,

      instruction,

      evaluator_key: evaluatorKey,

      tone_summary: parseResult.tone_summary,

    }).catch(() => {

      /* 错误已写入 store */

    });

  }, [branch, conversation, parseResult, reportEntry, instruction, evaluatorKey]);



  if (!parseResult) {

    return (

      <div className="max-w-4xl mx-auto p-6 space-y-2">

        <div className="text-slate-500 text-sm">尚未解析任务指令。</div>

        <Link to="/config" className="text-indigo-600 underline text-sm">

          返回配置页

        </Link>

      </div>

    );

  }

  if (!branch) {

    return (

      <div className="max-w-4xl mx-auto p-6 space-y-2">

        <div className="text-slate-500 text-sm">未找到该分支：{branchId}</div>

        <Link to="/branches" className="text-indigo-600 underline text-sm">

          返回分支选择

        </Link>

      </div>

    );

  }

  if (!conversation || conversation.status === 'running') {

    return (

      <div className="max-w-4xl mx-auto p-6 space-y-2">

        <div className="text-slate-500 text-sm">该分支尚未跑完，无法生成报告。</div>

        <Link to={`/simulate/${branchId}`} className="text-indigo-600 underline text-sm">

          查看对话进度

        </Link>

      </div>

    );

  }



  const allBranches = parseResult.branches;



  return (

    <div className="max-w-5xl mx-auto p-6 space-y-5">

      <header>

        <div className="text-xs text-slate-500">

          <Link to="/branches" className="hover:underline">

            « 返回分支选择

          </Link>

        </div>

        <h1 className="text-2xl font-bold text-slate-800 mt-1">评测报告</h1>

        {/* 轻量 segmented control：次级人格分支切换 */}
        <div className="mt-2 inline-flex items-center flex-wrap rounded-lg bg-slate-100 p-0.5 gap-0.5">

          {allBranches.map((b) => {

            const isActive = b.id === branchId;

            return (

              <button

                key={b.id}

                type="button"

                onClick={() => {
                  const target = conversations[b.id];
                  if (!target || target.status === 'running') {
                    navigate('/branches');
                    return;
                  }
                  navigate(`/report/${b.id}`);
                }}

                className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${

                  isActive

                    ? 'bg-indigo-600 text-white shadow-sm'

                    : 'bg-transparent text-slate-500 hover:text-slate-700'

                }`}

              >

                {b.id} · {b.name}

              </button>

            );

          })}

        </div>

      </header>



      {!reportEntry || reportEntry.status === 'loading' ? (

        <LoadingPanel progress={reportEntry?.progress} />

      ) : reportEntry.status === 'error' ? (

        <ErrorPanel

          message={reportEntry.error ?? '未知错误'}

          onRetry={() => {

            void runEvaluate({

              branch,

              conversation,

              scoring_criteria: parseResult.scoring_criteria,

              instruction,

              evaluator_key: evaluatorKey,

              tone_summary: parseResult.tone_summary,

            }).catch(() => undefined);

          }}

        />

      ) : reportEntry.data ? (

        <div className="space-y-4">

          <ViewTabBar activeView={activeView} onChange={setActiveView} />

          {activeView === 'report' && (

            <ReportBody report={reportEntry.data} branchName={branch.name} />

          )}

          {activeView === 'conversation' && (

            <ConversationPanel conversation={conversation} />

          )}

          {activeView === 'instruction' && (

            <InstructionPanel instruction={instruction} />

          )}

        </div>

      ) : null}

    </div>

  );

}



function ViewTabBar({

  activeView,

  onChange,

}: {

  activeView: ReportView;

  onChange: (view: ReportView) => void;

}) {

  return (

    <div className="flex items-center gap-6 border-b border-slate-200 flex-wrap">

      {/* 页面级主导航：underline tab，视觉权重高于分支切换 */}

      {VIEW_TABS.map((tab) => {

        const isActive = tab.id === activeView;

        return (

          <button

            key={tab.id}

            type="button"

            onClick={() => onChange(tab.id)}

            className={`relative pb-2.5 pt-1 text-sm font-medium transition-colors ${

              isActive

                ? 'text-indigo-600 border-b-2 border-indigo-600 -mb-px'

                : 'text-slate-500 hover:text-slate-800'

            }`}

          >

            {tab.label}

          </button>

        );

      })}

    </div>

  );

}



function LoadingPanel({ progress }: { progress?: ReportProgress }) {
  const DIM_LABEL: Record<DimensionKey, string> = {
    task_completion: '任务完成',
    instruction_following: '指令遵循',
    naturalness: '自然度',
    branch_handling: '分支处理',
  };

  let statusText = '正在评测中（包含多次 LLM 调用，可能 10–30 秒）…';
  if (progress) {
    if (progress.phase === 'summary') {
      statusText = '正在生成优势与改进建议…';
    } else if (progress.phase === 'efficiency') {
      statusText = '正在计算效率维度…';
    } else if (progress.currentDimension && progress.currentDimension in DIM_LABEL) {
      const dim = progress.currentDimension as DimensionKey;
      statusText = `正在评分：${DIM_LABEL[dim]}（${progress.completedItems}/${progress.totalItems}）`;
    } else if (progress.totalItems > 0) {
      statusText = `正在评分子项（${progress.completedItems}/${progress.totalItems}）`;
    }
  }

  return (

    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">

      <div className="inline-block w-5 h-5 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin mr-2 align-middle" />

      {statusText}

    </div>

  );

}



function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {

  return (

    <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 space-y-3">

      <div className="text-rose-700 text-sm font-medium">评测失败</div>

      <div className="text-xs text-rose-600 whitespace-pre-wrap break-all">{message}</div>

      <button

        type="button"

        onClick={onRetry}

        className="px-3 py-1.5 rounded-md bg-rose-600 text-white text-sm hover:bg-rose-700"

      >

        重试

      </button>

    </div>

  );

}



function ConversationPanel({ conversation }: { conversation: Conversation }) {

  const turns = conversation.turns.filter((t) => t.done && t.text.length > 0);



  return (

    <section className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3 max-h-[70vh] overflow-y-auto">

      {turns.length === 0 ? (

        <div className="text-center text-sm text-slate-400 py-8">暂无对话记录</div>

      ) : (

        turns.map((t, i) => <ChatBubble key={`${t.turn}-${t.role}-${i}`} turn={t} />)

      )}

    </section>

  );

}



function InstructionPanel({ instruction }: { instruction: string }) {

  return (

    <section className="rounded-xl border border-slate-200 bg-white p-5">

      <div className="text-sm font-medium text-slate-700 mb-3">任务指令</div>

      {instruction.trim().length === 0 ? (

        <div className="text-xs text-slate-500">（暂无）</div>

      ) : (

        <pre className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed font-sans">

          {instruction}

        </pre>

      )}

    </section>

  );

}



function ReportBody({

  report,

  branchName,

}: {

  report: Pick<Report, 'overall' | 'advantages' | 'improvements' | 'dimensions' | 'efficiency'>;

  branchName: string;

}) {

  const overallPct = Math.round(report.overall * 100);

  const colors = colorForOverall(report.overall);



  return (

    <>

      <section className="rounded-xl border border-slate-200 bg-white p-5">

        <div className="flex items-baseline gap-3">

          <div className="text-sm text-slate-500">分支「{branchName}」综合得分</div>

          <div className={`text-4xl font-bold ${colors.text}`}>{overallPct}</div>

          <div className="text-sm text-slate-400">/ 100</div>

        </div>

        <div className="mt-3 h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">

          <div

            className={`h-full ${colors.bar} transition-all duration-500`}

            style={{ width: `${overallPct}%` }}

          />

        </div>

      </section>



      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        <section className="rounded-xl border border-slate-200 bg-white p-4">

          <div className="text-sm font-medium text-slate-700 mb-2">五维度雷达</div>

          <ScoreRadar report={report as Report} />

        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">

          <div>

            <div className="text-sm font-medium text-emerald-700 mb-1.5">✓ 优势</div>

            {report.advantages.length === 0 ? (

              <div className="text-xs text-slate-500">（暂无）</div>

            ) : (

              <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">

                {report.advantages.map((a, i) => (

                  <li key={i}>{a}</li>

                ))}

              </ul>

            )}

          </div>

          <div>

            <div className="text-sm font-medium text-rose-700 mb-1.5">! 改进建议</div>

            {report.improvements.length === 0 ? (

              <div className="text-xs text-slate-500">（暂无）</div>

            ) : (

              <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">

                {report.improvements.map((a, i) => (

                  <li key={i}>{a}</li>

                ))}

              </ul>

            )}

          </div>

        </section>

      </div>



      <section>

        <div className="text-sm font-medium text-slate-700 mb-2">维度详情</div>

        <DimensionAccordion dimensions={report.dimensions} efficiency={report.efficiency} />

      </section>

    </>

  );

}


