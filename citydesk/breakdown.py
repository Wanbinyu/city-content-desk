"""把口播拆成开头、中段、结尾。拆解保留原句，供人选结构。"""

import re

from citydesk.compliance import find_risks

_SENTENCE = re.compile(r"[。！？!\n]+")


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(text or "") if part.strip()]


def build_breakdown(transcript: str) -> dict:
    sentences = split_sentences(transcript)
    if not sentences:
        raise ValueError("先贴口播或导入文案，再拆解")
    hook = sentences[0]
    ending = sentences[-1] if len(sentences) > 1 else ""
    middle = sentences[1:-1] if len(sentences) > 2 else sentences[1:]
    points = middle[:3] or sentences[:3]
    structure = "\n".join(
        [
            f"开头：{hook}",
            "中段：" + (" / ".join(points) if points else "（没有单独中段）"),
            f"结尾：{ending or '（没有单独结尾）'}",
        ]
    )
    return {
        "hook": hook,
        "structure": structure,
        "points": "\n".join(f"{index}. {line}" for index, line in enumerate(points, start=1)),
        "cta": ending,
        "risk_words": find_risks(transcript),
    }
