import type { Branch, Conversation, Report, ScoringCriteria } from '../types';
import { useAppStore } from '../store/useAppStore';

interface RunEvaluateParams {
  branch: Branch;
  conversation: Conversation;
  scoring_criteria: ScoringCriteria;
  instruction: string;
  evaluator_key: string;
}

function toBackendStatus(s: Conversation['status']): string {
  if (s === 'running') return 'ended';
  return s;
}

export async function runEvaluate(params: RunEvaluateParams): Promise<Report> {
  const store = useAppStore.getState();
  const branchId = params.branch.id;
  store.startReport(branchId);

  const body = {
    instruction: params.instruction,
    branch: params.branch,
    scoring_criteria: params.scoring_criteria,
    evaluator_key: params.evaluator_key,
    conversation: {
      branch_id: branchId,
      turns: params.conversation.turns
        .filter((t) => t.done && t.text.length > 0)
        .map((t) => ({ turn: t.turn, role: t.role, text: t.text })),
      status: toBackendStatus(params.conversation.status),
      total_turns:
        params.conversation.totalTurns ?? params.conversation.turns.length,
    },
  };

  let res: Response;
  try {
    res = await fetch('/api/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
    const msg = `网络异常：${(e as Error).message}`;
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }

  if (!res.ok) {
    let detail = '';
    try {
      detail = JSON.stringify(await res.json());
    } catch {
      detail = await res.text().catch(() => '');
    }
    const msg = `HTTP ${res.status}：${detail.slice(0, 300)}`;
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }

  const report = (await res.json()) as Report;
  store.setReport(branchId, report);
  return report;
}
