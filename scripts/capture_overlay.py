#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML 오버레이 → Chrome 헤드리스 캡처 → 배경과 1:1 크기 검증.

사용법:
    python capture_overlay.py <overlay.html> <out.png> <base.png>
    python capture_overlay.py --selfcheck

성공 시 마지막 줄에 {"out": ..., "size": [w, h]} JSON을 출력한다.
1:1 규칙 강제 2중 검증:
  ① 캡처 전 — HTML body 선언 크기(width/height px)가 배경 원본 픽셀과 다르면 exit 1
     (viewport가 배경 크기로 고정되므로 body가 크면 잘려나가는 작성 오류를 사전 차단)
  ② 캡처 후 — 출력 픽셀 크기가 배경 원본과 다르면 exit 1 (DPI/스케일 이상 차단)
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    return shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")


def check_body_size(html: Path, w: int, h: int):
    """HTML body 선언 크기 = 배경 크기 사전 검증 (§3-A 1:1 규칙)."""
    text = html.read_text(encoding="utf-8")
    m = re.search(r"body\s*\{([^}]*)\}", text, re.S)
    if not m:
        sys.exit("HTML에 body{...} 규칙이 없음 — §3-A 규약: body 크기 = 배경 원본 픽셀")
    mw = re.search(r"width:\s*(\d+)px", m.group(1))
    mh = re.search(r"height:\s*(\d+)px", m.group(1))
    if not (mw and mh):
        sys.exit("body에 width/height px 선언이 없음 — §3-A 규약 위반")
    declared = (int(mw.group(1)), int(mh.group(1)))
    if declared != (w, h):
        sys.exit(f"body 선언 크기 {declared} ≠ 배경 원본 {(w, h)} — 1:1 규칙 위반(잘림/여백 발생)")


def capture(html: Path, out: Path, base: Path) -> dict:
    # Chrome은 상대경로를 자기 작업 디렉터리 기준으로 풀므로 전부 절대화한다
    html, out, base = html.resolve(), out.resolve(), base.resolve()
    if not html.exists():
        sys.exit(f"overlay HTML 없음: {html}")
    if not base.exists():
        sys.exit(f"배경 PNG 없음: {base}")
    w, h = Image.open(base).size
    check_body_size(html, w, h)
    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome을 찾지 못함 — SKILL.md 오류표의 resvg 폴백을 사용하세요")
    r = subprocess.run(
        [
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--screenshot={out}", f"--window-size={w},{h}",
            "--virtual-time-budget=3000", html.resolve().as_uri(),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if not out.exists():
        sys.exit(f"캡처 실패: {r.stderr.strip()[-500:]}")
    size = Image.open(out).size
    if size != (w, h):
        sys.exit(f"크기 불일치: 출력={size} 배경={(w, h)} — 1:1 규칙 위반(뷰포트/스케일 확인)")
    return {"out": str(out), "size": [w, h]}


def selfcheck() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="capture_selfcheck_"))
    base = tmp / "base.png"
    Image.new("RGB", (320, 200), "#dde7e3").save(base)
    html = tmp / "overlay.html"
    html.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<style>*{margin:0}body{width:320px;height:200px;position:relative;"
        "font-family:'Malgun Gothic'}img{position:absolute;inset:0}"
        ".p{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);"
        "background:rgba(17,24,39,.72);color:#fff;padding:6px 12px;"
        "border-radius:8px;font-size:20px;white-space:nowrap}</style>"
        "<img src='base.png'><div class='p'>한글 자가점검</div>",
        encoding="utf-8",
    )
    result = capture(html, tmp / "out.png", base)
    assert result["size"] == [320, 200]
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if "--selfcheck" in sys.argv:
        print(json.dumps(selfcheck(), ensure_ascii=False))
        return
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    html, out, base = (Path(a) for a in sys.argv[1:4])
    print(json.dumps(capture(html, out, base), ensure_ascii=False))


if __name__ == "__main__":
    main()
