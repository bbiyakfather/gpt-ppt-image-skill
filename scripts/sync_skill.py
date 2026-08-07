#!/usr/bin/env python3
"""이 저장소(DEV)를 실제로 로드되는 설치 스킬 디렉터리로 동기화한다.

이 저장소는 개발용 사본이다. Claude Code가 실제로 읽는 스킬은
`~/.claude/skills/gpt-ppt-image` 에 있는 **별도의 실사본**(심볼릭 링크 아님)이고,
누군가 손으로 복사하기 전까지 이 저장소를 아무리 고쳐도 반영되지 않는다.
"고쳤는데 왜 그대로지?" 를 만드는 흔한 함정이라 이 스크립트로 그 손복사를 대신한다.

사용:
  python sync_skill.py                 # 실제 복사 (기본 대상: ~/.claude/skills/gpt-ppt-image)
  python sync_skill.py --dest DIR       # 대상 디렉터리 지정
  python sync_skill.py --dry-run        # 무엇이 바뀔지만 보고, 복사는 안 함
  python sync_skill.py --check          # in-sync 여부만 확인, 어긋나면 exit 1 (pre-commit 게이트용)
  python sync_skill.py --selftest       # 순수 로직 자기점검 (임시 디렉터리, 실제 스킬 안 건드림)

대상 해석 순서: --dest > $CLAUDE_SKILLS_DIR/gpt-ppt-image > ~/.claude/skills/gpt-ppt-image
복사 대상: SKILL.md, README.md, LICENSE, scripts/, references/, docs/
제외: .git, .fablize, __pycache__, *.pyc, gpt-image/ (개발 전용 잔재 — .gitignore와 동일 기준)

안전장치: 대상이 이미 있는데 SKILL.md가 없으면 이 스킬 디렉터리가 아니라고 보고 거부한다
(엉뚱한 디렉터리를 덮어쓰지 않기 위함).
"""
import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

TOP_ITEMS = ["SKILL.md", "README.md", "LICENSE", "scripts", "references", "docs"]
EXCLUDE_NAMES = {".git", ".fablize", "__pycache__", "gpt-image"}
EXCLUDE_SUFFIXES = (".pyc",)


def is_excluded(name):
    return name in EXCLUDE_NAMES or name.endswith(EXCLUDE_SUFFIXES)


def iter_tree_files(root, item):
    """root/item 아래(item이 파일이면 자기 자신)를 순회 -> (root 기준 relpath, abspath). exclude 적용."""
    p = root / item
    if not p.exists():
        return
    if p.is_file():
        if not is_excluded(p.name):
            yield item, p
        return
    for dirpath, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if not is_excluded(d)]
        for f in files:
            if is_excluded(f):
                continue
            ap = Path(dirpath) / f
            rel = ap.relative_to(root)
            yield str(rel).replace("\\", "/"), ap


def source_files(src_root):
    """복사 대상 전체를 {relpath: abspath} 로."""
    out = {}
    for item in TOP_ITEMS:
        out.update(iter_tree_files(src_root, item))
    return out


def dest_files(dest_root):
    """대상 쪽의 (source_files와 같은 기준으로 걸러진) 파일 전체."""
    out = {}
    for item in TOP_ITEMS:
        out.update(iter_tree_files(dest_root, item))
    return out


def looks_like_skill(dest_root):
    return (dest_root / "SKILL.md").is_file()


def resolve_dest(dest_arg):
    if dest_arg:
        return Path(dest_arg)
    env = os.environ.get("CLAUDE_SKILLS_DIR")
    if env:
        return Path(env) / "gpt-ppt-image"
    return Path.home() / ".claude" / "skills" / "gpt-ppt-image"


def guard_dest(dest_root):
    """엉뚱한 디렉터리를 덮어쓰지 않기 위한 방어. 새 디렉터리(미존재)는 통과."""
    if dest_root.exists() and not looks_like_skill(dest_root):
        sys.exit(
            f"거부: {dest_root} 가 이미 있지만 SKILL.md가 없음 — 이 스킬 디렉터리가 아닌 듯. "
            "--dest 로 올바른 경로를 지정하세요."
        )


def diff_status(src_root, dest_root):
    """(missing, differing, extra) — 대상 기준 어긋난 파일들.

    missing: 소스엔 있는데 대상에 없음. differing: 둘 다 있는데 내용이 다름.
    extra: 대상엔 있는데 소스에 없음(소스에서 지워진 잔재).
    """
    src = source_files(src_root)
    dst = dest_files(dest_root) if dest_root.is_dir() else {}
    missing, differing = [], []
    for rel, ap in src.items():
        dp = dest_root / rel
        if not dp.is_file():
            missing.append(rel)
        elif not filecmp.cmp(ap, dp, shallow=False):
            differing.append(rel)
    extra = sorted(set(dst) - set(src))
    return sorted(missing), sorted(differing), extra


def sync(src_root, dest_root, dry_run):
    """어긋난 파일만 복사. 반환: 복사(예정)한 relpath 목록."""
    missing, differing, _ = diff_status(src_root, dest_root)
    todo = sorted(missing + differing)
    for rel in todo:
        if not dry_run:
            dp = dest_root / rel
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_root / rel, dp)
    return todo


