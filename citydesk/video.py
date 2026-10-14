"""把对照表画成竖屏页面，并导出一张封面和一条静帧视频。"""

import html
import ipaddress
import shutil
import socket
import subprocess
import urllib.error
import urllib.request
from io import BytesIO
from urllib.parse import urlparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from citydesk.tablecopy import table_text

WIDTH = 1080
HEIGHT = 1920
ROWS_PER_PAGE = 7
GREEN = (33, 115, 70)
INK = (28, 25, 21)
PAPER = (246, 248, 244)
LINE = (214, 222, 214)
WHITE = (255, 255, 255)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    # 文泉驿微米黑只有一个字重，Linux 上粗体标题也用这个文件。
    names = (
        ["msyhbd.ttc", "msyh.ttc", "wqy-microhei.ttc", "NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc"]
        if bold
        else ["msyh.ttc", "wqy-microhei.ttc", "NotoSansCJK-Regular.ttc"]
    )
    folders = [
        Path(r"C:\Windows\Fonts"),
        Path("/usr/share/fonts/truetype/wqy"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/noto"),
    ]
    for folder in folders:
        for name in names:
            path = folder / name
            if path.is_file():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


_NARROW = {"排名", "序号", "名次", "序", "#"}
_IMAGE = {"图片", "图", "封面", "截图"}


def _weight(column: str) -> float:
    name = column.strip()
    if name in _NARROW:
        return 0.62
    if name in _IMAGE:
        return 0.9
    if len(name) <= 2:
        return 0.85
    return 1.45


def _widths(columns: list[str], total: int) -> list[int]:
    weights = [_weight(column) for column in columns]
    raw = [weight / sum(weights) * total for weight in weights]
    widths = [max(1, int(value)) for value in raw]
    widths[-1] += total - sum(widths)
    return widths


def _lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, limit: int) -> list[str]:
    value = " ".join((text or "").split())
    if not value:
        return [""]
    lines = []
    while value and len(lines) < limit:
        if draw.textlength(value, font=font) <= width:
            lines.append(value)
            break
        last = len(lines) == limit - 1
        take = 1
        while take < len(value):
            piece = value[: take + 1]
            shown = piece + "…" if last else piece
            if draw.textlength(shown, font=font) > width:
                break
            take += 1
        if last:
            chunk = value[:take]
            while chunk and draw.textlength(chunk + "…", font=font) > width:
                chunk = chunk[:-1]
            lines.append((chunk or value[:1]) + "…")
            break
        lines.append(value[:take])
        value = value[take:]
    return lines


