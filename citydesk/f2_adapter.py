"""调用 Apache-2.0 项目 Johnserf-Seed/f2 的单条作品命令，读取它保存的文案。"""

import subprocess
from pathlib import Path


def build_command(url: str, dest: Path, cookie: str = "") -> list[str]:
    command = ["f2", "douyin", "-u", url, "-M", "one", "-p", str(dest)]
    if cookie.strip():
        command.extend(["-k", cookie.strip()])
    return command


def read_desc(folder: Path) -> str:
    if not folder.exists():
        return ""
    files = sorted(folder.rglob("*_desc.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            return text
    return ""


def run_fetch(url: str, dest: Path, cookie: str = "", timeout: int = 120) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    command = build_command(url, dest, cookie)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ValueError("本机没有 f2。先运行 scripts\\setup.ps1，或直接粘贴口播。") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("f2 超时。可以改成手工粘贴口播。") from exc
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    desc = read_desc(dest)
    if not desc:
        tail = stderr[-400:] if stderr else "没有读到 _desc.txt"
        raise ValueError(f"f2 没有保存文案。{tail}")
    return {"transcript": desc, "returncode": completed.returncode}
