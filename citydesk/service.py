"""把导入、拆解、改写、人审和发布包串成一步一步的操作。"""

from pathlib import Path

from citydesk.breakdown import build_breakdown
from citydesk.compliance import find_risks
from citydesk.db import (
    get_breakdown,
    get_draft,
    get_post,
    insert_draft,
    insert_job,
    list_board,
    save_breakdown,
    seed_samples,
    set_draft_status,
    update_draft,
    upsert_post,
)
from citydesk.importer import parse_import
from citydesk.publish import execute_upload, write_package
from citydesk.rewrite import build_draft, detect_city
from citydesk.settings import load_settings


def import_text(conn, text: str) -> dict:
    records = parse_import(text)
    added = 0
    for record in records:
        added += upsert_post(conn, record)
    return {"imported": len(records), "added": added}


def make_breakdown(conn, post_id: int) -> dict:
    post = get_post(conn, post_id)
    if post is None:
        raise ValueError("热帖不存在")
    breakdown = build_breakdown(post["transcript"])
    save_breakdown(conn, post_id, breakdown)
    return breakdown


def make_draft(conn, post_id: int, db_path: Path, city: str = "") -> dict:
    post = get_post(conn, post_id)
    if post is None:
        raise ValueError("热帖不存在")
    breakdown = get_breakdown(conn, post_id)
    if breakdown is None:
        raise ValueError("先拆解，再写复刻稿")
    settings = load_settings(db_path)
    chosen = detect_city(city, post["keyword"], post["title"], fallback=settings["city"])
    draft = build_draft(
        post["transcript"],
        breakdown,
        chosen,
        settings["selling_points"],
        settings,
    )
    draft_id = insert_draft(conn, post_id, draft)
    draft["id"] = draft_id
    return draft


def revise_draft(conn, draft_id: int, fields: dict) -> dict:
    current = get_draft(conn, draft_id)
    if current is None:
        raise ValueError("稿不存在")
    merged = {
        "title": fields.get("title", current["title"]),
        "script": fields.get("script", current["script"]),
        "shots": fields.get("shots", current["shots"]),
        "cover_text": fields.get("cover_text", current["cover_text"]),
        "tags": fields.get("tags", current["tags"]),
    }
    risks = find_risks("\n".join(merged.values()))
    update_draft(conn, draft_id, merged, risks)
    merged["id"] = draft_id
    merged["risk_words"] = risks
    merged["status"] = "draft"
    return merged


def approve_draft(conn, draft_id: int) -> dict:
    draft = get_draft(conn, draft_id)
    if draft is None:
        raise ValueError("稿不存在")
    risks = find_risks("\n".join([draft["title"], draft["script"], draft["cover_text"], draft["tags"]]))
    if risks:
        raise ValueError("稿里还有风险词，改掉后再通过：" + "、".join(risks))
    set_draft_status(conn, draft_id, "approved", "approved")
    return {"id": draft_id, "status": "approved"}


def reject_draft(conn, draft_id: int) -> dict:
    set_draft_status(conn, draft_id, "rejected", "broken")
    return {"id": draft_id, "status": "rejected"}


def create_package(conn, draft_id: int, db_path: Path, account: str, video_path: str, execute: bool) -> dict:
    draft = get_draft(conn, draft_id)
    if draft is None:
        raise ValueError("稿不存在")
    if draft["status"] != "approved":
        raise ValueError("先通过这篇稿，再生成发布包")
    risks = find_risks("\n".join([draft["title"], draft["script"], draft["cover_text"]]))
    if risks:
        raise ValueError("稿里还有风险词：" + "、".join(risks))
    settings = load_settings(db_path)
    account = (account or settings.get("sau_account") or "").strip()
    video_path = (video_path or "").strip()
    folder = db_path.parent / "publish" / str(draft_id)
    written = write_package(folder, draft, account, video_path)
    executed = False
    message = "发布包已生成，未执行上传。"
    if execute:
        if not video_path or not Path(video_path).is_file():
            message = "没有找到成片文件，未执行上传。发布包已留下。"
        else:
            executed, message = _run_saved_command(account, video_path, draft, folder)
    job_id = insert_job(
        conn,
        draft_id,
        {
            "account": account,
            "video_path": video_path,
            "package_dir": written["package_dir"],
            "command": written["command"],
            "executed": executed,
            "message": message,
        },
    )
    return {
        "job_id": job_id,
        "package_dir": written["package_dir"],
        "command": written["command"],
        "executed": executed,
        "message": message,
    }


def _run_saved_command(account: str, video_path: str, draft: dict, folder: Path) -> tuple[bool, str]:
    desc_file = (folder / "script.txt").read_text(encoding="utf-8").strip()
    tags = (folder / "tags.txt").read_text(encoding="utf-8")
    tag_line = " ".join(f"#{item.strip()}" for item in tags.replace("，", ",").split(",") if item.strip())
    desc = desc_file if not tag_line else f"{desc_file}\n{tag_line}"
    args = [
        "sau",
        "douyin",
        "upload-video",
        "--account",
        account or "账号名",
        "--file",
        video_path,
        "--title",
        draft["title"].strip()[:55],
        "--desc",
        desc[:500],
    ]
    return execute_upload(args)


def board(conn) -> dict:
    return {"posts": list_board(conn)}


def load_demo(conn) -> dict:
    return {"added": seed_samples(conn)}
