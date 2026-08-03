#!/usr/bin/env python3
"""슬라이드 이미지 → .pptx 조립 — gpt-ppt-image 덱 워크플로의 마지막 단계.

이미지 한 장이 슬라이드 한 장을 꽉 채운다 (텍스트는 이미지에 그려져 있다).
산출물은 이미지 슬라이드라 나중에 글자를 고칠 수 없다 — 편집 가능한 pptx가
필요하면 이 스크립트가 아니라 `pptx` 스킬을 쓴다.

사용:
  python assemble_ppt.py gpt-image/mydeck -o mydeck.pptx
  python assemble_ppt.py a.png b.png c.png -o deck.pptx --notes speech.md
  python assemble_ppt.py DIR -o out.pptx --ar 4:3
  python assemble_ppt.py --selftest

디렉터리를 주면 `slide_01.png`, `slide_02.png` … 를 페이지 번호순으로 모은다
(그 패턴에 안 맞는 파일은 샘플·참고용으로 보고 건너뛴다).
파일을 직접 나열하면 나열한 순서 그대로 쓴다.

발표노트(--notes)는 마크다운 헤딩으로 페이지를 가른다. 아래 형식을 모두 인식:
  ## Slide 1: 제목   ## 1장: 제목   ## 1페이지 - 제목   ## 第 1 页：标题

의존성: pip install python-pptx  (2MB 초과 이미지 압축에만 Pillow 추가 사용)
"""
import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SLIDE_RE = re.compile(r"^slide[_-]?(\d+)\.(png|jpe?g|gif|bmp)$", re.IGNORECASE)
# "## Slide 1:", "## 1장", "## 1 페이지", "## 第 1 页" — 숫자만 뽑는다.
NOTE_HEADING_RE = re.compile(
    r"^#{1,4}\s*(?:slide\s*)?(?:第\s*)?(\d+)\s*(?:장|페이지|쪽|页|p)?\b\s*[:：.\-–—]?\s*.*$",
    re.IGNORECASE,
)
MAX_MB = 2.0          # pptx가 비대해지지 않도록 장당 상한
AR_INCHES = {"16:9": (10, 5.625), "4:3": (10, 7.5)}


# ── 순수 함수 (selftest 대상 — python-pptx 없이 돈다) ──────────────────────────

def slide_sort_key(name):
    """'slide_10.png' 이 'slide_2.png' 앞에 오지 않도록 페이지 번호로 정렬."""
    m = SLIDE_RE.match(name)
    return (int(m.group(1)), name.lower())


def collect_images(inputs):
    """디렉터리 1개 → slide_NN 패턴 정렬. 파일 여러 개 → 준 순서 그대로."""
    if len(inputs) == 1 and Path(inputs[0]).is_dir():
        d = Path(inputs[0])
        names = sorted((f.name for f in d.iterdir()
                        if f.is_file() and SLIDE_RE.match(f.name)), key=slide_sort_key)
        return [str(d / n) for n in names]
    return [str(Path(p)) for p in inputs]


def parse_notes(text):
    """마크다운 → {페이지번호: 노트 본문}. 헤딩 사이의 줄을 그 페이지에 붙인다."""
    notes, cur, buf = {}, None, []

    def flush():
        if cur is not None and "\n".join(buf).strip():
            notes[cur] = "\n".join(buf).strip()

    for line in text.splitlines():
        m = NOTE_HEADING_RE.match(line.strip())
        if m:
            flush()
            cur, buf = int(m.group(1)), []
            continue
        if cur is not None:
            buf.append(line)
    flush()
    return notes


# ── 이미지·pptx (지연 임포트) ──────────────────────────────────────────────────

def compress_if_needed(path, max_mb=MAX_MB):
    """상한 초과분만 JPEG 재인코딩. 임시파일 경로를 돌려주고, 불필요하면 None."""
    if os.path.getsize(path) <= max_mb * 1024 * 1024:
        return None
    try:
        from PIL import Image
    except ImportError:
        print(f"  경고: Pillow 미설치로 압축 생략 ({Path(path).name}) — pip install Pillow")
        return None

    img = Image.open(path)
    if img.mode in ("RGBA", "LA", "P"):
        if img.mode == "P":
            img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg

    fd, tmp = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    limit = max_mb * 1024 * 1024
    for q in range(95, 20, -5):          # 먼저 품질로
        img.save(tmp, "JPEG", quality=q, optimize=True)
        if os.path.getsize(tmp) <= limit:
            print(f"  압축: {Path(path).name} → {os.path.getsize(tmp)/1048576:.2f}MB (품질 {q})")
            return tmp
    for scale in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4):   # 그래도 크면 축소
        img.resize((int(img.width*scale), int(img.height*scale)),
                   Image.Resampling.LANCZOS).save(tmp, "JPEG", quality=85, optimize=True)
        if os.path.getsize(tmp) <= limit:
            print(f"  압축: {Path(path).name} → {os.path.getsize(tmp)/1048576:.2f}MB (축소 {scale:.0%})")
            return tmp
    print(f"  경고: {Path(path).name} 을 {max_mb}MB 이하로 못 줄임 — 최소 버전 사용")
    return tmp


