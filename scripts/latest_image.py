#!/usr/bin/env python3
"""생성기(codex·grok)의 런타임 홈에서 방금 만든 생성물을 찾는다 — gpt-ppt-image 4단계 보조 도구.

생성기가 결과물을 목적지로 복사하는 단계는 환경마다 깨진다. 그래도 이미지 자체는
런타임 홈에 남으므로 그걸 회수한다. 문제는 그 경로가 버전·세션마다 바뀐다는 것.
실측 전례:
  codex 0.144.1  codex-runtime-home/home/generated_images/
  codex 0.144.6  codex-accounts/<uuid>/home/generated_images/
  codex 0.145.0  위 두 곳 모두 비거나 낡음. ~/.codex/generated_images/ 사용
  grok  1.0.5    ~/.grok/sessions/<URL인코딩된 cwd>/<세션UUID>/images/N.jpg
                 (복사 단계는 경로가 Windows MAX_PATH 260자를 넘으면 실패한다)

경로만 갈아끼우는 건 증상 치료였다. 진짜 문제는 "최신 PNG"라는 휴리스틱이
**조용히 틀린다**는 것 — 낡은 경로에 예전 생성물이 남아 있으면 9일 전 이미지를
"방금 생성물"이라며 복사한다. 그래서 이 스크립트는 신선도를 하드 게이트로 건다:
기준 시각보다 오래된 후보는 반환하지 않고 실패한다.

사용:
  # 생성 직전에 기준 시각을 찍어두고
  T0=$(python latest_image.py --now)
  codex exec ...
  # 그 뒤에 만들어진 것만 받는다
  python latest_image.py --since "$T0" --copy-to gpt-image/hero.png

  python latest_image.py --max-age 300        # 최근 5분 내 생성물만
  python latest_image.py --list               # 루트별 최신 시각 진단
  python latest_image.py --selftest

종료 코드: 0 성공 / 1 조건에 맞는 생성물 없음 (조용히 낡은 걸 주느니 실패한다)
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

# Windows 콘솔 기본 인코딩(cp949)에서 한글 출력이 깨진다 — 다른 스크립트와 동일 처리.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 알려진 런타임 홈들. 새 경로가 생기면 여기만 고친다.
# 각 항목은 홈 디렉터리 기준 glob 패턴.
ROOT_GLOBS = [
    ".codex/generated_images",
    "AppData/Roaming/orca/codex-accounts/*/home/generated_images",
    "AppData/Roaming/orca/codex-runtime-home/home/generated_images",
    ".config/orca/codex-accounts/*/home/generated_images",
    ".config/orca/codex-runtime-home/home/generated_images",
    ".grok/sessions/*/*/images",
]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MAX_AGE = 600.0  # 초. 생성 직후 회수가 전제라 넉넉히 10분.
_UNSET = object()  # "환경변수를 읽어라"와 "무시하라(None)"를 구분하기 위한 센티널


def candidate_roots(home=None, codex_home=_UNSET, grok_home=_UNSET):
    """실재하는 생성물 루트들을 반환. CODEX_HOME·GROK_HOME이 있으면 우선 포함.

    codex_home/grok_home 을 명시하면 환경변수 대신 그 값을 쓴다
    (None 이면 무시 — selftest 격리용).
    """
    home = Path(home) if home else Path.home()
    roots = []
    for var, sub, override in (("CODEX_HOME", "generated_images", codex_home),
                               ("GROK_HOME", "sessions/*/*/images", grok_home)):
        env = os.environ.get(var) if override is _UNSET else override
        if not env:
            continue
        for p in sorted(Path(env).glob(sub)):
            if p.is_dir() and p not in roots:
                roots.append(p)
    for pattern in ROOT_GLOBS:
        for p in sorted(home.glob(pattern)):
            if p.is_dir() and p not in roots:
                roots.append(p)
    return roots


def scan(roots):
    """모든 루트의 이미지를 (mtime, path) 리스트로. 최신순 정렬."""
    found = []
    for root in roots:
        for p in root.rglob("*"):
            if p.suffix.lower() in IMAGE_EXTS and p.is_file():
                try:
                    found.append((p.stat().st_mtime, p))
                except OSError:
                    continue
    found.sort(key=lambda t: t[0], reverse=True)
    return found


def pick_fresh(found, since):
    """since(epoch) 이후 생성물 중 최신 1개. 없으면 None."""
    for mtime, path in found:
        if mtime >= since:
            return mtime, path
    return None


def _fmt(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def diagnose(roots, found, since, out=sys.stderr):
    """왜 못 찾았는지 루트별로 보여준다 — 조용한 실패를 만들지 않기 위해."""
    if not roots:
        print("런타임 홈을 하나도 못 찾음. codex가 설치·실행된 적이 있는지 확인.", file=out)
        print("탐색한 패턴:", file=out)
        for g in ROOT_GLOBS:
            print(f"  ~/{g}", file=out)
        return
    print(f"기준 시각 {_fmt(since)} 이후 생성물 없음. 루트별 최신:", file=out)
    for root in roots:
        newest = max((m for m, p in found if root in p.parents or p.parent == root),
                     default=None)
        if newest is None:
            print(f"  (비어 있음)  {root}", file=out)
        else:
            age = (time.time() - newest) / 3600.0
            print(f"  {_fmt(newest)}  ({age:.1f}시간 전)  {root}", file=out)
    print("\n생성기가 실제로 저장한 경로를 먼저 확인할 것 (codex: `-o` 출력 / grok: 마지막 줄).", file=out)


def selftest():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        root = home / ".codex" / "generated_images" / "sess"
        root.mkdir(parents=True)
        old, new = root / "old.png", root / "new.png"
        old.write_bytes(b"x")
        new.write_bytes(b"y")
        now = time.time()
        os.utime(old, (now - 9 * 86400, now - 9 * 86400))  # 9일 전 (실측된 사고 재현)
        os.utime(new, (now - 10, now - 10))                # 10초 전

        # *_home=None 으로 실환경 CODEX_HOME/GROK_HOME 을 차단해야 격리가 된다
        roots = candidate_roots(home, codex_home=None, grok_home=None)
        assert roots == [root.parent], roots
        found = scan(roots)
        assert len(found) == 2, found

        # 신선도 게이트가 낡은 것을 거른다 — 이 스크립트의 존재 이유
        hit = pick_fresh(found, now - 60)
        assert hit and hit[1] == new, hit
        # 기준보다 모두 낡으면 조용히 주지 않고 None
        assert pick_fresh(found, now - 5) is None
        # 게이트를 9일보다 넓게 잡으면 그제야 낡은 것도 후보
        assert pick_fresh(found, now - 10 * 86400)[1] == new

        # 확장자 필터
        (root / "note.txt").write_bytes(b"z")
        assert len(scan(roots)) == 2

        # grok 세션 이미지도 같은 게이트로 잡힌다 (경로가 세션마다 다르고 확장자가 .jpg)
        gimg = home / ".grok" / "sessions" / "F%3A%5Ctmp%5Cgk" / "01a038c0-uuid" / "images"
        gimg.mkdir(parents=True)
        gjpg = gimg / "1.jpg"
        gjpg.write_bytes(b"g")
        os.utime(gjpg, (now - 5, now - 5))  # codex 생성물보다 5초 신선

        roots2 = candidate_roots(home, codex_home=None, grok_home=None)
        assert gimg in roots2, roots2
        assert pick_fresh(scan(roots2), now - 60)[1] == gjpg

        # 낡은 grok 생성물은 여전히 주지 않는다 — 엔진이 늘어도 게이트는 같다
        os.utime(gjpg, (now - 9 * 86400, now - 9 * 86400))
        assert pick_fresh(scan(roots2), now - 60)[1] == new

    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(
        description="codex 런타임 홈의 최신 생성물을 신선도 게이트와 함께 찾는다.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float,
                    help="이 epoch 이후 생성물만 (생성 전에 --now 로 찍어둔 값)")
    ap.add_argument("--max-age", type=float,
                    help=f"최근 N초 내 생성물만 (기본 {DEFAULT_MAX_AGE:.0f})")
    ap.add_argument("--now", action="store_true", help="현재 epoch 출력 후 종료")
    ap.add_argument("--list", action="store_true", help="루트별 최신 생성물 진단 출력")
    ap.add_argument("--copy-to", help="찾은 파일을 이 경로로 복사 (덮어쓰지 않음)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return 0
    if a.now:
        print(f"{time.time():.3f}")
        return 0

    roots = candidate_roots()
    found = scan(roots)

    if a.list:
        diagnose(roots, found, time.time(), out=sys.stdout)
        return 0

    since = a.since if a.since is not None else time.time() - (a.max_age or DEFAULT_MAX_AGE)
    hit = pick_fresh(found, since)
    if not hit:
        diagnose(roots, found, since)
        return 1

    mtime, path = hit
    if a.copy_to:
        dest = Path(a.copy_to)
        if dest.exists():
            print(f"이미 존재해 덮어쓰지 않음: {dest}", file=sys.stderr)
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        print(f"복사: {path}  ({_fmt(mtime)})\n  -> {dest}", file=sys.stderr)
        print(dest)
    else:
        print(f"{_fmt(mtime)}  {path}", file=sys.stderr)
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
