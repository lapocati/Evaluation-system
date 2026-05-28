export type EvalType = 'rule' | 'keyword' | 'llm';

export type ItemKind =
  | 'mandatory_step'
  | 'conditional_response'
  | 'faq_entry'
  | 'constraint'
  | 'opening';

export interface Branch {
  id: string;
  name: string;
  description: string;
  estimated_max_turns: number;
  npc_persona: string;
}

export interface ScoringItem {
  id: string;
  description: string;
  source: string;
  eval_type: EvalType;
  keywords?: string[];
  rule?: string;
  rule_param?: unknown;
  applicable_branches?: string[];
  item_kind?: ItemKind;
}

export interface DimensionCriteria {
  weight: number;
  items: ScoringItem[];
}

export interface EfficiencyCriteria {
  weight: number;
  per_branch_max_turns: Record<string, number>;
}

export interface ScoringCriteria {
  task_completion: DimensionCriteria;
  instruction_following: DimensionCriteria;
  naturalness: DimensionCriteria;
  branch_handling: DimensionCriteria;
  efficiency: EfficiencyCriteria;
}

export interface ParseResult {
  branches: Branch[];
  scoring_criteria: ScoringCriteria;
  tone_summary?: string;
}

export type TurnRole = 'agent' | 'user';

export interface Turn {
  turn: number;
  role: TurnRole;
  text: string;
  done: boolean;
}

export type ConversationStatus =
  | 'running'
  | 'ended'
  | 'max_turns'
  | 'user_aborted'
  | 'llm_error';

export interface Conversation {
  branchId: string;
  turns: Turn[];
  status: ConversationStatus;
  reason?: string;
  totalTurns?: number;
  error?: string;
}

export type DimensionKey =
  | 'task_completion'
  | 'instruction_following'
  | 'naturalness'
  | 'branch_handling';

export interface ScoreItemResult {
  id: string;
  description: string;
  source: string;
  eval_type: EvalType;
  applicable: boolean;
  score: number | null;
  reason: string;
}

export interface DimensionScoreResult {
  dimension: DimensionKey;
  weight: number;
  score: number | null;
  items: ScoreItemResult[];
}

export interface EfficiencyResult {
  weight: number;
  score: number;
  actual_turns: number;
  estimated_max_turns: number;
  reason: string;
}

export interface Report {
  branch_id: string;
  overall: number;
  dimensions: Record<DimensionKey, DimensionScoreResult>;
  efficiency: EfficiencyResult;
  advantages: string[];
  improvements: string[];
}

export type ReportStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface ReportEntry {
  status: ReportStatus;
  data?: Report;
  error?: string;
}
