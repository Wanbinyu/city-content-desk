"""生成一次城市对照表：页面、视频、文案。"""

from datetime import datetime
from pathlib import Path

from citydesk.tablecopy import prepare_copy
from citydesk.video import render_job

ROOT = Path(__file__).resolve().parents[1]


def generate_table(payload: dict, db_path: Path, settings: dict) -> dict:
    data_dir = db_path.parent / "ranks"
    examples_dir = ROOT / "examples" / "ranks"
    prepared = prepare_copy(payload, data_dir, examples_dir, settings)
    if payload.get("preview"):
        return {
            **prepared,
            "preview": True,
            "page_url": "",
            "poster_url": "",
            "video_url": "",
            "video_message": "",
            "folder": "",
        }
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = db_path.parent / "outputs" / job_id
    rendered = render_job(
        job_dir,
        prepared["title"],
        prepared["columns"],
        prepared["rows"],
        prepared["caption"],
        prepared["note"],
    )
    return {
        **prepared,
        "id": job_id,
        "preview": False,
        "page_url": f"/outputs/{job_id}/{rendered['page']}",
        "poster_url": f"/outputs/{job_id}/{rendered['poster']}",
        "video_url": f"/outputs/{job_id}/{rendered['video']}" if rendered["video"] else "",
        "video_message": rendered["video_message"],
        "folder": str(job_dir),
    }
