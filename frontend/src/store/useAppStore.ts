import { create } from 'zustand';
import type {
  Conversation,
  ConversationStatus,
  ParseResult,
  Report,
  ReportEntry,
  TurnRole,
} from '../types';

interface AppState {
  instruction: string;
  agentKey: string;
  evaluatorKey: string;
  parseResult: ParseResult | null;

  conversations: Record<string, Conversation>;
  runningBranchId: string | null;

  reports: Record<string, ReportEntry>;

  setInstruction: (v: string) => void;
  setAgentKey: (v: string) => void;
  setEvaluatorKey: (v: string) => void;
  setParseResult: (v: ParseResult | null) => void;

  startConversation: (branchId: string) => void;
  beginTurn: (branchId: string, turn: number, role: TurnRole) => void;
  appendDelta: (branchId: string, turn: number, role: TurnRole, text: string) => void;
  endTurn: (branchId: string, turn: number, role: TurnRole, text: string) => void;
  finishConversation: (
    branchId: string,
    status: ConversationStatus,
    totalTurns: number,
  ) => void;
  errorConversation: (branchId: string, message: string) => void;

  startReport: (branchId: string) => void;
  setReport: (branchId: string, report: Report) => void;
  errorReport: (branchId: string, message: string) => void;
}

function sameTurn(a: { turn: number; role: TurnRole }, turn: number, role: TurnRole) {
  return a.turn === turn && a.role === role;
}

export const useAppStore = create<AppState>((set) => ({
  instruction: '',
  agentKey: '',
  evaluatorKey: '',
  parseResult: null,

  conversations: {},
  runningBranchId: null,

  reports: {},

  setInstruction: (v) => set({ instruction: v }),
  setAgentKey: (v) => set({ agentKey: v }),
  setEvaluatorKey: (v) => set({ evaluatorKey: v }),
  setParseResult: (v) =>
    set({ parseResult: v, conversations: {}, runningBranchId: null, reports: {} }),

  startConversation: (branchId) =>
    set((s) => {
      const reports = { ...s.reports };
      delete reports[branchId];
      return {
        runningBranchId: branchId,
        conversations: {
          ...s.conversations,
          [branchId]: { branchId, turns: [], status: 'running' },
        },
        reports,
      };
    }),

  beginTurn: (branchId, turn, role) =>
    set((s) => {
      const conv = s.conversations[branchId];
      if (!conv) return s;
      if (conv.turns.some((t) => sameTurn(t, turn, role))) return s;
      return {
        conversations: {
          ...s.conversations,
          [branchId]: {
            ...conv,
            turns: [...conv.turns, { turn, role, text: '', done: false }],
          },
        },
      };
    }),

  appendDelta: (branchId, turn, role, text) =>
    set((s) => {
      const conv = s.conversations[branchId];
      if (!conv) return s;
      let turns = conv.turns;
      const hasMatch = turns.some((t) => sameTurn(t, turn, role));
      if (!hasMatch) {
        // #region agent log
        fetch('http://localhost:7492/ingest/018f9570-af31-4316-8237-a31d49daba47', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '1793b4' },
          body: JSON.stringify({
            sessionId: '1793b4',
            hypothesisId: 'H2',
            location: 'useAppStore.ts:appendDelta',
            message: 'auto_begin_turn',
            data: {
              branchId,
              turn,
              role,
              textLen: text.length,
              existingTurns: turns.map((t) => ({ turn: t.turn, role: t.role })),
            },
            timestamp: Date.now(),
          }),
        }).catch(() => {});
        // #endregion
        turns = [...turns, { turn, role, text: '', done: false }];
      }
      turns = turns.map((t) =>
        sameTurn(t, turn, role) ? { ...t, text: t.text + text } : t,
      );
      return { conversations: { ...s.conversations, [branchId]: { ...conv, turns } } };
    }),

  endTurn: (branchId, turn, role, text) =>
    set((s) => {
      const conv = s.conversations[branchId];
      if (!conv) return s;
      const turns = conv.turns.map((t) =>
        sameTurn(t, turn, role) ? { ...t, text, done: true } : t,
      );
      return { conversations: { ...s.conversations, [branchId]: { ...conv, turns } } };
    }),

  finishConversation: (branchId, status, totalTurns) =>
    set((s) => {
      const conv = s.conversations[branchId];
      if (!conv) return { runningBranchId: null };
      return {
        runningBranchId: s.runningBranchId === branchId ? null : s.runningBranchId,
        conversations: {
          ...s.conversations,
          [branchId]: { ...conv, status, totalTurns },
        },
      };
    }),

  errorConversation: (branchId, message) =>
    set((s) => {
      const conv = s.conversations[branchId];
      const base: Conversation = conv ?? { branchId, turns: [], status: 'llm_error' };
      return {
        runningBranchId: s.runningBranchId === branchId ? null : s.runningBranchId,
        conversations: {
          ...s.conversations,
          [branchId]: { ...base, status: 'llm_error', error: message },
        },
      };
    }),

  startReport: (branchId) =>
    set((s) => ({
      reports: { ...s.reports, [branchId]: { status: 'loading' } },
    })),

  setReport: (branchId, report) =>
    set((s) => ({
      reports: { ...s.reports, [branchId]: { status: 'ready', data: report } },
    })),

  errorReport: (branchId, message) =>
    set((s) => ({
      reports: {
        ...s.reports,
        [branchId]: { status: 'error', error: message },
      },
    })),
}));
