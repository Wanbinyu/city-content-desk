"""本机设置。API key 只留在 data 目录，接口不回传原文。"""

import json
from pathlib import Path

DEFAULTS = {
    "city": "北京",
    "selling_points": "",
    "llm_base_url": "",
    "llm_model": "",
    "llm_api_key": "",
    "sau_account": "",
    "f2_cookie": "",
}

MASK = "******"


def settings_path(db_path: Path) -> Path:
    return db_path.parent / "settings.json"


def load_settings(db_path: Path) -> dict:
    path = settings_path(db_path)
    data = dict(DEFAULTS)
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            for key in DEFAULTS:
                if key in stored and stored[key] is not None:
                    data[key] = str(stored[key])
    return data


def save_settings(db_path: Path, incoming: dict, current: dict) -> dict:
    merged = dict(current)
    for key in DEFAULTS:
        if key not in incoming:
            continue
        value = incoming[key]
        if value is None:
            continue
        text = str(value)
        if key in ("llm_api_key", "f2_cookie") and text == MASK:
            continue
        merged[key] = text
    path = settings_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def public_settings(settings: dict) -> dict:
    shown = dict(settings)
    shown["has_llm_key"] = bool(settings.get("llm_api_key"))
    shown["has_f2_cookie"] = bool(settings.get("f2_cookie"))
    if shown["has_llm_key"]:
        shown["llm_api_key"] = MASK
    if shown["has_f2_cookie"]:
        shown["f2_cookie"] = MASK
    return shown
