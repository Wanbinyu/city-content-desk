"""导入表格、MediaCrawler 导出的 JSON，或一行一个抖音链接。"""

import csv
import hashlib
import io
import json
import re

_URL = re.compile(r"https?://[^\s，,；;]+", re.IGNORECASE)
_VIDEO_ID = re.compile(r"/video/(\d+)")

_ALIASES = {
    "aweme_id": "aweme_id",
    "作品id": "aweme_id",
    "id": "aweme_id",
    "title": "title",
    "标题": "title",
    "desc": "desc",
    "nickname": "author",
    "作者": "author",
    "liked_count": "liked_count",
    "digg_count": "liked_count",
    "点赞": "liked_count",
    "comment_count": "comment_count",
    "评论": "comment_count",
    "share_count": "share_count",
    "分享": "share_count",
    "aweme_url": "aweme_url",
    "链接": "aweme_url",
    "url": "aweme_url",
    "source_keyword": "keyword",
    "关键词": "keyword",
    "keyword": "keyword",
    "transcript": "transcript",
    "口播": "transcript",
    "文案": "transcript",
}


def _blank() -> dict:
    return {
        "aweme_id": "",
        "title": "",
        "author": "",
        "liked_count": 0,
        "comment_count": 0,
        "share_count": 0,
        "aweme_url": "",
        "keyword": "",
        "transcript": "",
        "source": "导入",
    }


def _count(value) -> int:
    if value is None or value == "":
        return 0
    text = str(value).replace(",", "").strip()
    try:
        return max(0, int(float(text)))
    except ValueError:
        return 0


def _aweme_id(url: str, title: str) -> str:
    match = _VIDEO_ID.search(url or "")
    if match:
        return match.group(1)
    seed = url or title or "empty"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def normalize_record(raw: dict, source: str = "导入") -> dict:
    item = _blank()
    item["source"] = source
    desc = ""
    for key, value in raw.items():
        if value is None:
            continue
        field = _ALIASES.get(str(key).strip().lower())
        if field is None:
            field = _ALIASES.get(str(key).strip())
        if field is None:
            continue
        if field in ("liked_count", "comment_count", "share_count"):
            item[field] = _count(value)
        elif field == "desc":
            desc = str(value).strip()
        else:
            item[field] = str(value).strip()
    if not item["title"]:
        item["title"] = desc
    if not item["aweme_url"] and item["aweme_id"].isdigit():
        item["aweme_url"] = f"https://www.douyin.com/video/{item['aweme_id']}"
    if not item["title"]:
        item["title"] = item["aweme_url"] or "未命名"
    item["aweme_id"] = item["aweme_id"] or _aweme_id(item["aweme_url"], item["title"])
    return item


def _parse_json(text: str) -> list[dict]:
    if text.startswith("{") and "\n{" in text:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    else:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ("data", "items", "awemes", "contents"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]
        if not isinstance(data, list):
            raise ValueError("JSON 里没有作品列表")
        rows = data
    return [normalize_record(row) for row in rows if isinstance(row, dict)]


def _parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("表格没有表头")
    return [normalize_record(row) for row in reader]


def _parse_links(text: str) -> list[dict]:
    urls = []
    for match in _URL.findall(text):
        url = match.rstrip(").]）】\"'")
        if "douyin.com" not in url and "iesdouyin.com" not in url:
            continue
        if url not in urls:
            urls.append(url)
    if not urls:
        raise ValueError("没有找到抖音链接")
    rows = []
    for url in urls:
        rows.append(
            normalize_record(
                {
                    "aweme_url": url,
                    "title": "待补充标题",
                    "source_keyword": "",
                }
            )
        )
    return rows


def parse_import(text: str) -> list[dict]:
    raw = (text or "").strip().lstrip("\ufeff")
    if not raw:
        raise ValueError("导入内容是空的")
    if raw[0] in "[{":
        return _parse_json(raw)
    first = raw.splitlines()[0]
    if "http" in raw and "," not in first and "\t" not in first and "标题" not in first:
        return _parse_links(raw)
    try:
        rows = _parse_csv(raw)
    except (csv.Error, ValueError):
        rows = []
    if rows:
        return rows
    if "http" in raw:
        return _parse_links(raw)
    raise ValueError("无法识别。请贴 JSON、带表头的 CSV，或抖音链接")
