"""本地工作台。只监听本机。"""

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from citydesk.db import connect, init_db, seed_samples
from citydesk.service import (
    approve_draft,
    board,
    create_package,
    import_text,
    load_demo,
    make_breakdown,
    make_draft,
    reject_draft,
    revise_draft,
)
from citydesk.jobs import generate_table
from citydesk.settings import load_settings, public_settings, save_settings

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class App:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.lock = threading.Lock()

    def call(self, fn):
        with self.lock:
            conn = connect(self.db_path)
            try:
                init_db(conn)
                result = fn(conn)
                conn.commit()
                return result
            finally:
                conn.close()


class Handler(BaseHTTPRequestHandler):
    app: App
    static_dir: Path

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json({"ok": True})
            return
        if path == "/api/board":
            self._json(self.app.call(board))
            return
        if path == "/api/settings":
            self._json(public_settings(load_settings(self.app.db_path)))
            return
        if path in ("/", "/index.html"):
            self._file(self.static_dir / "index.html")
            return
        if path in ("/app.js", "/app.css"):
            self._file(self.static_dir / path.lstrip("/"))
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path.startswith("/outputs/"):
            self._output(path)
            return
        self._error(404, "没有这个页面")

    def do_POST(self) -> None:
        self._route("POST")

    def do_PUT(self) -> None:
        self._route("PUT")

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        parts = [part for part in path.split("/") if part]
        try:
            if method == "POST" and path == "/api/table":
                body = self._body()
                result = generate_table(body, self.app.db_path, load_settings(self.app.db_path))
                self._json(result)
                return
            if method == "POST" and path == "/api/import":
                body = self._body()
                result = self.app.call(lambda conn: import_text(conn, body.get("text", "")))
                self._json(result)
                return
            if method == "POST" and path == "/api/sample":
                self._json(self.app.call(load_demo))
                return
            if method == "PUT" and path == "/api/settings":
                current = load_settings(self.app.db_path)
                merged = save_settings(self.app.db_path, self._body(), current)
                self._json(public_settings(merged))
                return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "posts":
                post_id = int(parts[2])
                action = parts[3]
                if method == "POST" and action == "transcript":
                    text = self._body().get("transcript", "")
                    self.app.call(lambda conn: _save_transcript(conn, post_id, text))
                    self._json({"ok": True})
                    return
                if method == "POST" and action == "breakdown":
                    self._json(self.app.call(lambda conn: make_breakdown(conn, post_id)))
                    return
                if method == "POST" and action == "draft":
                    city = self._body().get("city", "")
                    self._json(self.app.call(lambda conn: make_draft(conn, post_id, self.app.db_path, city)))
                    return
                if method == "POST" and action == "fetch":
                    self._json(fetch_transcript_outside_lock(self.app, post_id))
                    return
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "drafts":
                draft_id = int(parts[2])
                action = parts[3]
                if method == "PUT" and action == "body":
                    self._json(self.app.call(lambda conn: revise_draft(conn, draft_id, self._body())))
                    return
                if method == "POST" and action == "approve":
                    self._json(self.app.call(lambda conn: approve_draft(conn, draft_id)))
                    return
                if method == "POST" and action == "reject":
                    self._json(self.app.call(lambda conn: reject_draft(conn, draft_id)))
                    return
                if method == "POST" and action == "package":
                    body = self._body()
                    result = self.app.call(
                        lambda conn: create_package(
                            conn,
                            draft_id,
                            self.app.db_path,
                            body.get("account", ""),
                            body.get("video_path", ""),
                            bool(body.get("execute")),
                        )
                    )
                    self._json(result)
                    return
        except ValueError as exc:
            self._error(400, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - 返回给本机页面，避免工作台直接断掉
            self._error(500, f"处理失败：{exc}")
            return
        self._error(404, "没有这个接口")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 2_000_000:
            raise ValueError("内容超过 2MB")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("请求体要是 JSON 对象")
        return data

    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _output(self, path: str) -> None:
        root = (self.app.db_path.parent / "outputs").resolve()
        target = (root / path[len("/outputs/") :]).resolve()
        if target != root and root not in target.parents:
            self._error(404, "没有这个文件")
            return
        self._file(target)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._error(404, "文件不存在")
            return
        raw = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in (".html", ".js", ".css"):
            mime = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}[path.suffix]
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _save_transcript(conn, post_id: int, text: str) -> None:
    from citydesk.db import get_post, save_transcript

    if get_post(conn, post_id) is None:
        raise ValueError("热帖不存在")
    save_transcript(conn, post_id, text)


def fetch_transcript_outside_lock(app: App, post_id: int) -> dict:
    with app.lock:
        conn = connect(app.db_path)
        try:
            init_db(conn)
            from citydesk.db import get_post

            post = get_post(conn, post_id)
            if post is None:
                raise ValueError("热帖不存在")
            if not post["aweme_url"]:
                raise ValueError("这条没有抖音链接")
            url = post["aweme_url"]
            cookie = load_settings(app.db_path).get("f2_cookie", "")
        finally:
            conn.close()
    from citydesk.f2_adapter import run_fetch

    result = run_fetch(url, app.db_path.parent / "f2" / str(post_id), cookie)
    with app.lock:
        conn = connect(app.db_path)
        try:
            from citydesk.db import save_transcript

            save_transcript(conn, post_id, result["transcript"])
            conn.commit()
        finally:
            conn.close()
    return {"transcript": result["transcript"]}


def make_server(db_path: Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    app = App(db_path)
    handler = type("BoundHandler", (Handler,), {"app": app, "static_dir": STATIC})
    server = ThreadingHTTPServer((host, port), handler)
    server.app = app
    return server


def prepare_db(db_path: Path, with_samples: bool = False) -> None:
    conn = connect(db_path)
    try:
        init_db(conn)
        if with_samples:
            count = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
            if count == 0:
                seed_samples(conn)
        conn.commit()
    finally:
        conn.close()
