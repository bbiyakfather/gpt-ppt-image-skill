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
# 접두사(slide/第) · 접미사(장/페이지/…) · 구분자 중 최소 하나를 요구한다.
# 셋 다 선택적이면 "## 10가지 핵심 포인트" 같은 평범한 소제목이 10장으로 잡혀
# 앞 장의 노트가 조기 종료되고 없는 장에 노트가 흡수된다 (경고 없이).
NOTE_HEADING_RE = re.compile(
    r"^#{1,4}\s*(?:"
    r"(?:slide|第)\s*(\d+)"                       # 접두사형: Slide 1 / 第 1
    r"|(\d+)\s*(?:장|페이지|쪽|页|p)\b"            # 접미사형: 1장 / 1페이지 / 1p
    r"|(\d+)\s*[:：.\-–—](?=\s|$)"                # 구분자형: "1: 제목" ("3.5%" 는 제외)
    r")",
    re.IGNORECASE,
)


def heading_page(line):
    """헤딩 줄 -> 페이지 번호. 슬라이드 헤딩이 아니면 None."""
    m = NOTE_HEADING_RE.match(line)
    if not m:
        return None
    return int(next(g for g in m.groups() if g is not None))
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
        page = heading_page(line.strip())
        if page is not None:
            flush()
            cur, buf = page, []
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
    # Image.Resampling 은 Pillow>=9.1 에만 있음. 없으면 구버전대로 Image.LANCZOS 를 쓴다.
    resample = getattr(Image, "Resampling", Image).LANCZOS
    for scale in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4):   # 그래도 크면 축소
        img.resize((int(img.width*scale), int(img.height*scale)),
                   resample).save(tmp, "JPEG", quality=85, optimize=True)
        if os.path.getsize(tmp) <= limit:
            print(f"  압축: {Path(path).name} → {os.path.getsize(tmp)/1048576:.2f}MB (축소 {scale:.0%})")
            return tmp
    print(f"  경고: {Path(path).name} 을 {max_mb}MB 이하로 못 줄임 — 최소 버전 사용")
    return tmp


AR_TOL = 0.01   # 비율 차이가 이 이하면 같은 비율로 본다


def missing_pages(paths):
    """slide_NN 파일명에서 빠진 번호를 찾는다. 디렉터리 수집 결과에만 의미가 있다.

    생성이 중간에 실패하면 그 장만 없는 채로 조립돼 조용히 짧은 덱이 나온다.
    """
    nums = []
    for p in paths:
        m = SLIDE_RE.match(Path(p).name)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return []
    return [n for n in range(min(nums), max(nums) + 1) if n not in set(nums)]


def fit_box(path, slide_w, slide_h, fit):
    """이미지를 슬라이드에 어떻게 앉힐지. -> (left, top, w, h) 또는 None(=꽉 채움).

    비율이 다른 이미지를 꽉 채우면 조용히 늘어나 얼굴·글자가 왜곡된다.
    """
    if fit == "stretch":
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
    except Exception:
        return None   # 크기를 못 읽으면 기존 동작 유지
    if not ih or not iw:
        return None
    slide_ar, img_ar = slide_w / slide_h, iw / ih
    if abs(slide_ar - img_ar) <= AR_TOL:
        return None
    if fit == "contain":
        if img_ar > slide_ar:                      # 이미지가 더 넓다 → 위아래 여백
            w = slide_w
            h = int(slide_w / img_ar)
        else:                                      # 더 좁다 → 좌우 여백
            h = slide_h
            w = int(slide_h * img_ar)
    else:                                          # cover: 채우고 넘치는 부분은 잘림
        if img_ar > slide_ar:
            h = slide_h
            w = int(slide_h * img_ar)
        else:
            w = slide_w
            h = int(slide_w / img_ar)
    return int((slide_w - w) / 2), int((slide_h - h) / 2), w, h


