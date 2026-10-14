"""SQLite 里的热帖、拆解、稿和发布包记录。"""

import sqlite3
from datetime import datetime
from pathlib import Path

from citydesk.sample import SAMPLES


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            aweme_id TEXT NOT NULL UNIQUE,
            keyword TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            author TEXT NOT NULL DEFAULT '',
            liked_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            share_count INTEGER NOT NULL DEFAULT 0,
            aweme_url TEXT NOT NULL DEFAULT '',
            transcript TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'inbox',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS breakdowns (
            post_id INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
            hook TEXT NOT NULL,
            structure TEXT NOT NULL,
            points TEXT NOT NULL,
            cta TEXT NOT NULL,
            risk_words TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            city TEXT NOT NULL,
            title TEXT NOT NULL,
            script TEXT NOT NULL,
            shots TEXT NOT NULL,
            cover_text TEXT NOT NULL,
            tags TEXT NOT NULL,
            risk_words TEXT NOT NULL DEFAULT '',
            engine TEXT NOT NULL DEFAULT 'rule',
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
            account TEXT NOT NULL DEFAULT '',
            video_path TEXT NOT NULL DEFAULT '',
            package_dir TEXT NOT NULL,
            command TEXT NOT NULL,
            executed INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )


def _join_risks(words: list[str] | str) -> str:
    if isinstance(words, str):
        return words
    return ",".join(words)


def seed_samples(conn: sqlite3.Connection) -> int:
    added = 0
    for sample in SAMPLES:
        added += upsert_post(conn, sample)
    return added


def upsert_post(conn: sqlite3.Connection, record: dict) -> int:
    stamp = now()
    existing = conn.execute(
        "SELECT id, transcript, status, keyword, title, author, aweme_url FROM posts WHERE aweme_id = ?",
        (record["aweme_id"],),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO posts (
                aweme_id, keyword, title, author, liked_count, comment_count,
                share_count, aweme_url, transcript, source, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbox', ?, ?)
            """,
            (
                record["aweme_id"],
                record.get("keyword", ""),
                record.get("title") or "未命名",
                record.get("author", ""),
                int(record.get("liked_count") or 0),
                int(record.get("comment_count") or 0),
                int(record.get("share_count") or 0),
                record.get("aweme_url", ""),
                record.get("transcript", ""),
                record.get("source", "导入"),
                stamp,
                stamp,
            ),
        )
        return 1
    transcript = record.get("transcript") or existing["transcript"]
    title = record.get("title") or existing["title"]
    if title == "待补充标题":
        title = existing["title"]
    conn.execute(
        """
        UPDATE posts SET
            keyword = ?, title = ?, author = ?, liked_count = ?, comment_count = ?,
            share_count = ?, aweme_url = ?, transcript = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            record.get("keyword") or existing["keyword"],
            title,
            record.get("author") or existing["author"],
            int(record.get("liked_count") or 0),
            int(record.get("comment_count") or 0),
            int(record.get("share_count") or 0),
            record.get("aweme_url") or existing["aweme_url"],
            transcript,
            stamp,
            existing["id"],
        ),
    )
    return 0


