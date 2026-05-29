import type { Branch, ConversationStatus, ScoringCriteria, Turn, TurnRole } from '../types';
import { runEvaluate } from './evaluate';
import { useAppStore } from '../store/useAppStore';

function countAgentTurns(turns: Turn[]): number {
  return turns.filter((t) => t.role === 'agent').length;
}

interface StartParams {
  branch: Branch;
  instruction: string;
  scoring_criteria: ScoringCriteria;
  agent_key: string;
  evaluator_key: string;
}

const aborters = new Map<string, AbortController>();

export function abortBranch(branchId: string) {
  const c = aborters.get(branchId);
  if (!c) return;
  aborters.delete(branchId);
  c.abort();
  const store = useAppStore.getState();
  const conv = store.conversations[branchId];
  store.finishConversation(branchId, 'user_aborted', countAgentTurns(conv?.turns ?? []));
}

export function runBranchSimulation(params: StartParams) {
  const store = useAppStore.getState();
  if (store.runningBranchId) return;
  const branchId = params.branch.id;
  store.startConversation(branchId);

  const controller = new AbortController();
  aborters.set(branchId, controller);
  void runStream(branchId, params, controller.signal);
}

async function runStream(branchId: string, params: StartParams, signal: AbortSignal) {
  let res: Response;
  try {
    res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/simulate/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') return;
    aborters.delete(branchId);
    useAppStore.getState().errorConversation(branchId, `网络异常：${(e as Error).message}`);
    return;
  }

  if (!res.ok || !res.body) {
    aborters.delete(branchId);
    let body = '';
    try {
      body = await res.text();
    } catch {
      /* ignore */
    }
    useAppStore.getState().errorConversation(branchId, `HTTP ${res.status} ${body.slice(0, 200)}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let gotDone = false;

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
      if (eventMarksDone(dispatch(branchId, raw, params))) gotDone = true;
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buf += decoder.decode(value, { stream: !done });
      flushEvents();
      if (done) {
        if (buf.trim()) {
          if (eventMarksDone(dispatch(branchId, buf, params))) gotDone = true;
          buf = '';
        }
        break;
      }
    }
    if (!gotDone) {
      // #region agent log
      fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '1793b4' },
        body: JSON.stringify({
          sessionId: '1793b4',
          runId: 'post-fix',
          hypothesisId: 'H6',
          location: 'simulate.ts:runStream',
          message: 'stream_end_without_done',
          data: { branchId, leftoverBufLen: buf.length },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
      // #endregion
      aborters.delete(branchId);
      useAppStore.getState().errorConversation(branchId, '连接意外中断，模拟未完成');
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return;
    aborters.delete(branchId);
    const errName = (e as Error).name || 'Error';
    const errMsg = (e as Error).message || errName;
    // #region agent log
    fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'fb3d39'},body:JSON.stringify({sessionId:'fb3d39',hypothesisId:'H3',location:'simulate.ts:runStream',message:'stream_read_error',data:{branchId,errName,errMsg},timestamp:Date.now()})}).catch(()=>{});
    // #endregion
    useAppStore.getState().errorConversation(branchId, `网络异常：${errMsg}`);
  }
}

function eventMarksDone(event: string): boolean {
  return event === 'done';
}

function dispatch(branchId: string, raw: string, params: StartParams): string {
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
    // #region agent log
    fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '1793b4' },
      body: JSON.stringify({
        sessionId: '1793b4',
        hypothesisId: 'H3',
        location: 'simulate.ts:dispatch',
        message: 'json_parse_failed',
        data: { raw: raw.slice(0, 200) },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
    return event;
  }

  const store = useAppStore.getState();
  const turn = Number(payload.turn);
  const role = payload.role as TurnRole;
  const text = String(payload.text ?? '');

  // #region agent log
  fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '1793b4' },
    body: JSON.stringify({
      sessionId: '1793b4',
      hypothesisId: event === 'delta' ? 'H2' : 'H3',
      location: 'simulate.ts:dispatch',
      message: 'sse_event',
      data: { event, turn, role, textLen: text.length },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion

  switch (event) {
    case 'turn_start':
      store.beginTurn(branchId, turn, role);
      break;
    case 'delta':
      store.appendDelta(branchId, turn, role, text);
      break;
    case 'turn_end':
      store.endTurn(branchId, turn, role, text);
      break;
    case 'done': {
      const reason = String(payload.reason ?? 'ended') as ConversationStatus;
      const total = Number(payload.total_turns ?? 0);
      aborters.delete(branchId);
      store.finishConversation(branchId, reason, total);
      if (reason === 'ended' || reason === 'max_turns') {
        prefetchEvaluate(branchId, params);
      }
      break;
    }
    case 'error': {
      // #region agent log
      fetch('http://127.0.0.1:7456/ingest/a0e45155-c3fd-453e-878d-00c592c80c43',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'fb3d39'},body:JSON.stringify({sessionId:'fb3d39',hypothesisId:'H1',location:'simulate.ts:dispatch',message:'sse_error_event',data:{branchId,turn,role,errorMessage:String(payload.message??'').slice(0,400)},timestamp:Date.now()})}).catch(()=>{});
      fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'b3a46e' },
        body: JSON.stringify({
          sessionId: 'b3a46e',
          hypothesisId: 'H1',
          location: 'simulate.ts:dispatch',
          message: 'sse_error_event',
          data: {
            branchId,
            turn,
            role,
            errorMessage: String(payload.message ?? '').slice(0, 400),
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
      // #endregion
      aborters.delete(branchId);
      store.errorConversation(branchId, String(payload.message ?? 'LLM 错误'));
      break;
    }
    default:
      break;
  }
  return event;
}

function prefetchEvaluate(branchId: string, params: StartParams) {
  const store = useAppStore.getState();
  const entry = store.reports[branchId];
  if (entry?.status === 'loading' || entry?.status === 'ready') return;
  const conversation = store.conversations[branchId];
  if (!conversation || conversation.status === 'running') return;
  void runEvaluate({
    branch: params.branch,
    conversation,
    scoring_criteria: params.scoring_criteria,
    instruction: params.instruction,
    evaluator_key: params.evaluator_key,
    tone_summary: store.parseResult?.tone_summary,
  }).catch(() => {
    /* 错误已写入 store */
  });
}
