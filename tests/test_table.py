import tempfile
import unittest
from pathlib import Path

from citydesk.jobs import generate_table
from citydesk.tablecopy import ai_table, parse_table, prepare_copy, resolve_table, retitle, script_table
from citydesk.video import image_url_allowed


class TableCopyTest(unittest.TestCase):
    def test_city_swap_and_user_table(self):
        columns, rows = parse_table("排名,机构\n1,北京示例机构甲\n")
        self.assertEqual(columns, ["排名", "机构"])
        self.assertEqual(rows[0][1], "北京示例机构甲")
        self.assertEqual(retitle("北京双眼皮机构对照表", "武汉", "双眼皮"), "武汉双眼皮机构对照表")

    def test_script_uses_example_and_refuses_missing_city(self):
        root = Path(__file__).resolve().parents[1]
        columns, rows, note = script_table("武汉", "双眼皮", Path("missing"), root / "examples" / "ranks")
        self.assertEqual(columns[0], "排名")
        self.assertIn("示例", rows[0][1])
        self.assertIn("不是真实排名", note)
        with self.assertRaises(ValueError):
            script_table("拉萨", "双眼皮", Path("missing"), root / "examples" / "ranks")

    def test_ai_does_not_invent_without_material(self):
        with self.assertRaises(ValueError) as caught:
            ai_table("武汉", "双眼皮", "", {"llm_api_key": "x", "llm_base_url": "http://x", "llm_model": "m"})
        self.assertIn("不会编造", str(caught.exception))

    def test_generate_page_and_video(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "citydesk.db"
            result = generate_table(
                {
                    "url": "https://v.douyin.com/example/",
                    "title": "北京双眼皮机构对照表",
                    "city": "武汉",
                    "topic": "双眼皮",
                    "source": "user",
                    "table_text": "排名,机构,参考信息\n1,北京示例机构甲,当面核对项目\n",
                },
                db,
                {},
            )
            self.assertEqual(result["title"], "武汉双眼皮机构对照表")
            self.assertIn("武汉示例机构甲", result["table_text"])
            self.assertIn("武汉", result["caption"])
            folder_path = Path(result["folder"])
            self.assertTrue((folder_path / "index.html").is_file())
            self.assertTrue((folder_path / "video.mp4").is_file())
            self.assertTrue((folder_path / "caption.txt").is_file())
            page = (folder_path / "index.html").read_text(encoding="utf-8")
            self.assertIn("武汉示例机构甲", page)
            self.assertNotIn("北京示例机构甲", page)

    def test_loose_text_custom_city_and_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            prepared = prepare_copy(
                {
                    "title": "嘉定双眼皮怎么选",
                    "city": "青岛",
                    "from_city": "嘉定",
                    "topic": "双眼皮",
                    "source": "user",
                    "notes": "把示例机构甲改成海滨示例",
                    "table_text": "\n".join(
                        [
                            "先看完再问",
                            "1、嘉定示例机构甲：当面核对项目",
                            "2、嘉定示例机构乙：不要保证效果",
                            "https://v.douyin.com/abc/",
                        ]
                    ),
                },
                Path(folder),
                Path(folder),
                {},
            )
        self.assertEqual(prepared["title"], "青岛双眼皮怎么选")
        self.assertEqual(prepared["columns"], ["排名", "机构", "参考信息"])
        self.assertIn("青岛海滨示例", prepared["table_text"])
        self.assertNotIn("嘉定", prepared["table_text"])
        self.assertNotIn("https://", prepared["table_text"])
        self.assertIn("保证", prepared["risks"])
        self.assertIn("已按补充说明替换", prepared["note"])

    def test_chinese_comma_json_and_row_limit(self):
        columns, rows = parse_table("排名，机构\n1，甲\n")
        self.assertEqual(rows, [["1", "甲"]])
        columns, rows = parse_table('[{"排名":"1","机构":"乙"}]')
        self.assertEqual(columns, ["排名", "机构"])
        self.assertEqual(rows, [["1", "乙"]])
        body = "排名,机构\n" + "".join(f"{index},甲\n" for index in range(1, 30))
        with self.assertRaises(ValueError) as caught:
            parse_table(body)
        self.assertIn("28", str(caught.exception))

    def test_gbk_rank_file_and_preview_skips_video(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rank = root / "青岛-双眼皮.csv"
            rank.write_bytes("排名,机构\n1,示例机构甲\n".encode("gbk"))
            columns, rows, note = script_table("青岛", "双眼皮", root, Path(folder) / "none")
            self.assertEqual(rows[0][1], "示例机构甲")
            self.assertIn("你放入的排名文件", note)
            db = root / "citydesk.db"
            result = generate_table(
                {
                    "title": "北京双眼皮",
                    "city": "武汉",
                    "source": "user",
                    "preview": True,
                    "table_text": "排名,机构\n1,北京示例机构甲\n",
                },
                db,
                {},
            )
            self.assertTrue(result["preview"])
            self.assertEqual(result["page_url"], "")
            self.assertIn("武汉示例机构甲", result["table_text"])
            self.assertFalse((root / "outputs").exists())

    def test_ai_uses_parsed_table_without_model(self):
        columns, rows, note = resolve_table(
            {"source": "ai", "city": "武汉", "table_text": "排名,机构\n1,甲\n"},
            Path("missing"),
            Path("missing"),
            {},
        )
        self.assertEqual(columns, ["排名", "机构"])
        self.assertEqual(rows, [["1", "甲"]])
        self.assertIn("你贴上的表格", note)

    def test_image_url_blocks_private_hosts(self):
        self.assertFalse(image_url_allowed("http://127.0.0.1/a.png"))
        self.assertFalse(image_url_allowed("http://10.1.2.3/a.png"))
        self.assertFalse(image_url_allowed("http://192.168.0.8/a.png"))
        self.assertFalse(image_url_allowed("http://169.254.169.254/latest"))
        self.assertFalse(image_url_allowed("file:///C:/Windows/win.ini"))


if __name__ == "__main__":
    unittest.main()