def build(images, out_path, aspect="16:9", notes=None, fit="contain"):
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
            box = fit_box(tmp or img, prs.slide_width, prs.slide_height, fit)
            if box is None:
                slide.shapes.add_picture(tmp or img, 0, 0,
                                         width=prs.slide_width, height=prs.slide_height)
            else:
                left, top, pw, ph = box
                slide.shapes.add_picture(tmp or img, left, top, width=pw, height=ph)
            if notes.get(i):
                frame = slide.notes_slide.notes_text_frame
                frame.clear()
                frame.text = notes[i]
            fitnote = "" if box is None else f"  [{fit}: 비율 달라 여백 처리]"
            print(f"  {i}장 ← {Path(img).name}"
                  + ("  +노트" if notes.get(i) else "") + fitnote)

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

    # 숫자로 시작하는 평범한 소제목을 슬라이드 헤딩으로 오인하면 안 된다
    assert parse_notes("## Slide 1: 도입\n첫\n\n## 10가지 핵심 포인트\n본문\n") == \
        {1: "첫\n\n## 10가지 핵심 포인트\n본문"}
    assert heading_page("## 3가지 이유") is None
    assert heading_page("## 2024년 전망") is None
    assert heading_page("## 3.5% 성장") is None
    assert heading_page("## 5. 결론") == 5
    assert heading_page("## Slide 7") == 7

    assert collect_images(["a.png", "b.png"]) == [str(Path("a.png")), str(Path("b.png"))]
    assert AR_INCHES["16:9"] == (10, 5.625)

    # 결번 감지 — 생성 실패한 장을 모른 채 짧은 덱을 내보내는 사고를 막는다
    assert missing_pages(["slide_01.png", "slide_02.png", "slide_05.png"]) == [3, 4]
    assert missing_pages(["slide_01.png", "slide_02.png"]) == []
    assert missing_pages(["a.png", "b.png"]) == []      # 파일 나열 모드는 대상 아님

    # 비율 처리: 같은 비율이면 꽉 채우고(None), 다르면 여백 상자를 준다
    assert fit_box("nonexistent.png", 1600, 900, "stretch") is None

    selftest_integration()
    print("selftest OK")


def selftest_integration():
    """build() 를 실제로 돌려보는 통합 점검 — 순수 함수만 보던 기존 selftest 의
    사각지대(감사에서 지적된 최우선 항목)를 없앤다.

    docstring 대로 "무거운 의존성 없이" 도는 게 selftest 의 전제라, python-pptx/
    Pillow 가 없으면 실패시키지 않고 건너뛴다.
    """
    try:
        from PIL import Image
        from pptx import Presentation
    except ImportError:
        print("selftest: 통합 점검 생략 (python-pptx 또는 Pillow 미설치)")
        return

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # slide_03 은 800x900(세로형)으로 만들어 16:9 슬라이드와 비율을 일부러 다르게 한다.
        for n, size in [(1, (1600, 900)), (2, (1600, 900)), (3, (800, 900))]:
            Image.new("RGB", size, "red").save(d / f"slide_{n:02d}.png")
        Image.new("RGB", (100, 100), "blue").save(d / "sample_slide.png")   # 덱에서 빠져야 함

        speech = d / "speech.md"
        speech.write_text(
            "## Slide 1: 도입\n첫 장 노트\n\n"
            "## 2장: 본론\n둘째 장 노트\n\n"
            "## Slide 3\n셋째 장 노트\n",
            encoding="utf-8",
        )

        images = collect_images([str(d)])
        assert len(images) == 3 and all("sample_slide" not in i for i in images), images

        notes = parse_notes(speech.read_text(encoding="utf-8"))
        out = d / "out.pptx"
        build(images, str(out), aspect="16:9", notes=notes, fit="contain")

        prs = Presentation(str(out))
        assert len(prs.slides) == 3, len(prs.slides)
        for idx, slide in enumerate(prs.slides, 1):
            actual = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
            assert actual == notes.get(idx, ""), (idx, actual, notes.get(idx))

        # 3번 장(800x900)은 슬라이드(16:9)와 비율이 달라 contain 처리돼야 한다 —
        # 그림 비율이 슬라이드가 아니라 원본 이미지 비율을 따르는지로 왜곡 여부를 확인.
        pic = list(prs.slides)[2].shapes[0]
        img_ar, pic_ar = 800 / 900, pic.width / pic.height
        assert abs(img_ar - pic_ar) < 0.01, (img_ar, pic_ar)

    print("selftest: 통합 점검 OK (build() 실제 실행 포함)")


