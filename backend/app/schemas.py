from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Branch(BaseModel):
    id: str
    name: str
    description: str
    npc_persona: str


ItemKind = Literal[
    "mandatory_step",
    "conditional_response",
    "faq_entry",
    "constraint",
    "opening",
]


class ScoringItem(BaseModel):
    id: str
    description: str
    source: str
    eval_type: Literal["rule", "keyword", "llm"]
    keywords: Optional[list[str]] = None
    rule: Optional[str] = None
    rule_param: Optional[Any] = None
    applicable_branches: Optional[list[str]] = None
    item_kind: Optional[ItemKind] = None


class DimensionCriteria(BaseModel):
    weight: float
    items: list[ScoringItem] = Field(default_factory=list)


class EfficiencyCriteria(BaseModel):
    weight: float


class ScoringCriteria(BaseModel):
    task_completion: DimensionCriteria
    instruction_following: DimensionCriteria
    naturalness: DimensionCriteria
    branch_handling: DimensionCriteria
    efficiency: EfficiencyCriteria


class ParseRequest(BaseModel):
    instruction: str
    api_key: str = ""  # 已废弃：服务端从 DEEPSEEK_API_KEY 读取，保留字段仅为兼容旧前端


class ParseResponse(BaseModel):
    branches: list[Branch]
    scoring_criteria: ScoringCriteria
    tone_summary: Optional[str] = None


class ConversationTurn(BaseModel):
    turn: int
    role: Literal["agent", "user"]
    text: str


class ConversationData(BaseModel):
    branch_id: str
    turns: list[ConversationTurn]
    status: Literal["ended", "max_turns", "user_aborted", "llm_error"]
    total_turns: int


class EvaluateRequest(BaseModel):
    instruction: str
    branch: Branch
    conversation: ConversationData
    scoring_criteria: ScoringCriteria
    evaluator_key: str
    tone_summary: Optional[str] = None


class ScoreItemResult(BaseModel):
    id: str
    description: str
    source: str
    eval_type: Literal["rule", "keyword", "llm"]
    applicable: bool
    score: Optional[float] = None
    reason: str = ""


class DimensionScoreResult(BaseModel):
    dimension: str
    weight: float
    score: Optional[float] = None
    items: list[ScoreItemResult] = Field(default_factory=list)


class EfficiencyResult(BaseModel):
    weight: float
    score: Optional[float] = None
    actual_turns: int
    agent_turns: int
    invalid_turns: int
    invalid_breakdown: dict[str, int]
    reason: str


class Report(BaseModel):
    branch_id: str
    overall: float
    dimensions: dict[str, DimensionScoreResult]
    efficiency: EfficiencyResult
    advantages: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
