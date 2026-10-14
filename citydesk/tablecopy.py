"""把一条表格视频的版式换成目标城市。排名只来自用户的表、本地文件或模型整理，不编造机构。"""

import csv
import io
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from citydesk.compliance import find_risks

# 按长度从长到短替换，避免短名先改掉长名的一部分。
TABLE_CITIES = (
    "乌鲁木齐",
    "呼和浩特",
    "石家庄",
    "哈尔滨",
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
    "苏州",
    "青岛",
    "长沙",
    "郑州",
    "天津",
    "宁波",
    "厦门",
    "合肥",
    "昆明",
    "沈阳",
    "大连",
    "济南",
    "福州",
    "无锡",
    "佛山",
    "东莞",
    "长春",
    "南昌",
    "南宁",
    "贵阳",
    "太原",
    "兰州",
    "海口",
    "西宁",
    "银川",
    "拉萨",
    "温州",
    "金华",
    "泉州",
    "烟台",
    "洛阳",
    "珠海",
)

MAX_ROWS = 28
MAX_COLUMNS = 8

_SPLIT = re.compile(r"\s*\|\s*")
_NUMBERED = re.compile(r"^\s*(\d+)\s*[.、．)）:：]\s*(.+)$")
_EDIT = re.compile(r"(?:把|将)\s*(.+?)\s*(?:改成|改为|换成)\s*(.+)")
_ARROW = re.compile(r"^(.+?)\s*(?:->|=>|→)\s*(.+)$")