def read_notes(path):
    """speech.md 원문 읽기. utf-8-sig 는 BOM 있는/없는 UTF-8 을 모두 받는다."""
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        sys.exit(f"노트 파일 인코딩을 읽을 수 없음: {path} (UTF-8로 저장해서 다시 시도)")


def report_status(images, notes_path=None):
    """덱 상태 조회 — 조립하지 않는다. 배치가 끊겼을 때 재개 지점을 알려준다.

    생성은 장당 1~2분에 구독 한도를 쓴다. 다 만들었는지 눈으로 세는 대신
    빠진 번호만 뽑아 그 장만 다시 만들 수 있게 한다.
    """
    have = sorted(int(SLIDE_RE.match(Path(p).name).group(1))
                  for p in images if SLIDE_RE.match(Path(p).name))
    gaps = missing_pages(images)
    print(f"수집: {len(images)}장" + (f"  (slide_{have[0]:02d}~slide_{have[-1]:02d})" if have else ""))
    if gaps:
        print("빠진 장: " + ", ".join(f"slide_{n:02d}" for n in gaps))
        print("  → 이 번호만 다시 생성하면 된다 (전체 재생성 불필요)")
    elif have:
        print("빠진 장: 없음")

    if notes_path:
        p = Path(notes_path)
        if not p.is_file():
            print(f"노트: 파일 없음 ({p})")
        else:
            notes = parse_notes(read_notes(p))
            missing = [n for n in (have or range(1, len(images) + 1)) if n not in notes]
            extra = [n for n in sorted(notes) if have and n not in have]
            print(f"노트: {len(notes)}개" + (f"  없는 장: {missing}" if missing else "  전 장 커버"))
            if extra:
                print(f"  경고: 없는 슬라이드 번호에 노트가 붙어 있음 {extra} — 헤딩 번호를 확인")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="이미지 디렉터리 1개 또는 이미지 파일들")
    ap.add_argument("-o", "--out", help="출력 .pptx 경로")
    ap.add_argument("--notes", help="발표노트 마크다운 (speech.md)")
    ap.add_argument("--ar", "--aspect-ratio", choices=list(AR_INCHES), default="16:9",
                    dest="ar", help="슬라이드 비율 (기본 16:9)")
    ap.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain",
                    help="비율이 다른 이미지 처리 (기본 contain: 여백을 두고 왜곡하지 않음. "
                         "stretch 는 슬라이드를 꽉 채우지만 늘어난다)")
    ap.add_argument("--allow-gaps", action="store_true",
                    help="slide_NN 번호가 비어 있어도 조립한다 (기본: 중단). "
                         "생성 실패한 장을 모르고 짧은 덱을 내보내는 사고를 막는다")
    ap.add_argument("--status", action="store_true",
                    help="조립하지 않고 덱 상태만 본다 — 있는 장·빠진 장·노트 커버리지. "
                         "배치가 중간에 끊겼을 때 어디부터 다시 만들지 알려준다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return
    if not a.inputs:
        ap.error("inputs 가 필요합니다 (--selftest 제외)")
    if not a.out and not a.status:
        ap.error("-o 가 필요합니다 (--status 로 조회만 할 수도 있습니다)")

    images = collect_images(a.inputs)
    if not images:
        sys.exit(f"슬라이드 이미지를 못 찾음: {a.inputs[0]} "
                 "(디렉터리라면 slide_01.png 형식이어야 함)")

    if a.status:
        return report_status(images, a.notes)

    gaps = missing_pages(images)
    if gaps:
        msg = ("slide 번호가 빠져 있음: "
               + ", ".join(f"slide_{n:02d}" for n in gaps)
               + f" (수집된 {len(images)}장)")
        if not a.allow_gaps:
            sys.exit(msg + "\n생성에 실패한 장이 있는지 확인하고, 의도한 것이면 --allow-gaps 를 준다.")
        print(f"  경고: {msg} — --allow-gaps 로 계속한다")

    notes = {}
    if a.notes:
        p = Path(a.notes)
        if not p.is_file():
            sys.exit(f"노트 파일 없음: {p}")
        notes = parse_notes(read_notes(p))

    print(f"{len(images)}장 조립 중 ({a.ar}, fit={a.fit})…")
    build(images, a.out, a.ar, notes, a.fit)


if __name__ == "__main__":
    main()