def selftest():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "src"
        for item in ["SKILL.md", "README.md", "LICENSE"]:
            (src).mkdir(exist_ok=True)
            (src / item).write_text(f"{item} v1", encoding="utf-8")
        (src / "scripts").mkdir()
        (src / "scripts" / "a.py").write_text("print(1)", encoding="utf-8")
        (src / "scripts" / "__pycache__").mkdir()
        (src / "scripts" / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"x")
        (src / "scripts" / "a.pyc").write_bytes(b"x")
        (src / "references").mkdir()
        (src / "references" / "r.md").write_text("ref", encoding="utf-8")
        (src / "docs").mkdir()
        (src / "docs" / "d.md").write_text("doc", encoding="utf-8")
        (src / ".git").write_text("gitdir: ...", encoding="utf-8")
        (src / ".fablize").mkdir()
        (src / ".fablize" / "state.json").write_text("{}", encoding="utf-8")
        (src / "gpt-image").mkdir()
        (src / "gpt-image" / "hero.png").write_bytes(b"x")

        files = source_files(src)
        # exclude 필터: .git/.fablize/__pycache__/*.pyc/gpt-image 는 하나도 안 들어와야 한다
        assert "scripts/a.py" in files
        assert "references/r.md" in files
        assert "docs/d.md" in files
        assert not any(
            r.startswith((".git", ".fablize", "gpt-image")) or "__pycache__" in r or r.endswith(".pyc")
            for r in files
        ), files

        # 대상 미존재: guard 통과, 전부 missing
        dest = root / "dest"
        guard_dest(dest)  # raise 없어야 함
        missing, differing, extra = diff_status(src, dest)
        assert set(missing) == set(files), (missing, files)
        assert differing == [] and extra == []

        # dry-run: 아무것도 실제로 안 생김
        copied = sync(src, dest, dry_run=True)
        assert set(copied) == set(files)
        assert not dest.exists()

        # 실제 sync: 전부 복사되고, 그 뒤 diff_status는 깨끗
        copied = sync(src, dest, dry_run=False)
        assert set(copied) == set(files)
        m2, d2, e2 = diff_status(src, dest)
        assert (m2, d2, e2) == ([], [], [])

        # 소스 한 파일 변경 -> differing 감지
        (src / "README.md").write_text("README.md v2", encoding="utf-8")
        m3, d3, e3 = diff_status(src, dest)
        assert d3 == ["README.md"], d3

        # 재동기화 후 다시 깨끗
        sync(src, dest, dry_run=False)
        assert diff_status(src, dest) == ([], [], [])

        # 대상에만 있는 잔재 파일 -> extra 감지
        (dest / "scripts" / "stale.py").write_text("old", encoding="utf-8")
        m4, d4, e4 = diff_status(src, dest)
        assert e4 == ["scripts/stale.py"], e4

        # guard: SKILL.md 없는 무관한 디렉터리는 거부
        unrelated = root / "unrelated"
        unrelated.mkdir()
        (unrelated / "something.txt").write_text("x", encoding="utf-8")
        try:
            guard_dest(unrelated)
            raise AssertionError("거부했어야 함")
        except SystemExit:
            pass

        # dest 해석 우선순위: --dest > CLAUDE_SKILLS_DIR > 기본값
        assert resolve_dest("/explicit") == Path("/explicit")
        os.environ["CLAUDE_SKILLS_DIR"] = str(root / "envskills")
        try:
            assert resolve_dest(None) == root / "envskills" / "gpt-ppt-image"
        finally:
            del os.environ["CLAUDE_SKILLS_DIR"]
        assert resolve_dest(None) == Path.home() / ".claude" / "skills" / "gpt-ppt-image"

    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", help="설치 스킬 디렉터리 (기본: $CLAUDE_SKILLS_DIR/gpt-ppt-image 또는 ~/.claude/skills/gpt-ppt-image)")
    ap.add_argument("--check", action="store_true", help="in-sync 여부만 확인 (어긋나면 exit 1). 복사 안 함")
    ap.add_argument("--dry-run", action="store_true", help="무엇이 바뀔지만 출력, 실제 복사 안 함")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return 0

    src_root = Path(__file__).resolve().parent.parent  # scripts/ 의 부모 = 저장소 루트
    dest_root = resolve_dest(a.dest)
    guard_dest(dest_root)

    if a.check:
        missing, differing, extra = diff_status(src_root, dest_root)
        if not missing and not differing and not extra:
            print(f"동기화됨: {dest_root}")
            return 0
        print(f"어긋남: {dest_root} (source: {src_root})")
        for rel in missing:
            print(f"  누락: {rel}")
        for rel in differing:
            print(f"  변경됨: {rel}")
        for rel in extra:
            print(f"  대상에만 있음(소스에서 삭제됨): {rel}")
        return 1

    todo = sync(src_root, dest_root, a.dry_run)
    if not todo:
        print(f"이미 동기화됨: {dest_root}")
        return 0
    verb = "복사 예정" if a.dry_run else "복사"
    for rel in todo:
        print(f"  {verb}: {rel}")
    print(f"{verb} {len(todo)}개 -> {dest_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
