import type { Branch, Conversation, Report, ReportProgress, ScoringCriteria } from '../types';
import { useAppStore } from '../store/useAppStore';

interface RunEvaluateParams {
  branch: Branch;
  conversation: Conversation;
  scoring_criteria: ScoringCriteria;
  instruction: string;
  evaluator_key: string;
  tone_summary?: string;
}

function toBackendStatus(s: Conversation['status']): string {
  if (s === 'running') return 'ended';
  return s;
}

function countAgentTurns(turns: Conversation['turns']): number {
  return turns.filter((t) => t.role === 'agent').length;
}

function buildEvaluateBody(params: RunEvaluateParams) {
  const branchId = params.branch.id;
  return {
    instruction: params.instruction,
    branch: params.branch,
    scoring_criteria: params.scoring_criteria,
    evaluator_key: params.evaluator_key,
    tone_summary: params.tone_summary,
    conversation: {
      branch_id: branchId,
      turns: params.conversation.turns
        .filter((t) => t.done && t.text.length > 0)
        .map((t) => ({ turn: t.turn, role: t.role, text: t.text })),
      status: toBackendStatus(params.conversation.status),
      total_turns:
        params.conversation.totalTurns ?? countAgentTurns(params.conversation.turns),
    },
  };
}

function toReportProgress(payload: Record<string, unknown>): ReportProgress {
  return {
    phase: String(payload.phase ?? 'scoring') as ReportProgress['phase'],
    completedItems: Number(payload.completed_items ?? 0),
    totalItems: Number(payload.total_items ?? 0),
    currentDimension: payload.current_dimension
      ? String(payload.current_dimension)
      : undefined,
  };
}

function dispatchEvaluateEvent(branchId: string, raw: string): string {
  let event = 'message';
  const dataLines: string[] = [];
  for (const rawLine of raw.split('\n')) {
    const line = rawLine.replace(/\r$/, '');
    if (!line || line.startsWith(':')) continue;
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
  }
  if (!dataLines.length) return event;

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(dataLines.join('\n'));
  } catch {
    return event;
  }

  const store = useAppStore.getState();
  switch (event) {
    case 'progress':
      store.updateReportProgress(branchId, toReportProgress(payload));
      break;
    case 'done':
      store.setReport(branchId, payload as unknown as Report);
      break;
    case 'error':
      store.errorReport(branchId, String(payload.message ?? '评测失败'));
      break;
    default:
      break;
  }
  return event;
}

export async function runEvaluate(params: RunEvaluateParams): Promise<Report> {
  const store = useAppStore.getState();
  const branchId = params.branch.id;
  const existing = store.reports[branchId];
  if (existing?.status === 'ready' && existing.data) return existing.data;
  if (existing?.status === 'loading') {
    return new Promise((resolve, reject) => {
      const unsub = useAppStore.subscribe((s) => {
        const entry = s.reports[branchId];
        if (entry?.status === 'ready' && entry.data) {
          unsub();
          resolve(entry.data);
        } else if (entry?.status === 'error') {
          unsub();
          reject(new Error(entry.error ?? '评测失败'));
        }
      });
    });
  }

  store.startReport(branchId);
  const body = buildEvaluateBody(params);
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';
  const streamUrl = `${apiBase}/api/evaluate/stream`;
  // #region agent log
  fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'fb3d39'},body:JSON.stringify({sessionId:'fb3d39',hypothesisId:'H1-H3',location:'evaluate.ts:runEvaluate',message:'fetch_stream_start',data:{streamUrl,apiBaseSet:!!import.meta.env.VITE_API_BASE_URL,branchId},timestamp:Date.now()})}).catch(()=>{});
  // #endregion

  let res: Response;
  try {
    res = await fetch(streamUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
    const msg = `网络异常：${(e as Error).message}`;
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }

  if (!res.ok || !res.body) {
    const bodyText = await res.text();
    // #region agent log
    fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'fb3d39'},body:JSON.stringify({sessionId:'fb3d39',hypothesisId:'H1-H2',location:'evaluate.ts:runEvaluate',message:'fetch_stream_failed',data:{status:res.status,streamUrl,bodyPreview:bodyText.slice(0,200)},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    let detail = bodyText;
    try {
      detail = bodyText ? JSON.stringify(JSON.parse(bodyText)) : '';
    } catch {
      /* 非 JSON 响应，保留 bodyText */
    }
    const msg = `HTTP ${res.status}：${detail.slice(0, 300)}`;
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let report: Report | null = null;

  const flushEvents = () => {
    while (true) {
      const crlf = buf.indexOf('\r\n\r\n');
      const lf = buf.indexOf('\n\n');
      let sep: number;
      let sepLen: number;
      if (crlf >= 0 && (lf < 0 || crlf <= lf)) {
        sep = crlf;
        sepLen = 4;
      } else if (lf >= 0) {
        sep = lf;
        sepLen = 2;
      } else {
        break;
      }
      const raw = buf.slice(0, sep);
      buf = buf.slice(sep + sepLen);
      if (dispatchEvaluateEvent(branchId, raw) === 'done') {
        report = useAppStore.getState().reports[branchId]?.data ?? null;
      }
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buf += decoder.decode(value, { stream: !done });
      flushEvents();
      if (done) {
        if (buf.trim()) {
          dispatchEvaluateEvent(branchId, buf);
          report = useAppStore.getState().reports[branchId]?.data ?? report;
          buf = '';
        }
        break;
      }
    }
  } catch (e) {
    const msg = `网络异常：${(e as Error).message}`;
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }

  if (!report) {
    const entry = useAppStore.getState().reports[branchId];
    if (entry?.status === 'error') throw new Error(entry.error ?? '评测失败');
    const msg = '连接意外中断，评测未完成';
    store.errorReport(branchId, msg);
    throw new Error(msg);
  }
  return report;
}
