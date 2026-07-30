# codex-image

Claude Code용 이미지 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀-댓글 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates/edits images through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local pin-comment review popup for revision loops, plus a text-free background fallback for Korean text that gpt-image-2 cannot render reliably.

## 텍스트

문구(한글 포함)는 이미지 생성 시 프롬프트에 포함해 **직접 그리는 것이 기본**이다. 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으며, 스킬이 생성 전 리스크를 고지하고(소형 텍스트는 고위험 사전 경고) 결과에서 글자를 검증한다.

**같은 한글 문구가 2회 연속 깨지면 폴백**: 같은 구도를 텍스트 제외로 1회 재생성해 **깨끗한 배경 이미지**를 납품한다. 텍스트 작업은 사용자가 PowerPoint·한글 등 익숙한 도구에서 직접 한다 — 스킬은 문구·배치·서체·색을 정리한 **라벨 가이드 표**를 함께 제공해 배치만 하면 되게 돕는다. (HTML/SVG 오버레이 합성·대화형 에디터는 실사용 결과 PPT 직접 작업보다 사용성이 낮아 폐기했다.)

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 워크플로 8단계 + §3-A 한글 폴백(배경 납품), 오류 대응표 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·댓글을 JSON으로 반환 |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3
npm i -g @openai/codex && codex login
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/codex-image"
```

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다. 고칠 곳을 클릭해 핀을 찍고 댓글을 달면, 핀들을 하나의 수정 요청으로 묶어 codex `-i` 재생성(1장)으로 반영한다. "수정 없음(확정)"까지 반복한다. 텍스트 제외 배경 폴백 산출물도 같은 루프로 구도·색감을 다듬는다.

## License

MIT
