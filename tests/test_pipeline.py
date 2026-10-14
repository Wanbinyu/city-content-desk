import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from citydesk.f2_adapter import build_command, read_desc
from citydesk.importer import parse_import
from citydesk.publish import build_command as publish_command
from citydesk.rewrite import overlaps_source, rule_draft
from citydesk.server import make_server, prepare_db
from citydesk.service import approve_draft
from citydesk.db import connect, get_draft, init_db, insert_draft


ROOT = Path(__file__).resolve().parents[1]


def request(base, path, method="GET", body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class ImportTest(unittest.TestCase):
    def test_mediacrawler_json(self):
        rows = parse_import(
            json.dumps(
                [
                    {
                        "aweme_id": "123",
                        "title": "深圳双眼皮记录",
                        "nickname": "测",
                        "liked_count": "1200",
                        "comment_count": "30",
                        "share_count": "4",
                        "aweme_url": "https://www.douyin.com/video/123",
                        "source_keyword": "深圳双眼皮",
                    }
                ],
                ensure_ascii=False,
            )
        )
        self.assertEqual(rows[0]["liked_count"], 1200)
        self.assertEqual(rows[0]["keyword"], "深圳双眼皮")

    def test_csv_and_link(self):
        rows = parse_import(
            "标题,点赞,链接,关键词,口播\n上海记录,8,https://www.douyin.com/video/77,上海双眼皮,上海口播一句。\n"
        )
        self.assertEqual(rows[0]["aweme_id"], "77")
        links = parse_import("打开抖音 https://v.douyin.com/abc123/ 看看")
        self.assertEqual(links[0]["title"], "待补充标题")
        self.assertIn("douyin.com", links[0]["aweme_url"])


class DraftSafetyTest(unittest.TestCase):
    def test_rule_draft_does_not_copy_source_or_risk_words(self):
        transcript = (
            "很多在北京看双眼皮的人，会先拿别人的成片来对自己的眼睛。"
            "上海有些帖子开头写无痛，这句话不能直接拿来用。"
        )
        draft = rule_draft("北京", "无痛速成，保证效果")
        self.assertNotIn("无痛", draft["script"])
        self.assertNotIn("保证", draft["script"])
        self.assertFalse(overlaps_source(draft["script"], transcript))
        self.assertIn("未写进口播", draft["note"])
        self.assertEqual(draft["risk_words"], [])


class AdapterTest(unittest.TestCase):
    def test_f2_command_and_desc_file(self):
        command = build_command("https://v.douyin.com/abc/", Path("out"), "")
        self.assertEqual(command[:4], ["f2", "douyin", "-u", "https://v.douyin.com/abc/"])
        self.assertNotIn("-k", command)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "2020_标题_desc.txt"
            path.write_text("口播正文", encoding="utf-8")
            self.assertEqual(read_desc(Path(folder)), "口播正文")

    def test_publish_command_quotes_title(self):
        command = publish_command("诊所号", r"G:\片.mp4", "北京双眼皮，面诊前先问这3件事", "正文")
        self.assertIn("sau", command)
        self.assertIn("upload-video", command)
        self.assertIn("诊所号", command)
        self.assertIn("面诊前先问这3件事", command)


class HttpFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "citydesk.db"
        prepare_db(self.db, with_samples=True)
        self.server = make_server(self.db, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_page_and_full_flow(self):
        with urllib.request.urlopen(self.base + "/") as response:
            html = response.read().decode("utf-8")
        self.assertIn("城市内容台", html)
        self.assertIn("拆解", (ROOT / "static" / "app.js").read_text(encoding="utf-8"))

        status, board = request(self.base, "/api/board")
        self.assertEqual(status, 200)
        post = next(item for item in board["posts"] if item["aweme_id"] == "demo-shanghai-1")
        status, breakdown = request(self.base, f"/api/posts/{post['id']}/breakdown", "POST", {})
        self.assertEqual(status, 200)
        self.assertIn("无痛", breakdown["risk_words"])

        status, draft = request(self.base, f"/api/posts/{post['id']}/draft", "POST", {"city": "上海"})
        self.assertEqual(status, 200)
        self.assertNotIn("无痛", draft["script"])
        self.assertFalse(overlaps_source(draft["script"], post["transcript"]))

        status, blocked = request(
            self.base,
            f"/api/drafts/{draft['id']}/body",
            "PUT",
            {"script": draft["script"] + "无痛"},
        )
        self.assertEqual(status, 200)
        status, denied = request(self.base, f"/api/drafts/{draft['id']}/approve", "POST", {})
        self.assertEqual(status, 400)
        self.assertIn("无痛", denied["error"])

        status, saved = request(self.base, f"/api/drafts/{draft['id']}/body", "PUT", {"script": draft["script"]})
        self.assertEqual(saved["risk_words"], [])
        status, approved = request(self.base, f"/api/drafts/{draft['id']}/approve", "POST", {})
        self.assertEqual(approved["status"], "approved")

        status, package = request(
            self.base,
            f"/api/drafts/{draft['id']}/package",
            "POST",
            {"account": "诊所号", "video_path": "", "execute": False},
        )
        self.assertEqual(status, 200)
        self.assertFalse(package["executed"])
        self.assertIn("未执行上传", package["message"])
        folder = Path(package["package_dir"])
        self.assertTrue((folder / "script.txt").is_file())
        self.assertIn("sau", (folder / "command.txt").read_text(encoding="utf-8"))
        self.assertNotIn("无痛", (folder / "script.txt").read_text(encoding="utf-8"))

        status, settings = request(
            self.base,
            "/api/settings",
            "PUT",
            {"city": "深圳", "llm_api_key": "secret-key"},
        )
        self.assertEqual(settings["city"], "深圳")
        self.assertEqual(settings["llm_api_key"], "******")
        self.assertNotIn("secret-key", json.dumps(settings))
        stored = json.loads((self.db.parent / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["llm_api_key"], "secret-key")

    def test_missing_post_fetch_does_not_need_f2(self):
        status, payload = request(self.base, "/api/posts/999/fetch", "POST", {})
        self.assertEqual(status, 400)
        self.assertIn("不存在", payload["error"])


class ApproveUnitTest(unittest.TestCase):
    def test_direct_approve_blocks_risk(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "t.db"
            conn = connect(db)
            init_db(conn)
            conn.execute(
                """
                INSERT INTO posts (
                    aweme_id, keyword, title, author, liked_count, comment_count,
                    share_count, aweme_url, transcript, source, status, created_at, updated_at
                ) VALUES ('x', '', 't', '', 0, 0, 0, '', '口播', '测试', 'drafted', 't', 't')
                """
            )
            post_id = conn.execute("SELECT id FROM posts").fetchone()["id"]
            draft_id = insert_draft(
                conn,
                post_id,
                {
                    "city": "北京",
                    "title": "标题",
                    "script": "这里写了无痛",
                    "shots": "1",
                    "cover_text": "封面",
                    "tags": "标签",
                    "risk_words": ["无痛"],
                    "engine": "rule",
                    "note": "",
                },
            )
            conn.commit()
            with self.assertRaises(ValueError):
                approve_draft(conn, draft_id)
            self.assertEqual(get_draft(conn, draft_id)["status"], "draft")
            conn.close()
            self.assertIsNone(shutil.which("__citydesk_missing__"))


if __name__ == "__main__":
    unittest.main()
