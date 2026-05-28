"""效率评分与模拟的可调参数。"""

FILLER_PATTERNS = [
    r"^好的[，。]?$",
    r"^明白了?[，。]?$",
    r"^收到[，。]?$",
    r"^嗯+[，。]?$",
    r"^没问题[，。]?$",
    r"^稍等[一下]?[，。]?$",
]

FILLER_MAX_LEN = 10

RULE_REPEAT_THRESHOLD = 0.8
EFFICIENCY_REPEAT_THRESHOLD = 0.85
CIRCULAR_THRESHOLD = 0.80

EFFICIENCY_TASK_FLOOR = 0.5

SIMULATION_SAFETY_MAX = 25
