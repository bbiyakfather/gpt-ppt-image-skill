#!/usr/bin/env python3
"""핀·붓 기반 국소 텍스트 수리 — gpt-ppt-image 7단계 보조 도구.

생성 이미지에서 깨진 텍스트 영역만 국소 수리한다 (전체 재생성 없이):
  1) 수리할 영역을 정한다 — 둘 중 하나
     · 핀(--pin): easyocr(CRAFT)로 텍스트 박스를 검출하고 핀이 가리키는 박스를 고른다
     · 붓(--mask): 리뷰 팝업에서 칠한 마스크 PNG를 그대로 영역으로 쓴다 (OCR 생략)
  2) cv2.inpaint 로 그 영역 배경 복원
  3) 원 글자색을 추정해 맑은 고딕으로 교체 문구 재기입

사용:
  python repair_text.py IMG --pin "62,88:내비온 기술연구소" [--pin ...] [-o OUT.png]
  python repair_text.py IMG --mask "mask_1.png:내비온 기술연구소" [--mask ...]
  python repair_text.py IMG --pin ... --engine sam   # 획 단위 정밀 마스크 (GPU 권장)
  python repair_text.py --selftest    # 순수 로직 자기점검 (모델 다운로드 없음)

핀 vs 붓:
  핀은 easyocr이 텍스트로 검출한 박스에만 붙는다. 장식 폰트·저대비·그림 위에 얹힌
  글자는 검출이 안 돼 핀을 못 쓴다 — 그때 붓으로 영역을 직접 칠한다.
  붓 경로는 OCR을 아예 돌리지 않아 easyocr 로딩(~15초)도 건너뛴다.

마스크 엔진 (--pin 경로에만 적용. 붓 마스크는 이미 정확한 영역이라 그대로 쓴다):
  rect (기본) — 검출 박스 사각형째 inpaint. 단순 배경에 충분, 추가 의존성 없음.
  sam        — SAM vit_b box 프롬프트로 글자 획만 마스킹. 그림 위에 겹친 텍스트용.
               pip install segment-anything + 첫 실행 시 체크포인트(375MB) 자동 다운로드.
               CPU에서도 동작하나 느림. 마스크 퇴화 시 자동 rect 폴백.
  auto       — GPU(cuda)와 segment-anything이 모두 있으면 sam, 아니면 rect.

핀 형식은 리뷰 팝업 JSON의 x_pct/y_pct 그대로: "x_pct,y_pct:교체할 정확한 문구".
붓 형식은 팝업이 저장한 마스크 경로 그대로: "마스크.png:교체할 정확한 문구".
원본은 절대 덮어쓰지 않는다 — 기본 출력은 <원본stem>-fixed.png (있으면 -2, -3…).
의존성: pip install easyocr opencv-python  (torch CPU 판이면 충분)
        붓만 쓸 때는 easyocr 불필요 — opencv-python + Pillow 면 된다.
"""
import argparse
import math
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgunbd.ttf",  # 배너류는 거의 볼드
    r"C:\Windows\Fonts\malgun.ttf",
]

# ── 보정 상수 (2026-07-31 실측·독립검수로 확정한 값 — 근거 없이 바꾸지 말 것) ──
INK_HEIGHT_RATIO = 0.6      # 글리프 잉크높이/검출박스높이. 실측 0.59~0.61
WIDTH_OVERFLOW = 1.25       # 긴 교체 문구의 박스 폭 초과 허용 배율 (박스 밖도 배경이므로)
COLOR_TOP_PERCENT = 90      # 글자색 추정에 쓸 "배경과 먼" 픽셀 백분위. 70이면 가장자리 섞여 탁해짐
SAM_FRAC_RANGE = (0.03, 0.85)  # SAM 마스크가 박스에서 차지하는 정상 비율. 밖이면 퇴화 → rect 폴백
INPAINT_RADIUS = 5
PIN_MATCH_SLACK = 20        # 핀-박스 매칭 여유(px): 박스높이×0.5 + 이 값

