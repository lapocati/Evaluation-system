"""报告 summary：根据五维度结果生成"优势/改进"列表。"""

import json



SUMMARY_SYSTEM_PROMPT = """你是 DialogEval 的报告撰写助手。

根据给定的多维度评分明细（含每个子项的 score、reason、item_kind），输出该分支的"优势"和"改进建议"清单。



【撰写原则】

- 必须基于明细中的 score/reason/item_kind 撰写，不得自行臆测或分析对话内容

- advantages：优先挑选 score >= 0.8 的子项，总结其体现的能力亮点

- improvements：优先挑选 score < 0.6 的子项，给出对应改进方向

- 每条建议必须能对应到具体评分点，不要泛泛而谈

- 若某维度所有 applicable 子项 score 均 >= 0.8，不必为该维度写改进建议



【输出严格要求】

仅输出 JSON：

{"advantages": ["...", "..."], "improvements": ["...", "..."]}

- advantages: 2~4 条

- improvements: 2~4 条

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

        f"【维度评分明细】\n{json.dumps(dimensions_payload, ensure_ascii=False, indent=2)}\n\n"

        f"【效率评分】\n{json.dumps(efficiency_payload, ensure_ascii=False)}\n\n"

        f"请输出 JSON。"

    )

    return [

        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},

        {"role": "user", "content": user_msg},

    ]