def build(images, out_path, aspect="16:9", notes=None):
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError:
        sys.exit("python-pptx 미설치 — pip install python-pptx")

    notes = notes or {}
    prs = Presentation()
    w, h = AR_INCHES[aspect]
    prs.slide_width, prs.slide_height = Inches(w), Inches(h)

    temps = []
    try:
        for i, img in enumerate(images, 1):
            if not os.path.isfile(img):
                sys.exit(f"이미지 없음: {img}")   # 조용히 건너뛰면 장수가 어긋난다
            tmp = compress_if_needed(img)
            if tmp:
                temps.append(tmp)
            slide = prs.slides.add_slide(prs.slide_layouts[6])   # 6 = 빈 레이아웃
            slide.shapes.add_picture(tmp or img, 0, 0,
                                     width=prs.slide_width, height=prs.slide_height)
            if notes.get(i):
                frame = slide.notes_slide.notes_text_frame
                frame.clear()
                frame.text = notes[i]
            print(f"  {i}장 ← {Path(img).name}" + ("  +노트" if notes.get(i) else ""))

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(out))
    finally:
        for t in temps:
            try:
                os.remove(t)
            except OSError:
                pass

    matched = sum(1 for i in range(1, len(images) + 1) if notes.get(i))
    print(f"저장: {out}  ({len(images)}장, {aspect}, 노트 {matched}/{len(images)}장)")
    return out


# ── 자기점검 · CLI ─────────────────────────────────────────────────────────────

def selftest():
    assert sorted(["slide_10.png", "slide_2.png", "slide_1.png"], key=slide_sort_key) == \
        ["slide_1.png", "slide_2.png", "slide_10.png"]
    assert SLIDE_RE.match("slide_01.png") and SLIDE_RE.match("slide-3.JPG")
    assert not SLIDE_RE.match("sample_slide.png")   # 샘플은 덱에 안 들어간다
    assert not SLIDE_RE.match("reference.png")

    n = parse_notes("## Slide 1: 도입\n첫 장 멘트\n\n## 2장: 본론\n둘째 장 멘트\n")
    assert n == {1: "첫 장 멘트", 2: "둘째 장 멘트"}, n
    assert parse_notes("## 第 3 页：结论\n셋째\n") == {3: "셋째"}
    assert parse_notes("### 4페이지 - 마무리\n넷째\n") == {4: "넷째"}
    assert parse_notes("본문만 있고 헤딩 없음") == {}
    assert parse_notes("## Slide 1: 빈 장\n\n## Slide 2: 내용\n있음") == {2: "있음"}

    assert collect_images(["a.png", "b.png"]) == [str(Path("a.png")), str(Path("b.png"))]
    assert AR_INCHES["16:9"] == (10, 5.625)
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="이미지 디렉터리 1개 또는 이미지 파일들")
    ap.add_argument("-o", "--out", help="출력 .pptx 경로")
    ap.add_argument("--notes", help="발표노트 마크다운 (speech.md)")
    ap.add_argument("--ar", "--aspect-ratio", choices=list(AR_INCHES), default="16:9",
                    dest="ar", help="슬라이드 비율 (기본 16:9)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return
    if not a.inputs or not a.out:
        ap.error("inputs 와 -o 가 필요합니다 (--selftest 제외)")

    images = collect_images(a.inputs)
    if not images:
        sys.exit(f"슬라이드 이미지를 못 찾음: {a.inputs[0]} "
                 "(디렉터리라면 slide_01.png 형식이어야 함)")

    notes = {}
    if a.notes:
        p = Path(a.notes)
        if not p.is_file():
            sys.exit(f"노트 파일 없음: {p}")
        notes = parse_notes(p.read_text(encoding="utf-8"))

    print(f"{len(images)}장 조립 중 ({a.ar})…")
    build(images, a.out, a.ar, notes)


if __name__ == "__main__":
    main()
