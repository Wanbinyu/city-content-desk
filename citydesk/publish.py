"""生成发布包，并拼出 social-auto-upload 的上传命令。默认不执行。"""

import shutil
import subprocess
from pathlib import Path


def build_command(account: str, video_path: str, title: str, desc: str) -> str:
    return subprocess.list2cmdline(
        [
            "sau",
            "douyin",
            "upload-video",
            "--account",
            account or "账号名",
            "--file",
            video_path or "VIDEO_PATH",
            "--title",
            title[:55],
            "--desc",
            desc[:500],
        ]
    )


def write_package(folder: Path, draft: dict, account: str, video_path: str) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    desc = draft["script"].strip()
    tags = draft.get("tags", "").replace("，", ",")
    tag_line = " ".join(f"#{item.strip()}" for item in tags.split(",") if item.strip())
    full_desc = desc if not tag_line else f"{desc}\n{tag_line}"
    files = {
        "title.txt": draft["title"].strip(),
        "script.txt": draft["script"].strip(),
        "shots.txt": draft["shots"].strip(),
        "cover.txt": draft["cover_text"].strip(),
        "tags.txt": draft["tags"].strip(),
        "README.txt": (
            "这是发布包，不是已发布。\n"
            "请人工核对医疗广告表述，确认成片是本机构自己的素材后，再上传。\n"
            "上传命令在 command.txt。默认不会自动执行。\n"
        ),
    }
    command = build_command(account, video_path, draft["title"].strip(), full_desc)
    files["command.txt"] = command + "\n"
    for name, content in files.items():
        (folder / name).write_text(content, encoding="utf-8")
    return {"command": command, "package_dir": str(folder)}


def execute_upload(command_args: list[str], timeout: int = 300) -> tuple[bool, str]:
    if shutil.which("sau") is None and shutil.which(command_args[0]) is None:
        return False, "本机没有 sau。发布包已生成，可稍后按 social-auto-upload 的文档登录后再执行 command.txt。"
    completed = subprocess.run(
        command_args,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        return False, (stderr or stdout or "上传命令失败")[-500:]
    return True, "已执行上传命令。请到创作者中心再看一眼。"