def image_url_allowed(url: str) -> bool:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal")):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, None)]
        except socket.gaierror:
            return False
    for address in addresses:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return False
    return True


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not image_url_allowed(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _store_remote_image(url: str, dest: Path) -> bool:
    if not image_url_allowed(url):
        return False
    request = urllib.request.Request(url, headers={"User-Agent": "citydesk"})
    opener = urllib.request.build_opener(_CheckedRedirect)
    try:
        with opener.open(request, timeout=8) as response:
            chunks = []
            total = 0
            while True:
                block = response.read(65536)
                if not block:
                    break
                total += len(block)
                if total > 4_000_000:
                    return False
                chunks.append(block)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False
    try:
        image = Image.open(BytesIO(b"".join(chunks)))
        image.convert("RGB").save(dest, "PNG")
    except OSError:
        return False
    return dest.is_file()


def _materialize_images(rows: list[list[str]], job_dir: Path) -> list[list[str]]:
    copied = []
    index = 1
    for row in rows:
        cells = []
        for cell in row:
            text = (cell or "").strip()
            if text.startswith(("http://", "https://")):
                dest = job_dir / f"img_{index:02d}.png"
                if _store_remote_image(text, dest):
                    cells.append(dest.name)
                    index += 1
                    continue
            cells.append(cell)
        copied.append(cells)
    return copied


def _pages(rows: list[list[str]]) -> list[list[list[str]]]:
    if not rows:
        return [[]]
    return [rows[index : index + ROWS_PER_PAGE] for index in range(0, len(rows), ROWS_PER_PAGE)]


def _draw_page(title: str, columns: list[str], rows: list[list[str]], page: int, total: int, job_dir: Path) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    title_font = _font(64, bold=True)
    head_font = _font(32, bold=True)
    cell_font = _font(30)
    small = _font(26)
    title_lines = _lines(draw, title, title_font, WIDTH - 144, 2)
    y = 72
    for line in title_lines:
        draw.text((72, y), line, font=title_font, fill=INK)
        y += 76
    draw.text((72, y + 4), f"对照表  {page}/{total}", font=small, fill=(90, 100, 90))

    table_top = y + 56
    table_width = WIDTH - 144
    widths = _widths(columns, table_width)
    header_h = 78
    row_h = 150
    draw.rectangle((72, table_top, 72 + table_width, table_top + header_h), fill=GREEN)
    x = 72
    for index, column in enumerate(columns):
        header_lines = _lines(draw, column, head_font, widths[index] - 28, 2)
        draw.text((x + 16, table_top + 18), header_lines[0], font=head_font, fill=WHITE)
        x += widths[index]
    for row_index, row in enumerate(rows):
        top = table_top + header_h + row_index * row_h
        fill = WHITE if row_index % 2 == 0 else (236, 244, 236)
        draw.rectangle((72, top, 72 + table_width, top + row_h), fill=fill, outline=LINE)
        x = 72
        for index, cell in enumerate(row):
            picture = _local_image(cell, job_dir)
            if picture is not None:
                thumb = picture.convert("RGB")
                thumb.thumbnail((widths[index] - 36, row_h - 28))
                image.paste(thumb, (x + 16, top + (row_h - thumb.height) // 2))
            else:
                lines = _lines(draw, cell, cell_font, widths[index] - 28, 3)
                line_h = 36
                start = top + max(12, (row_h - line_h * len(lines)) // 2)
                for offset, line in enumerate(lines):
                    draw.text((x + 16, start + offset * line_h), line, font=cell_font, fill=INK)
            x += widths[index]
    draw.text((72, HEIGHT - 120), "方案因人而异，表内信息以导入材料为准", font=small, fill=(90, 100, 90))
    return image


def _local_image(cell: str, job_dir: Path) -> Image.Image | None:
    text = (cell or "").strip().strip('"')
    if not text:
        return None
    path = Path(text)
    if not path.is_file():
        path = job_dir / text
    if not path.is_file():
        return None
    try:
        return Image.open(path)
    except OSError:
        return None


def _html(title: str, columns: list[str], rows: list[list[str]], caption: str, note: str, job_dir: Path) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = []
        for cell in row:
            picture = _local_image(cell, job_dir)
            if picture is not None:
                name = Path(cell.strip().strip('"')).name
                target = job_dir / name
                if not target.exists():
                    shutil.copyfile(Path(cell.strip().strip('"')), target)
                cells.append(f'<td><img src="{html.escape(name)}" alt=""></td>')
            else:
                cells.append(f"<td>{html.escape(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 0; background: #dfe8df; font-family: "Microsoft YaHei", sans-serif; color: #1c1915; }}
    .phone {{ width: min(390px, 100%); min-height: 640px; margin: 0 auto; background: #f6f8f4; padding: 28px 18px 36px; box-sizing: border-box; }}
    h1 {{ font-size: 28px; line-height: 1.25; margin: 0 0 8px; }}
    .meta {{ color: #5c665c; font-size: 13px; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th {{ background: #217346; color: white; text-align: left; padding: 8px; font-size: 13px; }}
    td {{ border-bottom: 1px solid #d6ded6; padding: 10px 8px; font-size: 14px; vertical-align: middle; }}
    tr:nth-child(even) td {{ background: #f3f8f3; }}
    img {{ max-width: 72px; max-height: 72px; display: block; }}
    .foot {{ margin-top: 16px; color: #5c665c; font-size: 12px; }}
    pre {{ white-space: pre-wrap; font: 15px/1.5 "Microsoft YaHei", sans-serif; margin: 12px auto 24px; width: min(390px, 100%); box-sizing: border-box; padding: 0 12px; }}
  </style>
</head>
<body>
  <article class="phone">
    <h1>{html.escape(title)}</h1>
    <p class="meta">{html.escape(note)}</p>
    <table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>
    <p class="foot">方案因人而异，表内信息以导入材料为准</p>
  </article>
  <pre>{html.escape(caption)}</pre>
</body>
</html>
"""


def _video(frames: list[Path], target: Path) -> str:
    if shutil.which("ffmpeg") is None:
        return "页面已生成。本机没有 ffmpeg，所以没有导出视频。"
    lines = []
    for path in frames:
        lines.append(f"file '{path.name}'")
        lines.append("duration 4")
    lines.append(f"file '{frames[-1].name}'")
    list_file = target.parent / "frames.txt"
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-vsync",
            "vfr",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        cwd=target.parent,
        capture_output=True,
        timeout=max(60, 25 * len(frames)),
        check=False,
    )
    if completed.returncode != 0 or not target.is_file():
        tail = completed.stderr.decode("utf-8", errors="replace")[-300:]
        return f"页面已生成。视频导出失败：{tail}"
    return ""


def render_job(job_dir: Path, title: str, columns: list[str], rows: list[list[str]], caption: str, note: str) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)
    rows = _materialize_images(rows, job_dir)
    pages = _pages(rows)
    frames = []
    for index, page_rows in enumerate(pages, start=1):
        image = _draw_page(title, columns, page_rows, index, len(pages), job_dir)
        frame = job_dir / f"frame_{index:02d}.png"
        image.save(frame)
        frames.append(frame)
    poster = job_dir / "poster.png"
    shutil.copyfile(frames[0], poster)
    (job_dir / "index.html").write_text(_html(title, columns, rows, caption, note, job_dir), encoding="utf-8")
    (job_dir / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    (job_dir / "table.csv").write_text(table_text(columns, rows), encoding="utf-8")
    video = job_dir / "video.mp4"
    video_message = _video(frames, video)
    return {
        "poster": poster.name,
        "page": "index.html",
        "video": video.name if video.is_file() else "",
        "caption_file": "caption.txt",
        "video_message": video_message,
    }
