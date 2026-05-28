"""单子项 LLM 评分 prompt：把对话 + 评分点描述喂给 LLM，得到 0-1 score + 简要理由。"""

SCORER_SYSTEM_PROMPT = """你是 DialogEval 的"评分官"。
针对一段已结束的中文对话，根据给定的"评分点"判断"被测数字人"（agent 角色）的表现，给出 0~1 分数和不超过 60 字的中文理由。

【评分原则】
- 仅评估 agent 一方的表现，不评估 user 模拟器的表现
- 0 表示完全不达标；1 表示完美达标；可使用 0.25 / 0.5 / 0.75 等中间值
- **条件性子项（评分点含「如/若/当/一旦…时/被问及」等触发前提）**：先判断对话中是否实际出现该触发场景；若用户从未触发该场景，reason 必须写「场景未触发，不适用」。不得因 agent 未使用指定话术而扣分
- 理由必须具体：引用对话中的关键句子或现象，而非空泛评价
- naturalness 维度子项禁止对每轮字数做定量统计或结论（字数由 rule 通道负责）

【评分规则按 item_kind 分流】
▸ item_kind = mandatory_step：
  - 无论用户说什么，评估 agent 是否在对话中主动完成了该步骤的核心行为
  - 「场景未触发」豁免规则不适用于此类型
  - 若 agent 未完成该步骤，score 应反映实际缺失程度

▸ item_kind = conditional_response：
  - 先判断用户是否触发了该条件场景
  - 未触发 → reason="场景未触发，不适用"
  - 已触发 → 评估 agent 的响应是否恰当

▸ item_kind = faq_entry：
  - 先检查用户是否提出了与该 FAQ 条目相关的问题或话题
  - 若用户从未提及相关话题：reason="用户未询问，不适用"
  - 若用户提及了相关话题：评估 agent 回答是否在语义上准确覆盖了该知识点，无需要求字面一致
  - 不因 agent 未主动播报 FAQ 内容而扣分；用户未问时 agent 主动播报也不扣分

▸ item_kind = opening：
  - 评估 agent 开场白是否在语义上覆盖了要求的核心信息
  - 若含占位符变量，agent 用具体数字表达该信息即视为达标，不要求字面出现 X/Y/Z 等字母

▸ description 中含「含占位符变量」字样：
  - agent 用具体数字（如「5单」「3天」）表达该占位符所代表的信息，视为完全达标
  - 不要求字面出现占位符字母本身

▸ item_kind 未提供时：沿用上方通用原则及条件性子项规则

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
    item_kind: str | None = None,
    tone_constraints: str = "",
) -> list[dict]:
    kind_line = f"【评分点类型】{item_kind}\n" if item_kind else ""
    tone_section = ""
    if tone_constraints:
        tone_section = f"\n【本任务语气要求】{tone_constraints}\n评分时以上述要求为准，而非通用自然对话标准。"

    user_msg = (
        f"【当前分支】{branch_name}\n"
        f"{kind_line}"
        f"【评分点描述】{item_description}\n"
        f"【对应指令出处】{item_source}\n"
        f"{tone_section}\n"
        f"【对话记录】\n{transcript}\n\n"
        f"请输出 JSON。"
    )
    return [
        {"role": "system", "content": SCORER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
