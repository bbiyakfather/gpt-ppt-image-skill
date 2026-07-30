# codex-image

Claude Code용 이미지 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀-댓글 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates/edits images through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local pin-comment review popup for revision loops, and a two-stage pipeline that renders Korean/CJK labels with real system fonts — because gpt-image-2 cannot draw CJK glyphs. Labels use an auto light/dark adaptive theme with true alpha-composited translucent pills.

## 왜 2단계 파이프라인인가

gpt-image-2는 한글을 그리지 못한다(깨진 글자·가짜 글자). 그래서 한글 라벨이 필요한 다이어그램·인포그래픽은:

```
1단계  gpt-image-2로 그림 본체만 생성 (텍스트 0개, 목표 비율로 생성)
2단계  overlay_labels.py로 한글 라벨·리더선·화살표를 실제 시스템 폰트로 합성
```

글자는 100% 정확하고, 문구·수치 수정은 이미지 재생성 없이 스펙 JSON 한 줄 수정 + 재렌더로 끝난다(구독 한도 절약).

**적용 범위**: 완성된 그림 **한 장**에 라벨을 다는 용도다. 여러 패널을 조립하는 콜라주형 인포그래픽을 오버레이로 만들면 codex 단독 생성보다 조잡해진다 — 그 경우 전체 구도를 codex 한 장으로 생성하고 라벨만 최소로 얹는다. 오버레이 1차 렌더는 초안으로 사용자 승인을 받은 뒤 정밀화한다(승인 게이트).

### 라벨 디자인 (auto 테마)

라벨마다 놓일 자리의 이미지 밝기를 샘플링해 자동 선택한다:

- 밝은 배경 → **다크 스크림** rgba(17,24,39,0.72) + 흰 글자
- 어두운 배경 → **라이트 pill** rgba(255,255,255,0.78) + 검은 글자
- 진짜 알파 합성(배경이 비치는 반투명), 리더선은 흰 halo + 본선 + 대상점 dot

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 워크플로 8단계, 오류 대응표 |
| `scripts/overlay_labels.py` | 한글 라벨 합성기 (Pillow). `--selfcheck` 내장 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·댓글을 JSON으로 반환 |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3 + Pillow, Windows(맑은 고딕 폰트 기준)
npm i -g @openai/codex && codex login
pip install Pillow
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/codex-image"
python "$HOME/.claude/skills/codex-image/scripts/overlay_labels.py" --selfcheck
```

Windows 외 환경은 스펙 JSON의 `font`/`font_bold`에 존재하는 CJK ttf 경로를 지정하면 된다.

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다. 고칠 곳을 클릭해 핀을 찍고 댓글을 달면, 스킬이 핀을 **텍스트 계열**(스펙 수정·재렌더, 비용 0)과 **그림 본체**(codex `-i` 재생성, 1장)로 분류해 처리하고 다시 리뷰를 연다. "수정 없음(확정)"까지 반복.

## License

MIT