SAM_CKPT_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
SAM_CKPT = Path.home() / ".cache" / "repair_text" / "sam_vit_b_01ec64.pth"
_SAM_PREDICTOR = None


# ── 순수 함수 (selftest 대상 — 무거운 의존성 없음) ─────────────────────────────

def parse_pin(s):
    """'x_pct,y_pct:text' -> (float, float, str). 텍스트에 ':' 포함 가능."""
    coord, sep, text = s.partition(":")
    if not sep or not text.strip():
        raise ValueError(f"핀 형식 오류 (x,y:text): {s!r}")
    parts = coord.split(",")
    if len(parts) != 2:
        raise ValueError(f"핀 좌표는 'x,y' 두 개여야 함 (받은 값: {coord!r}) — 예: 62,88:문구")
    try:
        x, y = (float(v) for v in parts)
    except ValueError:
        raise ValueError(f"핀 좌표가 숫자가 아님: {coord!r} — 예: 62,88:문구") from None
    return x, y, text.strip()


def parse_mask_arg(s):
    """'경로:교체문구' -> (경로, 문구).

    Windows 드라이브 문자의 콜론(C:\\…)은 구분자로 보지 않는다. 문구 안의
    콜론("비율 10:1")은 첫 구분자 뒤라 그대로 살아남는다.
    """
    start = 2 if re.match(r"^[A-Za-z]:[\\/]", s) else 0
    i = s.find(":", start)
    if i < 0 or not s[i + 1:].strip():
        raise ValueError(f"붓 마스크 형식 오류 (경로:문구): {s!r}")
    return s[:i], s[i + 1:].strip()


def mask_to_rect(mask):
    """이진 마스크(2D 배열)에서 칠해진 픽셀의 bounding box -> (x0,y0,x1,y1).

    비어 있으면 None. x1/y1 은 quad_to_rect 와 같은 배타적 경계(슬라이스용).
    """
    import numpy as np

    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def quad_to_rect(quad):
    """OCR 사각형(4점) -> (x0,y0,x1,y1). mask_to_rect 와 같은 배타적 경계(+1).

    +1 이 없으면 검출 박스의 우/하단 1px 이 늘 잘린다. rect 엔진은 pad 가
    흡수하지만 sam 엔진은 이 값을 박스 프롬프트에 그대로 써서 정밀도가 깎인다.
    """
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1


def padded_rect(rect, pad, shape):
    """rect를 pad만큼 넓혀 이미지 경계 안으로 클램프."""
    h, w = shape
    x0, y0, x1, y1 = rect
    return max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)


def match_pin_to_box(px, py, rects):
    """핀 픽셀좌표가 속한 rect 인덱스. 없으면 가장자리 거리가 허용 내인 최근접, 그것도 없으면 None."""
    best, best_d, best_tol = None, None, 0
    for i, (x0, y0, x1, y1) in enumerate(rects):
        dx = max(x0 - px, 0, px - x1)
        dy = max(y0 - py, 0, py - y1)
        d = math.hypot(dx, dy)
        if d == 0:
            return i  # 내부
        if best_d is None or d < best_d:
            best, best_d, best_tol = i, d, 0.5 * (y1 - y0) + PIN_MATCH_SLACK
    if best is not None and best_d is not None and best_d <= best_tol:
        return best
    return None


def width_overflow_warning(idx, rendered_w, box_w):
    """렌더된 문구 폭이 WIDTH_OVERFLOW 허용치를 넘으면 경고 문자열, 아니면 None.

    rewrite_texts는 이미지 경계까지만 클램프하고 인접 박스는 모른다 — 여기서
    넘침을 알려야 사람/에이전트가 문구를 줄이는 판단을 할 수 있다.
    """
    if box_w <= 0 or rendered_w <= box_w * WIDTH_OVERFLOW:
        return None
    return f"box[{idx}] 교체 문구 폭이 원본 박스의 {rendered_w / box_w:.2f}배 — 인접 요소와 겹칠 수 있음 (문구를 줄이세요)"


