"""4 种规则类评分：max_chars_per_turn / no_repetition / forbidden_words / required_opening。

输入：scoring_criteria 的单个 ScoringItem + 完整对话 turns。
输出：(score: float in [0,1], reason: str)。
"""
from __future__ import annotations

from app.schemas import ConversationTurn, ScoringItem


def _agent_turns(turns: list[ConversationTurn]) -> list[ConversationTurn]:
    return [t for t in turns if t.role == "agent"]


def _levenshtein_sim(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return 1 - prev[lb] / max(la, lb)


def evaluate_rule(item: ScoringItem, turns: list[ConversationTurn]) -> tuple[float, str]:
    rule = (item.rule or "").strip()
    agents = _agent_turns(turns)

    if rule == "max_chars_per_turn":
        try:
            limit = int(item.rule_param) if item.rule_param is not None else 0
        except (TypeError, ValueError):
            return 1.0, "规则参数缺失，跳过检查"
        if limit <= 0 or not agents:
            return 1.0, "无适用轮次"
        violations = [t for t in agents if len(t.text) > limit]
        score = 1.0 - len(violations) / len(agents)
        if not violations:
            return 1.0, f"全部 {len(agents)} 轮均 ≤ {limit} 字"
        return max(0.0, score), (
            f"{len(violations)}/{len(agents)} 轮超过 {limit} 字（最长 "
            f"{max(len(t.text) for t in violations)} 字）"
        )

    if rule == "no_repetition":
        if len(agents) < 2:
            return 1.0, "轮次不足，无需检查"
        repeats = 0
        for i in range(1, len(agents)):
            if _levenshtein_sim(agents[i - 1].text, agents[i].text) >= 0.8:
                repeats += 1
        score = 1.0 - repeats / (len(agents) - 1)
        if repeats == 0:
            return 1.0, "相邻轮次未发现高度重复"
        return max(0.0, score), f"{repeats} 处相邻轮次相似度 ≥ 0.8"

    if rule == "forbidden_words":
        words: list[str] = []
        if isinstance(item.rule_param, list):
            words = [str(w) for w in item.rule_param if str(w).strip()]
        if not words:
            return 1.0, "未配置禁止词"
        joined = "\n".join(t.text for t in agents)
        hits = [w for w in words if w in joined]
        if not hits:
            return 1.0, "未出现禁止词"
        return 0.0, f"出现禁止词：{ '、'.join(hits[:5]) }"

    if rule == "required_opening":
        keywords = item.keywords or []
        if not keywords or not agents:
            return 1.0, "无开场白关键词或无对话"
        first = agents[0].text
        hits = [k for k in keywords if k in first]
        ratio = len(hits) / len(keywords)
        if ratio == 1.0:
            return 1.0, f"开场白命中全部 {len(keywords)} 个关键词"
        return ratio, (
            f"开场白命中 {len(hits)}/{len(keywords)} 关键词"
            + (f"，缺：{ '、'.join([k for k in keywords if k not in hits][:5]) }" if hits else "")
        )

    return 1.0, f"未识别规则：{rule}（默认满分）"
