import { Link, useNavigate } from 'react-router-dom';
import BranchCard from '../components/BranchCard';
import { runBranchSimulation } from '../api/simulate';
import { useAppStore } from '../store/useAppStore';

export default function BranchesPage() {
  const navigate = useNavigate();
  const {
    parseResult,
    instruction,
    agentKey,
    evaluatorKey,
    conversations,
    runningBranchId,
  } = useAppStore();

  if (!parseResult) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <div className="text-slate-500">尚未解析任务指令。</div>
        <Link to="/config" className="text-indigo-600 underline text-sm">
          返回配置页
        </Link>
      </div>
    );
  }

  const handleRun = (branchId: string) => {
    if (runningBranchId) return;
    const branch = parseResult.branches.find((b) => b.id === branchId);
    if (!branch) return;
    runBranchSimulation({
      branch,
      instruction,
      scoring_criteria: parseResult.scoring_criteria,
      agent_key: agentKey,
      evaluator_key: evaluatorKey,
    });
    navigate(`/simulate/${branchId}`);
  };

  const handleView = (branchId: string) => navigate(`/simulate/${branchId}`);
  const handleReport = (branchId: string) => navigate(`/report/${branchId}`);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500">
            <Link to="/config" className="hover:underline">
              « 返回配置
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-800 mt-1">分支选择</h1>
          <p className="text-sm text-slate-500 mt-1">
            选择一个用户分支启动模拟。运行期间其他分支按钮会被禁用。
          </p>
        </div>
      </header>

      {runningBranchId && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm px-3 py-2">
          分支 <b>{runningBranchId}</b> 正在运行中，
          <button
            onClick={() => navigate(`/simulate/${runningBranchId}`)}
            className="ml-1 underline font-medium"
          >
            查看进度 →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {parseResult.branches.map((b) => (
          <BranchCard
            key={b.id}
            branch={b}
            conversation={conversations[b.id]}
            disabled={!!runningBranchId && runningBranchId !== b.id}
            onRun={() => handleRun(b.id)}
            onView={() => handleView(b.id)}
            onReport={() => handleReport(b.id)}
          />
        ))}
      </div>
    </div>
  );
}
