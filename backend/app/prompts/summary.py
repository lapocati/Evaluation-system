"""报告 summary：根据五维度结果生成"优势/改进"列表。"""
import json

SUMMARY_SYSTEM_PROMPT = """你是 DialogEval 的报告撰写助手。
根据给定的多维度评分结果，输出该分支的"优势"和"改进建议"清单，要求：

【输出严格要求】
仅输出 JSON：
{"advantages": ["...", "..."], "improvements": ["...", "..."]}
- advantages: 2~4 条，挑选高分维度/子项总结亮点
- improvements: 2~4 条，挑选低分维度/子项给出具体改进方向
- 每条 ≤ 35 字，中文，可读性强，避免空话
- 不要 markdown、不要前后文"""


def build_summary_messages(
    *,
    branch_name: str,
    dimensions_payload: dict,
    efficiency_payload: dict,
) -> list[dict]:
    user_msg = (
        f"【分支】{branch_name}\n\n"
        f"【维度评分】\n{json.dumps(dimensions_payload, ensure_ascii=False, indent=2)}\n\n"
        f"【效率评分】\n{json.dumps(efficiency_payload, ensure_ascii=False)}\n\n"
        f"请输出 JSON。"
    )
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