def list_board(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            p.*,
            b.hook, b.structure, b.points, b.cta,
            b.risk_words AS breakdown_risks,
            d.id AS draft_id, d.city AS draft_city, d.title AS draft_title,
            d.script AS draft_script, d.shots AS draft_shots,
            d.cover_text AS draft_cover, d.tags AS draft_tags,
            d.risk_words AS draft_risks, d.engine AS draft_engine,
            d.note AS draft_note, d.status AS draft_status
        FROM posts p
        LEFT JOIN breakdowns b ON b.post_id = p.id
        LEFT JOIN drafts d ON d.id = (
            SELECT id FROM drafts WHERE post_id = p.id ORDER BY id DESC LIMIT 1
        )
        ORDER BY p.liked_count DESC, p.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_post(conn: sqlite3.Connection, post_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return dict(row) if row else None


def save_transcript(conn: sqlite3.Connection, post_id: int, transcript: str) -> None:
    conn.execute(
        "UPDATE posts SET transcript = ?, updated_at = ? WHERE id = ?",
        (transcript.strip(), now(), post_id),
    )


def save_breakdown(conn: sqlite3.Connection, post_id: int, breakdown: dict) -> None:
    stamp = now()
    conn.execute(
        """
        INSERT INTO breakdowns (post_id, hook, structure, points, cta, risk_words, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(post_id) DO UPDATE SET
            hook = excluded.hook,
            structure = excluded.structure,
            points = excluded.points,
            cta = excluded.cta,
            risk_words = excluded.risk_words,
            updated_at = excluded.updated_at
        """,
        (
            post_id,
            breakdown["hook"],
            breakdown["structure"],
            breakdown["points"],
            breakdown["cta"],
            _join_risks(breakdown["risk_words"]),
            stamp,
        ),
    )
    conn.execute(
        "UPDATE posts SET status = 'broken', updated_at = ? WHERE id = ?",
        (stamp, post_id),
    )


def get_breakdown(conn: sqlite3.Connection, post_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM breakdowns WHERE post_id = ?", (post_id,)).fetchone()
    return dict(row) if row else None


def insert_draft(conn: sqlite3.Connection, post_id: int, draft: dict) -> int:
    stamp = now()
    cursor = conn.execute(
        """
        INSERT INTO drafts (
            post_id, city, title, script, shots, cover_text, tags,
            risk_words, engine, note, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
        """,
        (
            post_id,
            draft["city"],
            draft["title"],
            draft["script"],
            draft["shots"],
            draft["cover_text"],
            draft["tags"],
            _join_risks(draft["risk_words"]),
            draft.get("engine", "rule"),
            draft.get("note", ""),
            stamp,
        ),
    )
    conn.execute(
        "UPDATE posts SET status = 'drafted', updated_at = ? WHERE id = ?",
        (stamp, post_id),
    )
    return int(cursor.lastrowid)


def get_draft(conn: sqlite3.Connection, draft_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    return dict(row) if row else None


def update_draft(conn: sqlite3.Connection, draft_id: int, fields: dict, risks: list[str]) -> None:
    current = get_draft(conn, draft_id)
    if current is None:
        raise ValueError("稿不存在")
    conn.execute(
        """
        UPDATE drafts SET
            title = ?, script = ?, shots = ?, cover_text = ?, tags = ?,
            risk_words = ?, status = 'draft'
        WHERE id = ?
        """,
        (
            fields.get("title", current["title"]),
            fields.get("script", current["script"]),
            fields.get("shots", current["shots"]),
            fields.get("cover_text", current["cover_text"]),
            fields.get("tags", current["tags"]),
            _join_risks(risks),
            draft_id,
        ),
    )
    conn.execute(
        "UPDATE posts SET status = 'drafted', updated_at = ? WHERE id = ?",
        (now(), current["post_id"]),
    )


def set_draft_status(conn: sqlite3.Connection, draft_id: int, status: str, post_status: str) -> dict:
    draft = get_draft(conn, draft_id)
    if draft is None:
        raise ValueError("稿不存在")
    conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))
    conn.execute(
        "UPDATE posts SET status = ?, updated_at = ? WHERE id = ?",
        (post_status, now(), draft["post_id"]),
    )
    draft["status"] = status
    return draft


def insert_job(conn: sqlite3.Connection, draft_id: int, job: dict) -> int:
    cursor = conn.execute(
        """
        INSERT INTO jobs (
            draft_id, account, video_path, package_dir, command,
            executed, message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            job.get("account", ""),
            job.get("video_path", ""),
            job["package_dir"],
            job["command"],
            1 if job.get("executed") else 0,
            job.get("message", ""),
            now(),
        ),
    )
    draft = get_draft(conn, draft_id)
    conn.execute(
        "UPDATE posts SET status = 'queued', updated_at = ? WHERE id = ?",
        (now(), draft["post_id"]),
    )
    return int(cursor.lastrowid)