def resolve_engine(choice, cuda_available, sam_installed):
    """auto: GPU와 segment-anything이 모두 있으면 sam, 아니면 rect. 명시 선택은 그대로."""
    if choice != "auto":
        return choice
    return "sam" if (cuda_available and sam_installed) else "rect"


# ── 이미지 헬퍼 (cv2/PIL 지연 임포트: --selftest 를 의존성 없이 돌리기 위함) ──────

def _require(mod_name, pip_name):
    """무거운 의존성을 함수 안에서 지연 임포트 — 미설치 시 raw traceback 대신 설치 안내.

    호출부마다 try/except를 반복하는 대신 한 곳에서 처리 (assemble_ppt.py의
    python-pptx 가드와 같은 톤).
    """
    import importlib

    try:
        return importlib.import_module(mod_name)
    except ImportError:
        sys.exit(f"{pip_name} 미설치 — pip install {pip_name}")


def load_bgr(path):
    cv2 = _require("cv2", "opencv-python")
    import numpy as np

    src = Path(path)
    if not src.is_file():
        sys.exit(f"파일 없음: {src}")
    img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"이미지 로드 실패: {src}")
    return src, img


def load_user_mask(path, shape):
    """붓 마스크 PNG -> 원본 크기 이진 마스크(0/255).

    팝업 canvas 해상도가 원본과 다를 수 있으므로 항상 원본 크기로 맞춘다.
    """
    cv2 = _require("cv2", "opencv-python")
    import numpy as np

    p = Path(path)
    if not p.is_file():
        sys.exit(f"마스크 파일 없음: {p}")
    m = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if m is None:
        sys.exit(f"마스크 로드 실패: {p}")
    h, w = shape
    if m.shape != (h, w):
        print(f"  마스크 크기 {m.shape[1]}x{m.shape[0]} → 원본 {w}x{h} 로 리샘플")
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
    return (m > 127).astype(np.uint8) * 255


def rect_mask(shape, rect, pad):
    """패딩 사각형을 255로 채운 마스크."""
    import numpy as np

    m = np.zeros(shape, dtype=np.uint8)
    x0, y0, x1, y1 = padded_rect(rect, pad, shape)
    m[y0:y1, x0:x1] = 255
    return m


