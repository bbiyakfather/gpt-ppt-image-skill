# codex-image

Claude Code용 이미지 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀-댓글 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates/edits images through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local pin-comment review popup for revision loops, and an HTML-overlay fallback that captures pixel-perfect Korean text over an AI-generated background via headless Chrome.

## 텍스트

문구(한글 포함)는 이미지 생성 시 프롬프트에 포함해 **직접 그리는 것이 기본**이다. 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으며, 스킬이 생성 전 리스크를 고지하고 결과에서 글자를 검증한다.

**같은 한글 문구가 2회 연속 깨지면 폴백**: 같은 구도를 텍스트 제외로 1회 재생성(배경) → 그 위에 HTML/CSS 오버레이(시스템 폰트, pill 자동 크기) → 헤드리스 Chrome으로 배경 원본과 1:1 픽셀 재캡처. 이후 문구 수정은 HTML 수정 + 재캡처(수 초, 한도 소모 0)로 끝난다. 캡처 출력 크기는 스크립트가 자동 검증하며, Chrome이 없는 환경에서는 [resvg](https://github.com/linebender/resvg) 단일 실행파일로 SVG 오버레이 폴백(SKILL.md 오류표)한다.

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 워크플로 8단계 + §3-A 한글 폴백, 오류 대응표 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·댓글을 JSON으로 반환 |
| `scripts/capture_overlay.py` | 오버레이 HTML → 헤드리스 Chrome 캡처 + 1:1 크기 자동 검증. `--selfcheck` 내장 |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3 + Pillow, Chrome(폴백 캡처용)
npm i -g @openai/codex && codex login
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/codex-image"
python "$HOME/.claude/skills/codex-image/scripts/capture_overlay.py" --selfcheck
```

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다. 고칠 곳을 클릭해 핀을 찍고 댓글을 달면:
- 일반 산출물: 핀들을 하나의 수정 요청으로 묶어 codex `-i` 재생성(1장)으로 반영
- 폴백 산출물: 텍스트·라벨 핀은 HTML 수정 + 재캡처(무료·수 초), 그림 핀만 codex 재생성

"수정 없음(확정)"까지 반복한다. 핀의 % 좌표는 오버레이 CSS `left`/`top`과 같은 좌표계라 무변환으로 옮겨진다.

## License

MIT
