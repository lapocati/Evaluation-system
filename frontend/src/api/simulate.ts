import type { Branch, ConversationStatus, ScoringCriteria, TurnRole } from '../types';
import { useAppStore } from '../store/useAppStore';

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
  store.finishConversation(branchId, 'user_aborted', conv?.turns.length ?? 0);
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
    res = await fetch('/api/simulate/stream', {
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

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
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
        dispatch(branchId, raw);
      }
    }
  } catch (e) {
    if ((e as Error).name === 'AbortError') return;
    aborters.delete(branchId);
    useAppStore.getState().errorConversation(branchId, (e as Error).message);
  }
}

function dispatch(branchId: string, raw: string) {
  let event = 'message';
  const dataLines: string[] = [];
  for (const rawLine of raw.split('\n')) {
    const line = rawLine.replace(/\r$/, '');
    if (!line || line.startsWith(':')) continue;
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
  }
  if (!dataLines.length) return;

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(dataLines.join('\n'));
  } catch {
    return;
  }

  const store = useAppStore.getState();
  const turn = Number(payload.turn);
  const role = payload.role as TurnRole;
  const text = String(payload.text ?? '');

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
      break;
    }
    case 'error': {
      aborters.delete(branchId);
      store.errorConversation(branchId, String(payload.message ?? 'LLM 错误'));
      break;
    }
    default:
      break;
  }
}