def estimate_text_color(img, rect):
    """inpaint 전에 원 글자색 추정: 박스 주변 링=배경, 배경에서 먼 상위 픽셀=글자."""
    import numpy as np

    x0, y0, x1, y1 = rect
    pad = max(4, (y1 - y0) // 3)
    rx0, ry0, rx1, ry1 = padded_rect(rect, pad, img.shape[:2])
    region = img[ry0:ry1, rx0:rx1].astype(np.float32)
    mask_inner = np.zeros(region.shape[:2], dtype=bool)
    mask_inner[y0 - ry0 : y1 - ry0, x0 - rx0 : x1 - rx0] = True
    ring = region[~mask_inner]
    inner = region[mask_inner]
    if len(ring) == 0 or len(inner) == 0:
        return (255, 255, 255)
    bg = np.median(ring, axis=0)
    dist = np.linalg.norm(inner - bg, axis=1)
    top = inner[dist >= np.percentile(dist, COLOR_TOP_PERCENT)]
    if len(top) == 0:
        return (255, 255, 255)
    color = np.median(top, axis=0)  # BGR
    return tuple(int(c) for c in color[::-1])  # -> RGB


def fit_font(text, box_w, box_h, font_path):
    """잉크높이를 박스높이×INK_HEIGHT_RATIO에 맞추는 최대 크기 폰트."""
    from PIL import ImageFont

    size = max(10, int(box_h * 1.3))
    while size > 8:
        font = ImageFont.truetype(font_path, size)
        bb = font.getbbox(text)
        if bb[3] - bb[1] <= box_h * INK_HEIGHT_RATIO and bb[2] - bb[0] <= box_w * WIDTH_OVERFLOW:
            return font
        size -= 2
    return ImageFont.truetype(font_path, 8)


# ── SAM (상위 마스크 엔진) ──────────────────────────────────────────────────────

def _get_sam_predictor():
    global _SAM_PREDICTOR
    if _SAM_PREDICTOR is None:
        torch = _require("torch", "torch")
        sam_pkg = _require("segment_anything", "segment-anything")
        SamPredictor, sam_model_registry = sam_pkg.SamPredictor, sam_pkg.sam_model_registry

        SAM_CKPT.parent.mkdir(parents=True, exist_ok=True)
        if not SAM_CKPT.is_file():
            print(f"SAM vit_b 체크포인트 다운로드 중 (375MB) → {SAM_CKPT}")
            import urllib.request

            urllib.request.urlretrieve(SAM_CKPT_URL, str(SAM_CKPT))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        sam = sam_model_registry["vit_b"](checkpoint=str(SAM_CKPT)).to(device)
        _SAM_PREDICTOR = SamPredictor(sam)
    return _SAM_PREDICTOR


def predict_glyph_mask(predictor, rect, pad, shape):
    """SAM box 프롬프트로 획 단위 마스크. 퇴화면 None → 호출부가 rect 폴백."""
    cv2 = _require("cv2", "opencv-python")
    import numpy as np

    x0, y0, x1, y1 = rect
    masks, scores, _ = predictor.predict(box=np.array([x0, y0, x1, y1]), multimask_output=True)
    m = masks[int(np.argmax(scores))].astype(np.uint8) * 255
    frac = (m[y0:y1, x0:x1] > 0).sum() / max((x1 - x0) * (y1 - y0), 1)
    lo, hi = SAM_FRAC_RANGE
    if not (lo <= frac <= hi):
        return None
    k = max(3, pad) | 1  # 홀수 커널: 안티앨리어싱 가장자리 커버
    m = cv2.dilate(m, np.ones((k, k), np.uint8))
    return cv2.bitwise_and(m, rect_mask(shape, rect, pad))


# ── 수리 단계 ──────────────────────────────────────────────────────────────────

def detect_text_boxes(img, use_gpu):
    """easyocr(CRAFT)로 텍스트 박스 전부 검출. (배열을 넘긴다 — cv2.imread는 한글 경로 불가)"""
    print("텍스트 박스 검출 중 (easyocr/CRAFT, %s)…" % ("GPU" if use_gpu else "CPU"))
    easyocr = _require("easyocr", "easyocr")

    reader = easyocr.Reader(["ko", "en"], gpu=use_gpu, verbose=False)
    results = reader.readtext(img)
    rects = [quad_to_rect(r[0]) for r in results]
    for i, (rect, r) in enumerate(zip(rects, results)):
        print(f"  box[{i}] {rect}  OCR={r[1]!r}  conf={r[2]:.2f}")
    return rects


def assign_pins(pins, rects, img):
    """핀 → 박스 매칭. 박스당 문구 1개 (중복 핀은 나중 것이 경고와 함께 대체)."""
    h, w = img.shape[:2]
    jobs = {}
    for x_pct, y_pct, text in pins:
        idx = match_pin_to_box(x_pct / 100 * w, y_pct / 100 * h, rects)
        if idx is None:
            sys.exit(f"핀({x_pct},{y_pct})이 속한 텍스트 박스 없음 — 위 box 목록 좌표 참고")
        if idx in jobs:
            print(f"경고: box[{idx}]에 핀 중복 — {jobs[idx][0]!r} 대신 {text!r} 적용")
        jobs[idx] = (text, estimate_text_color(img, rects[idx]))
    return jobs


def build_mask(img, rects, jobs, engine, user_masks=None):
    """선택 박스들의 inpaint 마스크.

    붓으로 칠한 영역(user_masks)은 사용자가 이미 정확히 지정한 것이므로
    SAM/사각형 추정을 거치지 않고 그대로 쓴다.
    """
    cv2 = _require("cv2", "opencv-python")
    import numpy as np

    user_masks = user_masks or {}
    h, w = img.shape[:2]
    # 붓 영역만 있으면 SAM 을 띄울 이유가 없다 (체크포인트 375MB 로딩 회피)
    need_engine = any(idx not in user_masks for idx in jobs)
    predictor = _get_sam_predictor() if (engine == "sam" and need_engine) else None
    if predictor is not None:
        predictor.set_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))  # 인코딩 1회, 박스별 predict
    mask = np.zeros((h, w), dtype=np.uint8)
    for idx in jobs:
        if idx in user_masks:
            print(f"  box[{idx}] 붓 마스크 그대로 적용")
            mask = cv2.bitwise_or(mask, user_masks[idx])
            continue
        y0, y1 = rects[idx][1], rects[idx][3]
        pad = max(3, (y1 - y0) // 4)  # 안티앨리어싱 잔여 커버
        m = predict_glyph_mask(predictor, rects[idx], pad, (h, w)) if predictor else None
        if m is None:
            if predictor is not None:
                print(f"  box[{idx}] SAM 마스크 퇴화 → 사각형 폴백")
            m = rect_mask((h, w), rects[idx], pad)
        else:
            print(f"  box[{idx}] SAM 획 마스크 적용")
        mask = cv2.bitwise_or(mask, m)
    return mask


def rewrite_texts(fixed_bgr, rects, jobs, font_path):
    """inpaint된 이미지 위에 실폰트로 교체 문구 재기입 (박스 중앙 정렬)."""
    cv2 = _require("cv2", "opencv-python")
    from PIL import Image, ImageDraw

    w = fixed_bgr.shape[1]
    pil = Image.fromarray(cv2.cvtColor(fixed_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    for idx, (text, color) in jobs.items():
        x0, y0, x1, y1 = rects[idx]
        font = fit_font(text, x1 - x0, y1 - y0, font_path)
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
        warn = width_overflow_warning(idx, tw, x1 - x0)
        if warn:
            print(f"  경고: {warn}")
        tx = x0 + ((x1 - x0) - tw) / 2 - bb[0]
        tx = min(max(tx, 4), w - tw - 4)  # 폭 넘침 허용분을 이미지 경계 안으로 클램프
        ty = y0 + ((y1 - y0) - (bb[3] - bb[1])) / 2 - bb[1]
        draw.text((tx, ty), text, font=font, fill=color)
        print(f"  box[{idx}] <- {text!r} color={color} font={Path(font_path).name}@{font.size}")
    return pil


def next_out_path(src, out_path):
    """수정본은 항상 새 파일 (원본·기존 파일 덮어쓰기 금지)."""
    if out_path is not None:
        out = Path(out_path)
        if out.exists():
            sys.exit(f"출력 파일이 이미 존재: {out} (덮어쓰기 금지)")
        return out
    out = src.with_name(src.stem + "-fixed.png")
    n = 2
    while out.exists():
        out = src.with_name(f"{src.stem}-fixed-{n}.png")
        n += 1
    return out


FLAT_TOL = 6.0     # 주변 링의 채널별 표준편차가 이 이하면 "단색"으로 본다
RING_PX = 25       # 배경 판정에 쓰는 마스크 바깥 링의 두께


def ring_stats(img, mask, ring_px=RING_PX):
    """마스크 바로 바깥 링의 (표준편차 최대, 중앙값). 링이 비면 (None, None)."""
    cv2 = _require("cv2", "opencv-python")
    import numpy as np

    ring = cv2.dilate(mask, np.ones((ring_px, ring_px), np.uint8)) - mask
    px = img[ring > 0]
    if len(px) == 0:
        return None, None
    return float(px.std(axis=0).max()), np.median(px, axis=0)


def restore_background(img, mask, fill="auto"):
    """마스크 영역의 배경을 복원. -> (이미지, 사용한 방식)

    단색 배경에서는 cv2.inpaint 가 채널당 최대 ±7/255 를 남긴다 — 그게 실측된
    "옅은 사각 자국"이다. 주변이 균일하면 그 색으로 그냥 채우는 게 오차 0 이다.
    배경이 복잡하면 단색 채우기가 오히려 판을 깨므로 inpaint 로 넘긴다.
    """
    cv2 = _require("cv2", "opencv-python")

    if fill != "inpaint":
        std, med = ring_stats(img, mask)
        if std is not None and (fill == "solid" or std <= FLAT_TOL):
            out = img.copy()
            out[mask > 0] = med.astype(img.dtype)
            return out, f"단색 채우기 (주변 편차 {std:.1f})"
        if fill == "solid":
            return img.copy(), "단색 채우기 불가(링 없음) — 원본 유지"
    fixed = cv2.inpaint(img, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)
    std, _ = ring_stats(img, mask)
    detail = f"주변 편차 {std:.1f}" if std is not None else "링 없음"
    return fixed, f"cv2.inpaint ({detail}) — 복잡한 배경은 자국이 남을 수 있음"


def repair(img_path, pins, masks=None, out_path=None, font_path=None, engine="auto",
           fill="auto"):
    cv2 = _require("cv2", "opencv-python")

    masks = masks or []
    src, img = load_bgr(img_path)
    font_path = font_path or next((f for f in FONT_CANDIDATES if Path(f).is_file()), None)
    if not font_path:
        sys.exit("맑은 고딕 폰트를 찾지 못함 — --font 로 ttf 경로 지정")

    rects, jobs, user_masks = [], {}, {}

    # 붓 영역: 사용자가 직접 칠했으므로 OCR 없이 바로 확정
    for mpath, text in masks:
        m = load_user_mask(mpath, img.shape[:2])
        rect = mask_to_rect(m)
        if rect is None:
            sys.exit(f"빈 마스크 (칠해진 픽셀이 없음): {mpath}")
        idx = len(rects)
        rects.append(rect)
        user_masks[idx] = m
        jobs[idx] = (text, estimate_text_color(img, rect))
        print(f"  붓[{idx}] rect={rect} <- {text!r}")

    # 핀이 있을 때만 OCR + 엔진 판정 (붓 전용 실행에서 easyocr·torch 로딩 회피)
    if pins:
        torch = _require("torch", "torch")

        try:
            import segment_anything  # noqa: F401

            has_sam = True
        except ImportError:
            has_sam = False
        use_gpu = torch.cuda.is_available()
        engine = resolve_engine(engine, use_gpu, has_sam)
        if engine == "sam" and not has_sam:
            sys.exit("--engine sam: segment-anything 미설치 — pip install segment-anything")
        print(f"마스크 엔진: {engine} ({'GPU' if use_gpu else 'CPU'})")

        ocr_rects = detect_text_boxes(img, use_gpu)
        base = len(rects)                      # 붓 영역 뒤에 이어붙인다
        rects.extend(ocr_rects)
        for i, v in assign_pins(pins, ocr_rects, img).items():
            jobs[base + i] = v

    mask = build_mask(img, rects, jobs, engine, user_masks)
    fixed, how = restore_background(img, mask, fill)
    print(f"배경 복원: {how}")
    pil = rewrite_texts(fixed, rects, jobs, font_path)

    out = next_out_path(src, out_path)
    pil.save(str(out))
    print(f"저장: {out}")
    return out


# ── 자기점검 · CLI ─────────────────────────────────────────────────────────────

def selftest():
    assert parse_pin("62,88:내비온 기술연구소") == (62.0, 88.0, "내비온 기술연구소")
    assert parse_pin("5,5:비율 10:1 유지")[2] == "비율 10:1 유지"
    for bad in ("62:문구", "1,2,3:문구", "a,b:문구"):
        try:
            parse_pin(bad)
            raise AssertionError(f"거부되어야 함: {bad}")
        except ValueError:
            pass
    # 두 rect 변환의 경계 규약이 같아야 한다 (sam 박스 프롬프트가 이 값을 그대로 쓴다)
    assert quad_to_rect([(10, 20), (30, 20), (30, 40), (10, 40)]) == (10, 20, 31, 41)
    rects = [(100, 100, 300, 150), (400, 400, 600, 450)]
    assert match_pin_to_box(200, 125, rects) == 0      # 내부
    assert match_pin_to_box(310, 125, rects) == 0      # 근접
    assert match_pin_to_box(1000, 1000, rects) is None  # 원거리
    assert resolve_engine("auto", True, True) == "sam"
    assert resolve_engine("auto", False, True) == "rect"
    assert resolve_engine("auto", True, False) == "rect"
    assert resolve_engine("rect", True, True) == "rect"
    assert resolve_engine("sam", False, False) == "sam"  # 명시 선택 존중 (미설치는 실행부에서 안내)
    assert padded_rect((10, 10, 50, 30), 5, (100, 200)) == (5, 5, 55, 35)
    assert padded_rect((2, 2, 198, 98), 5, (100, 200)) == (0, 0, 200, 100)  # 경계 클램프
    assert quad_to_rect([[10, 20], [50, 18], [52, 40], [9, 42]]) == (9, 18, 53, 43)

    # 붓 마스크 인자: Windows 드라이브 콜론은 구분자가 아니다
    assert parse_mask_arg(r"C:\tmp\m1.png:내비온") == (r"C:\tmp\m1.png", "내비온")
    assert parse_mask_arg("D:/x/m.png:비율 10:1 유지") == ("D:/x/m.png", "비율 10:1 유지")
    assert parse_mask_arg("mask_1.png:제목") == ("mask_1.png", "제목")
    assert parse_mask_arg("./sub/m.png:  공백 정리  ")[1] == "공백 정리"
    for bad in ("m.png", "m.png:", r"C:\tmp\m.png"):
        try:
            parse_mask_arg(bad)
            raise AssertionError(f"거부했어야 함: {bad!r}")
        except ValueError:
            pass

    # 붓 마스크 bbox: 칠해진 픽셀만 감싸고, 빈 마스크는 None
    import numpy as np

    m = np.zeros((100, 200), dtype=np.uint8)
    m[30:41, 50:71] = 255
    assert mask_to_rect(m) == (50, 30, 71, 41), mask_to_rect(m)
    assert mask_to_rect(np.zeros((10, 10), dtype=np.uint8)) is None
    single = np.zeros((10, 10), dtype=np.uint8)
    single[5, 7] = 255
    assert mask_to_rect(single) == (7, 5, 8, 6)   # 1픽셀도 폭 0 이 되면 안 된다

    # WIDTH_OVERFLOW 경고: 허용 배율(1.25) 이내는 조용히, 넘으면 box 번호+배율을 알림
    assert width_overflow_warning(0, 100, 100) is None       # 원본과 동일
    assert width_overflow_warning(0, 124, 100) is None       # 허용 범위 내
    w = width_overflow_warning(2, 130, 100)
    assert w is not None and "box[2]" in w and "1.30" in w
    assert width_overflow_warning(0, 999, 0) is None          # 폭 0 방어 (분모 0 회피)
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", nargs="?", help="수리할 이미지 경로")
    ap.add_argument("--pin", action="append", default=[], help='"x_pct,y_pct:교체 문구" (반복 가능)')
    ap.add_argument("--mask", action="append", default=[],
                    help='붓 마스크 "경로.png:교체 문구" (반복 가능, --pin 과 병용 가능)')
    ap.add_argument("-o", "--out", help="출력 경로 (기본: <stem>-fixed.png)")
    ap.add_argument("--font", help="ttf 경로 (기본: 맑은 고딕 볼드)")
    ap.add_argument("--engine", choices=["auto", "rect", "sam"], default="auto",
                    help="마스크 엔진 (auto: GPU+sam 설치 시 sam, 아니면 rect). --pin 경로에만 적용")
    ap.add_argument("--fill", choices=["auto", "solid", "inpaint"], default="auto",
                    help="배경 복원 (auto: 주변이 단색이면 그 색으로 채우고 아니면 inpaint). "
                         "단색 배경에서 inpaint 는 옅은 사각 자국을 남긴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.image or not (a.pin or a.mask):
        ap.error("image 와 --pin 또는 --mask 가 필요합니다 (--selftest 제외)")
    repair(a.image, [parse_pin(p) for p in a.pin], [parse_mask_arg(m) for m in a.mask],
           a.out, a.font, a.engine, a.fill)


if __name__ == "__main__":
    main()
