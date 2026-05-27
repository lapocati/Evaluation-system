"""单子项 LLM 评分 prompt：把对话 + 评分点描述喂给 LLM，得到 0-1 score + 简要理由。"""

SCORER_SYSTEM_PROMPT = """你是 DialogEval 的"评分官"。
针对一段已结束的中文对话，根据给定的"评分点"判断"被测数字人"（agent 角色）的表现，给出 0~1 分数和不超过 60 字的中文理由。

【评分原则】
- 仅评估 agent 一方的表现，不评估 user 模拟器的表现
- 0 表示完全不达标；1 表示完美达标；可使用 0.25 / 0.5 / 0.75 等中间值
- **条件性子项（评分点含「如/若/当/一旦…时/被问及」等触发前提）**：先判断对话中是否实际出现该触发场景；若用户从未触发该场景，必须 score=1.0，reason 写「场景未触发，不适用」。不得因 agent 未使用指定话术而扣分
- 理由必须具体：引用对话中的关键句子或现象，而非空泛评价

【输出严格要求】
仅输出一个 JSON 对象：
{"score": 0.0~1.0 的小数, "reason": "中文 ≤60 字"}
不要任何前后文、不要 markdown、不要解释。"""


def build_scorer_messages(
    *,
    item_description: str,
    item_source: str,
    branch_name: str,
    transcript: str,
) -> list[dict]:
    user_msg = (
        f"【当前分支】{branch_name}\n"
        f"【评分点描述】{item_description}\n"
        f"【对应指令出处】{item_source}\n\n"
        f"【对话记录】\n{transcript}\n\n"
        f"请输出 JSON。"
    )
    return [
        {"role": "system", "content": SCORER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
