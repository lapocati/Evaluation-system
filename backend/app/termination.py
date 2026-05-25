"""结束检测：关键词预筛 + 命中后用 LLM 二次确认。

预筛在毫秒级；只有命中关键词才会触发一次 LLM 调用，节省 token。
"""
from app.llm.deepseek import DeepSeekError, chat

TERMINATION_KEYWORDS: tuple[str, ...] = (
    "再见",
    "拜拜",
    "挂断",
    "挂了",
    "辛苦了",
    "感谢配合",
    "我先挂",
    "回头联系",
    "就这样吧",
    "晚安",
    "不打扰",
)


def keyword_pre_screen(text: str) -> bool:
    return any(k in text for k in TERMINATION_KEYWORDS)


_CONFIRM_SYSTEM = (
    "你判断一段对话片段的最后一句，是否是「明确的挂断告别」——"
    "即对话双方任何一方都在主动结束通话，而不是单纯感谢、寒暄、或承诺后续联系。"
    "仅回答一个汉字：是 或 否。不要解释、不要标点。"
)


async def llm_confirm_end(history_tail: str, api_key: str) -> bool:
    """对最后 2-3 轮做语义二次确认。失败时保守返回 False，让对话继续。"""
    try:
        out = await chat(
            [
                {"role": "system", "content": _CONFIRM_SYSTEM},
                {"role": "user", "content": history_tail},
            ],
            api_key,
            temperature=0.0,
            timeout=30.0,
        )
    except DeepSeekError:
        return False
    return out.strip().startswith("是")
