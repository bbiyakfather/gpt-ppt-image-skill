#!/usr/bin/env python3
"""붓 마스크 좌표 수학의 자동 점검 — review_server.py 브라우저 로직의 포트.

review_server.py의 붓(brush) 도구는 화면 표시 크기(display) 기준으로 정규화한
0..1 좌표를 저장했다가, 제출 시 이미지의 원본 해상도(natural)로 다시 래스터화한다
(HTML <script> 안의 pos()/paintStrokes()/maskPNG()). 이 변환이 틀리면 도구가
**엉뚱한 영역**을 "성공적으로" 수리한다 — 조용히, 티 안 나게. 그런데 그 로직이
인라인 <script> 안에 있어서 지금까지 자동 커버리지가 0이었다.

이 스크립트는 그 수학만 파이썬(PIL/numpy)으로 포팅해, 작은 display 크기에서 그린
획이 훨씬 큰(비정방 비율 포함) natural 크기로 재래스터화됐을 때 기대한 픽셀 박스에
정확히 떨어지는지 확인한다.

**중요 — 이것은 브라우저 로직의 포트다.** review_server.py의 HTML <script>
(pos/paintStrokes/maskPNG)가 바뀌면 이 파일도 같이 바꿔야 한다. 이 테스트는
좌표 수학만 지킨다 — pointerdown/이벤트 배선, canvas 실제 렌더링, 멀티터치
등 브라우저 쪽 배선은 전혀 검증하지 않는다.

사용:
  python test_coords.py             # 좌표 수학 점검 실행
  python test_coords.py --selftest  # 위와 동일 (다른 스크립트들과 이름 통일)
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_text import mask_to_rect  # noqa: E402  (bbox 계산은 기존 함수 재사용)


# ── review_server.py HTML <script> 포트 (pos / paintStrokes) ───────────────────
# 원본: scripts/review_server.py 의 HTML 문자열 안 pos(), paintStrokes() 함수.

def pos_norm(client_x, client_y, rect_w, rect_h):
    """pos(ev)의 포트: 캔버스 위 클릭 좌표 -> 0..1 정규화.

    JS: (ev.clientX-r.left)/r.width, (ev.clientY-r.top)/r.height
    원점(rect.left/top)은 0으로 고정해도 스케일 검증에는 영향 없다.
    """
    return client_x / rect_w, client_y / rect_h


def brush_radius_norm(brush_px, canvas_w):
    """pointerdown 핸들러 안 반경 계산의 포트: bsize.value / pc.width / 2.

    반경은 그린 시점의 display 캔버스 '폭'에만 대해 정규화된다 (높이 아님) —
    이 비대칭이 실제 JS의 동작이고, 아래 raster_natural()에서 그대로 재현한다.
    """
    return brush_px / canvas_w / 2


def paint_strokes(draw, w, h, strokes, fill):
    """paintStrokes(ctx, w, h, strokes, style)의 포트.

    각 stroke = {"pts": [[x,y], ...] (0..1 정규화), "r": 반경(0..1 정규화)}.
    lineWidth = r*2*w 로, 폭 스케일 기준은 항상 raster 대상의 '폭'(w)이다 — 세로가
    다른 비율이어도 h로 다시 나누지 않는다 (JS 원본 그대로).
    점 1개짜리 stroke는 원 하나, 그 이상은 선 + 양끝에 원(ctx의 round cap 재현).
    """
    for s in strokes:
        pts = s["pts"]
        r = s["r"]
        lw = max(1, r * 2 * w)
        rad = lw / 2
        if len(pts) == 1:
            cx, cy = pts[0][0] * w, pts[0][1] * h
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=fill)
            continue
        coords = [(p[0] * w, p[1] * h) for p in pts]
        draw.line(coords, fill=fill, width=max(1, int(round(lw))))
        for cx, cy in (coords[0], coords[-1]):  # lineCap='round' 재현
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=fill)


def raster_natural(strokes, natural_w, natural_h):
    """maskPNG(i, rg)의 포트: 검은 배경 캔버스에 흰 stroke -> numpy 마스크(0/255)."""
    import numpy as np
    from PIL import Image, ImageDraw

    img = Image.new("L", (natural_w, natural_h), 0)
    draw = ImageDraw.Draw(img)
    paint_strokes(draw, natural_w, natural_h, strokes, fill=255)
    return np.array(img)


# ── 기대값 계산 (테스트 전용 — 포트 대상 아님) ──────────────────────────────────

def expected_bbox(x0, y0, x1, y1, r, natural_w, natural_h):
    """정규화 bbox(선분 양끝)를 natural 해상도로 스케일 + round-cap 반경 패딩.

    paint_strokes와 동일하게 반경은 natural_w 기준으로만 계산한다.
    """
    lw = max(1, r * 2 * natural_w)
    rad = lw / 2
    ex0 = min(x0, x1) * natural_w - rad
    ey0 = min(y0, y1) * natural_h - rad
    ex1 = max(x0, x1) * natural_w + rad
    ey1 = max(y0, y1) * natural_h + rad
    return ex0, ey0, ex1, ey1


def assert_close(actual, expected, tol, label):
    for a, e, name in zip(actual, expected, ("x0", "y0", "x1", "y1")):
        assert abs(a - e) <= tol, f"{label} {name}: actual={a} expected={e} (tol={tol})"


# ── 시나리오: display에서 그리고 natural에서 래스터화 ──────────────────────────

def paint_at_display_and_raster_at_natural(display_xy0, display_xy1, brush_px,
                                            display_w, display_h, natural_w, natural_h):
    """display 픽셀 좌표로 선을 하나 그린 뒤, natural 해상도로 재래스터화.

    review_server.py의 실제 흐름 그대로: pointerdown/move에서 pos()로 정규화한
    좌표와 반경을 저장해뒀다가(display 기준), 제출 시 maskPNG가 naturalWidth/
    Height로 다시 그린다(natural 기준) — 두 단계를 분리해서 재현한다.
    """
    (x0, y0), (x1, y1) = display_xy0, display_xy1
    nx0, ny0 = pos_norm(x0, y0, display_w, display_h)
    nx1, ny1 = pos_norm(x1, y1, display_w, display_h)
    r = brush_radius_norm(brush_px, display_w)
    stroke = {"pts": [[nx0, ny0], [nx1, ny1]], "r": r}

    mask = raster_natural([stroke], natural_w, natural_h)
    x0e, y0e, x1e, y1e = mask_to_rect(mask)  # 배타적 상단 경계 (repair_text.py와 동일 규약)
    expected = expected_bbox(nx0, ny0, nx1, ny1, r, natural_w, natural_h)
    return (x0e, y0e, x1e, y1e), expected


def run_checks():
    cases = [
        # (라벨, display_w, display_h, natural_w, natural_h, 시작, 끝, 붓폭px)
        ("4:3 -> 4:3, 4배 확대", 400, 300, 1600, 1200, (50, 50), (350, 250), 20),
        ("정방형 display -> 16:9 natural (비정방 확대)", 500, 500, 1920, 1080, (100, 400), (450, 60), 24),
        ("세로형 display -> 세로형 natural, 세로/가로 배율 다름", 300, 600, 900, 1600, (30, 550), (270, 20), 12),
        ("작은 소형 스케치 -> 초고해상도", 120, 90, 4000, 3000, (10, 10), (110, 80), 8),
    ]
    for label, dw, dh, nw, nh, p0, p1, brush in cases:
        actual, expected = paint_at_display_and_raster_at_natural(p0, p1, brush, dw, dh, nw, nh)
        assert_close(actual, expected, tol=1.0, label=label)
        print(f"  OK  {label}: display {dw}x{dh} -> natural {nw}x{nh}  bbox={tuple(round(v) for v in actual)}")

    # 점 하나짜리 stroke (단일 클릭) 도 커버 — paint_strokes의 len(pts)==1 분기
    display_w, display_h, natural_w, natural_h = 300, 300, 3000, 1500
    px, py, brush = 150, 90, 16
    nx, ny = pos_norm(px, py, display_w, display_h)
    r = brush_radius_norm(brush, display_w)
    mask = raster_natural([{"pts": [[nx, ny]], "r": r}], natural_w, natural_h)
    actual = mask_to_rect(mask)
    expected = expected_bbox(nx, ny, nx, ny, r, natural_w, natural_h)
    assert_close(actual, expected, tol=1.0, label="단일 클릭(점) -> 비정방 natural")
    print(f"  OK  단일 클릭(점) -> 비정방 natural: bbox={tuple(round(v) for v in actual)}")

    # 회귀 가드: display 크기를 무시하고 natural 크기로 잘못 나누면(버그 재현) 어긋나야 한다
    # (이 assert_close가 통과해버리면 tol이 너무 헐거워 진짜 버그를 놓친다는 뜻)
    wrong_r = brush_radius_norm(brush, natural_w)  # 틀린 기준(자연 폭)으로 계산
    mask_wrong = raster_natural([{"pts": [[nx, ny]], "r": wrong_r}], natural_w, natural_h)
    actual_wrong = mask_to_rect(mask_wrong)
    try:
        assert_close(actual_wrong, expected, tol=1.0, label="회귀 가드")
    except AssertionError:
        pass  # 기대대로 불일치 -> 가드가 살아있음
    else:
        raise AssertionError("반경 기준을 틀리게 잡았는데도 일치함 — tol이 헐거워 가드가 무력함")
    print("  OK  회귀 가드: 반경 기준을 틀리면 실제로 불일치가 잡힘")


def selftest():
    run_checks()
    print("selftest OK")


def main():
    if "--selftest" in sys.argv[1:]:
        selftest()
        return 0
    run_checks()
    print("좌표 수학 점검 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
