#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한글 폰트 팔레트 설치기 — assets/fonts/ 에 다운로드하고 fonts.css 를 생성한다.

사용법: python setup_fonts.py          (이미 받은 파일은 건너뜀)
        python setup_fonts.py --force  (전부 다시 다운로드)

팔레트: NanumSquare(400/700/800) · Gmarket Sans(300/500=normal/700) ·
        KoPub Dotum(300/500=normal/700) · Noto Sans KR(가변 100-900) · 맑은 고딕(시스템)
"""
import sys
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# (파일명, URL, css family, font-weight 선언)
DOWNLOADS = [
    ("NanumSquareR.ttf", "https://raw.githubusercontent.com/moonspam/NanumSquare/master/NanumSquareR.ttf", "NanumSquare", "400"),
    ("NanumSquareB.ttf", "https://raw.githubusercontent.com/moonspam/NanumSquare/master/NanumSquareB.ttf", "NanumSquare", "700"),
    ("NanumSquareEB.ttf", "https://raw.githubusercontent.com/moonspam/NanumSquare/master/NanumSquareEB.ttf", "NanumSquare", "800"),
    ("GmarketSansLight.woff", "https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansLight.woff", "Gmarket Sans", "300"),
    ("GmarketSansMedium.woff", "https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansMedium.woff", "Gmarket Sans", "400"),
    ("GmarketSansBold.woff", "https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff", "Gmarket Sans", "700"),
    ("KoPubDotumLight.ttf", "https://raw.githubusercontent.com/webfont-kr/KoPubDotum/master/fonts/KoPubDotumLight.ttf", "KoPub Dotum", "300"),
    ("KoPubDotumMedium.ttf", "https://raw.githubusercontent.com/webfont-kr/KoPubDotum/master/fonts/KoPubDotumMedium.ttf", "KoPub Dotum", "400"),
    ("KoPubDotumBold.ttf", "https://raw.githubusercontent.com/webfont-kr/KoPubDotum/master/fonts/KoPubDotumBold.ttf", "KoPub Dotum", "700"),
    ("NotoSansKR-Variable.ttf", "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf", "Noto Sans KR", "100 900"),
]

MIN_SIZE = 50_000  # 폰트 파일 최소 크기(바이트) — 오류 페이지 다운로드 방지


def main():
    force = "--force" in sys.argv
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    css = ["/* setup_fonts.py 가 생성 — 직접 수정 금지 */"]
    failed = []
    for name, url, family, weight in DOWNLOADS:
        dest = FONTS_DIR / name
        if force or not dest.exists() or dest.stat().st_size < MIN_SIZE:
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                failed.append(f"{name}: {e}")
                continue
        if dest.stat().st_size < MIN_SIZE:
            failed.append(f"{name}: 파일이 너무 작음({dest.stat().st_size}B) — URL 확인 필요")
            dest.unlink(missing_ok=True)
            continue
        fmt = "woff" if name.endswith(".woff") else "truetype"
        css.append(
            f"@font-face {{ font-family:'{family}'; font-weight:{weight}; "
            f"src:url('{name}') format('{fmt}'); }}"
        )
    (FONTS_DIR / "fonts.css").write_text("\n".join(css) + "\n", encoding="utf-8")
    ok = len(DOWNLOADS) - len(failed)
    print(f"fonts: {ok}/{len(DOWNLOADS)} OK → {FONTS_DIR}")
    for f in failed:
        print("FAIL:", f)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
