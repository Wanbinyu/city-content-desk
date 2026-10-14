"""按结构重写口播。规则稿不复述原片原句。"""

import json
import urllib.error
import urllib.request

from citydesk.compliance import find_risks

CITIES = (
    "北京",
    "上海",
    "深圳",
    "广州",
    "杭州",
    "成都",
    "重庆",
    "武汉",
    "南京",
    "西安",
)


def detect_city(*texts: str, fallback: str = "北京") -> str:
    blob = "\n".join(text or "" for text in texts)
    for city in CITIES:
        if city in blob:
            return city
    cleaned = (fallback or "").strip()
    return cleaned or "北京"


def overlaps_source(script: str, transcript: str, window: int = 16) -> bool:
    source = "".join((transcript or "").split())
    draft = "".join((script or "").split())
    if len(source) < window or not draft:
        return False
    for index in range(0, len(source) - window + 1):
        if source[index : index + window] in draft:
            return True
    return False


def rule_draft(city: str, selling_points: str) -> dict:
    points = (selling_points or "").strip()
    risks = find_risks(points)
    note = ""
    point_line = ""
    if points and not risks:
        point_line = f"\n机构已确认可对外说明的信息：{points}"
    elif risks:
        note = "机构卖点里有风险词，未写进口播：" + "、".join(risks)
    script = (
        f"{city}准备了解双眼皮的人，可以先把三件事问清楚。\n"
        "1. 适合哪种方式，要看本人条件，不能只对照别人的成片。\n"
        "2. 恢复过程和复查安排，以面诊时的说明为准。\n"
        "3. 费用包含哪些项目，当场核对清楚。"
        f"{point_line}\n"
        "具体方案因人而异。这条只整理面诊前要问的问题。"
    )
    return {
        "city": city,
        "title": f"{city}双眼皮，面诊前先问这3件事",
        "script": script,
        "shots": "\n".join(
            [
                "1. 城市口播开头，字幕写出三件事",
                "2. 三条问题各停一拍，不放别人的案例对比",
                "3. 结尾口播：方案因人而异，鼓励把问题带到面诊",
            ]
        ),
        "cover_text": f"{city}双眼皮｜面诊前3问",
        "tags": f"{city}双眼皮,双眼皮面诊,医美科普",
        "engine": "rule",
        "note": note,
        "risk_words": find_risks(script),
    }


def _parse_llm_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("大模型没有返回 JSON")
    data = json.loads(text[start : end + 1])
    required = ("title", "script", "shots", "cover_text", "tags")
    if any(not str(data.get(key, "")).strip() for key in required):
        raise ValueError("大模型 JSON 缺少字段")
    return {key: str(data[key]).strip() for key in required}


def llm_draft(city: str, transcript: str, breakdown: dict, selling_points: str, settings: dict) -> dict | None:
    base = (settings.get("llm_base_url") or "").strip().rstrip("/")
    model = (settings.get("llm_model") or "").strip()
    key = (settings.get("llm_api_key") or "").strip()
    if not base or not model or not key:
        return None
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    system = (
        "你是医美内容编辑。根据热帖结构写一条新的口播，给机构自己的账号用。"
        "不要复述原片里连续的原句，不要承诺效果，不要使用绝对化用语。"
        "只输出 JSON，字段为 title, script, shots, cover_text, tags。"
    )
    user = json.dumps(
        {
            "city": city,
            "structure": breakdown.get("structure", ""),
            "source_excerpt_for_structure_only": transcript[:800],
            "selling_points": selling_points,
        },
        ensure_ascii=False,
    )
    payload = {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"大模型调用失败：{exc}") from exc
    content = body["choices"][0]["message"]["content"]
    parsed = _parse_llm_json(content)
    script = parsed["script"]
    risks = find_risks("\n".join(parsed.values()))
    if risks or overlaps_source(script, transcript):
        return None
    return {
        "city": city,
        "title": parsed["title"][:55],
        "script": script,
        "shots": parsed["shots"],
        "cover_text": parsed["cover_text"][:40],
        "tags": parsed["tags"],
        "engine": "llm",
        "note": "",
        "risk_words": [],
    }


def build_draft(transcript: str, breakdown: dict, city: str, selling_points: str, settings: dict | None = None) -> dict:
    settings = settings or {}
    note = ""
    draft = None
    if (settings.get("llm_api_key") or "").strip():
        try:
            draft = llm_draft(city, transcript, breakdown, selling_points, settings)
            if draft is None:
                note = "大模型稿含风险词或贴近原句，已改用规则稿。"
        except ValueError as exc:
            note = str(exc) + " 已改用规则稿。"
    if draft is None:
        draft = rule_draft(city, selling_points)
        if note:
            draft["note"] = (note + " " + draft["note"]).strip()
    draft["risk_words"] = find_risks(
        "\n".join([draft["title"], draft["script"], draft["cover_text"], draft["tags"]])
    )
    return draft