def clean_city(value: str, default: str = "") -> str:
    text = re.sub(r"\s+", "", value or "")
    if text.endswith("市") and len(text) > 2:
        text = text[:-1]
    return text or default


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _strip_fence(text: str) -> str:
    raw = (text or "").strip().lstrip("\ufeff")
    if not raw.startswith("```"):
        return raw
    lines = raw.splitlines()[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _rows_from_pairs(columns: list[str], body: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    width = len(columns)
    if width < 2 or width > MAX_COLUMNS or any(not column for column in columns):
        raise ValueError("表头需要 2 到 8 列，而且不能有空列名")
    rows = []
    for row in body:
        padded = (row + [""] * width)[:width]
        if any(cell.strip() for cell in padded):
            rows.append([cell.strip() for cell in padded])
    rows = _drop_link_rows(rows)
    if not rows:
        raise ValueError("表格没有数据行")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"一次最多 {MAX_ROWS} 行，请拆开再生成")
    return columns, rows


def _drop_link_rows(rows: list[list[str]]) -> list[list[str]]:
    kept = []
    for row in rows:
        filled = [cell.strip() for cell in row if cell.strip()]
        if len(filled) == 1 and filled[0].startswith(("http://", "https://")):
            continue
        kept.append(row)
    return kept


def _parse_json(text: str) -> tuple[list[str], list[list[str]]]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("rows") or data.get("data") or data.get("table")
    if not isinstance(data, list) or not data:
        raise ValueError("JSON 里没有表格")
    if isinstance(data[0], dict):
        columns = [str(key) for key in data[0].keys()]
        body = [["" if item.get(column) is None else str(item.get(column)) for column in columns] for item in data]
        return _rows_from_pairs(columns, body)
    if isinstance(data[0], list):
        columns = [str(cell) for cell in data[0]]
        body = [["" if cell is None else str(cell) for cell in row] for row in data[1:]]
        return _rows_from_pairs(columns, body)
    raise ValueError("JSON 表格格式不对")


def _split_detail(text: str) -> tuple[str, str]:
    for separator in ("：", ":", "—", "–", " - "):
        if separator in text:
            left, right = text.split(separator, 1)
            return left.strip(), right.strip()
    return text.strip(), ""


def _parse_loose(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    numbered = []
    for line in lines:
        if line.startswith(("http://", "https://")):
            continue
        match = _NUMBERED.match(line)
        if match:
            name, detail = _split_detail(match.group(2))
            numbered.append((match.group(1), name, detail))
    useful = [line for line in lines if not line.startswith(("http://", "https://"))]
    if len(numbered) >= 2 and len(numbered) >= max(1, len(useful) - 3):
        if any(item[2] for item in numbered):
            columns = ["排名", "机构", "参考信息"]
            body = [[rank, name, detail] for rank, name, detail in numbered]
        else:
            columns = ["排名", "内容"]
            body = [[rank, name] for rank, name, _detail in numbered]
        return _rows_from_pairs(columns, body)
    pairs = []
    for line in useful:
        name, detail = _split_detail(line)
        if detail and len(name) <= 24:
            pairs.append((name, detail))
    if len(pairs) >= 2 and len(pairs) == len(useful):
        return _rows_from_pairs(["项目", "内容"], [list(pair) for pair in pairs])
    raise ValueError("没有认出表格。可以贴 CSV，或一行一条：1、机构：说明")


def _parse_delimited(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("表格是空的")
    if lines[0].startswith("|"):
        lines = [line.strip("|") for line in lines if not re.fullmatch(r"[\s|:-]+", line)]
        parsed = [[cell.strip() for cell in _SPLIT.split(line)] for line in lines]
    else:
        sample = "\n".join(lines[:5])
        working = text
        if "，" in sample and "," not in sample:
            working = working.replace("，", ",")
        elif "；" in sample and ";" not in sample and "," not in sample:
            working = working.replace("；", ";")
        sample = "\n".join(line.strip() for line in working.splitlines() if line.strip())
        first = sample.splitlines()[0]
        if "\t" in first:
            delimiter = "\t"
        elif ";" in first and "," not in first:
            delimiter = ";"
        else:
            delimiter = ","
        parsed = [
            [cell.strip() for cell in row]
            for row in csv.reader(io.StringIO(sample), delimiter=delimiter)
            if any(cell.strip() for cell in row)
        ]
    if len(parsed) < 2:
        raise ValueError("表格至少要有表头和一行")
    if len(parsed[0]) < 2:
        raise ValueError("表头需要至少两列")
    return _rows_from_pairs(parsed[0], parsed[1:])


def _limit_error(exc: ValueError) -> bool:
    message = str(exc)
    return "一次最多" in message or "2 到 8 列" in message


def parse_table(text: str) -> tuple[list[str], list[list[str]]]:
    raw = _strip_fence(text)
    if not raw:
        raise ValueError("表格是空的")
    if raw[0] in "[{":
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            pass
        except ValueError as exc:
            if _limit_error(exc):
                raise
        except AttributeError:
            pass
    try:
        return _parse_delimited(raw)
    except ValueError as exc:
        if _limit_error(exc):
            raise
        return _parse_loose([line.strip() for line in raw.splitlines() if line.strip()])


def table_text(columns: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()


def edit_pairs(notes: str) -> list[tuple[str, str]]:
    pairs = []
    for line in (notes or "").splitlines():
        text = line.strip()
        if not text:
            continue
        match = _EDIT.search(text) or _ARROW.match(text)
        if not match:
            continue
        old, new = match.group(1).strip(), match.group(2).strip()
        if len(old) < 2 or not new or old == new:
            continue
        pairs.append((old, new))
    return pairs


def _apply_pairs(value: str, pairs: list[tuple[str, str]]) -> str:
    updated = value
    for old, new in pairs:
        updated = updated.replace(old, new)
    return updated


def _names_to_swap(city: str, from_city: str) -> list[str]:
    names = []
    source = clean_city(from_city)
    if len(source) >= 2 and source != city:
        names.append(source)
    for name in TABLE_CITIES:
        if name != city and name not in names:
            names.append(name)
    names.sort(key=len, reverse=True)
    return names


def swap_text(value: str, city: str, from_city: str = "") -> str:
    updated = value
    for name in _names_to_swap(city, from_city):
        updated = updated.replace(name, city)
    return updated


def rewrite_text(value: str, city: str, from_city: str, pairs: list[tuple[str, str]]) -> str:
    """先换城市。补充说明能改原表里的词，也能改换城之后的词，而且写明的新词不再被换掉。"""
    swapped = swap_text(value, city, from_city)
    replaced = _apply_pairs(swapped, pairs)
    if replaced != swapped:
        return replaced
    original = _apply_pairs(value, pairs)
    if original != value:
        return original
    return swapped


def retitle(title: str, city: str, topic: str, from_city: str = "", pairs: list[tuple[str, str]] | None = None) -> str:
    text = (title or "").strip() or f"{city}{topic}对照表"
    text = rewrite_text(text, city, from_city, pairs or [])
    if city not in text:
        text = f"{city}{text}"
    return text


def caption_for(title: str, city: str, topic: str, columns: list[str], row_count: int, note: str) -> str:
    lines = [
        title,
        f"这条按原表格的版式，整理成{city}{topic}对照表，共 {row_count} 行。",
        "列：" + "、".join(columns) + "。",
        "表里的名称、费用和项目以导入的材料为准。方案因人而异，不承诺效果。",
    ]
    if note:
        lines.append(note)
    return "\n".join(lines)


def script_table(city: str, topic: str, data_dir: Path, examples_dir: Path) -> tuple[list[str], list[list[str]], str]:
    names = [f"{city}-{topic}.csv", f"{city}-{topic}.tsv", f"{city}.csv", f"{city}.tsv"]
    searched = []
    for folder, label in ((data_dir, "你放入的排名文件"), (examples_dir, "示例文件，不是真实排名")):
        for name in names:
            path = folder / name
            searched.append(str(path))
            if path.is_file():
                columns, rows = parse_table(read_text_file(path))
                return columns, rows, f"脚本来源：{label} {path.name}"
    raise ValueError(
        "脚本没有找到排名文件。请把 CSV 放到 data/ranks/"
        f"{city}-{topic}.csv，或改用「我的表格」。已查找："
        + "；".join(searched)
    )


def ai_table(city: str, topic: str, material: str, settings: dict) -> tuple[list[str], list[list[str]], str]:
    material = (material or "").strip()
    if not material:
        raise ValueError("模型模式不会编造机构排名。请先贴上表格或来源内容。")
    base = (settings.get("llm_base_url") or "").strip().rstrip("/")
    model = (settings.get("llm_model") or "").strip()
    key = (settings.get("llm_api_key") or "").strip()
    if not base or not model or not key:
        raise ValueError("还没配置模型。设置里填写地址、模型名和 API key，或改用脚本、我的表格。")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    system = (
        "你把用户给的材料整理成 CSV 对照表。只能使用材料里写明的名称和数字。"
        "材料里没有的机构、价格、名次不要补。城市名改成用户指定的城市。"
        "只输出 CSV，第一行是表头。不要输出解释。"
    )
    user = json.dumps({"city": city, "topic": topic, "material": material[:6000]}, ensure_ascii=False)
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"模型调用失败：{exc}") from exc
    content = body["choices"][0]["message"]["content"]
    columns, rows = parse_table(content)
    return columns, rows, "模型只整理了你贴上的材料，没有补充材料以外的机构。"


def resolve_table(payload: dict, data_dir: Path, examples_dir: Path, settings: dict) -> tuple[list[str], list[list[str]], str]:
    source = (payload.get("source") or "user").strip()
    city = clean_city(payload.get("city") or "", "武汉")
    topic = (payload.get("topic") or "").strip() or "双眼皮"
    pasted = (payload.get("table_text") or "").strip()
    if source == "script":
        try:
            columns, rows, note = script_table(city, topic, data_dir, examples_dir)
        except ValueError:
            if not pasted:
                raise
            columns, rows = parse_table(pasted)
            return columns, rows, "来源：你贴上的表格"
        if not pasted or table_text(columns, rows).strip() == pasted.strip():
            return columns, rows, note
        columns, rows = parse_table(pasted)
        if "不是真实排名" in note:
            return columns, rows, "来源：你改过的表格。内容仍来自示例文件，不是真实排名。"
        return columns, rows, "来源：你改过的表格"
    if source == "ai":
        material = pasted or (payload.get("notes") or "")
        if pasted:
            try:
                columns, rows = parse_table(pasted)
            except ValueError:
                return ai_table(city, topic, material, settings)
            return columns, rows, "来源：你贴上的表格"
        return ai_table(city, topic, material, settings)
    if not pasted:
        raise ValueError("请贴上表格或文案。支持 CSV，也支持一行一条：1、机构：说明。")
    columns, rows = parse_table(pasted)
    return columns, rows, "来源：你贴上的表格"


def prepare_copy(payload: dict, data_dir: Path, examples_dir: Path, settings: dict) -> dict:
    city = clean_city(payload.get("city") or "", "武汉")
    if len(city) < 2:
        raise ValueError("目标城市至少两个字")
    topic = (payload.get("topic") or "").strip() or "双眼皮"
    from_city = clean_city(payload.get("from_city") or "")
    pairs = edit_pairs(payload.get("notes") or "")
    columns, rows, note = resolve_table(payload, data_dir, examples_dir, settings)
    columns = [rewrite_text(column, city, from_city, pairs) for column in columns]
    rows = [[rewrite_text(cell, city, from_city, pairs) for cell in row] for row in rows]
    if pairs:
        note = note + " 已按补充说明替换。"
    title = retitle(payload.get("title") or "", city, topic, from_city, pairs)
    supplied = (payload.get("caption") or "").strip()
    if supplied:
        caption = rewrite_text(supplied, city, from_city, pairs)
    else:
        caption = caption_for(title, city, topic, columns, len(rows), note)
    risks = find_risks("\n".join([title, caption, table_text(columns, rows)]))
    return {
        "title": title,
        "city": city,
        "topic": topic,
        "columns": columns,
        "rows": rows,
        "table_text": table_text(columns, rows),
        "note": note,
        "caption": caption,
        "risks": risks,
        "url": payload.get("url") or "",
    }
