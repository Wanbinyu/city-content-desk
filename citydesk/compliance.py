"""医疗广告口径拦截。只拦明确的承诺和绝对化用语。"""

RISK_PHRASES = (
    "最好",
    "最佳",
    "第一",
    "唯一",
    "保证",
    "包成功",
    "包过",
    "无痛",
    "零风险",
    "永久",
    "100%",
    "百分百",
    "根治",
    "无副作用",
    "绝对安全",
    "国家级",
    "全网最",
    "最强",
    "最自然",
)


def find_risks(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for phrase in RISK_PHRASES:
        if phrase in text and phrase not in found:
            found.append(phrase)
    return found
