# codex-image

Claude Code용 이미지 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀-댓글 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates/edits images through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local pin-comment review popup for revision loops.

## 한글·CJK 텍스트

gpt-image-2는 한글을 그리지 못한다(깨진 글자·가짜 글자). 그래서 이미지는 **텍스트 없이** 생성하는 것이 기본이고, 한글 문구가 필요하면 최종 배치처(PPT·한글 문서 등)의 텍스트 박스로 얹는다.

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 워크플로 8단계, 오류 대응표 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·댓글을 JSON으로 반환 |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3
npm i -g @openai/codex && codex login
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/codex-image"
```

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다. 고칠 곳을 클릭해 핀을 찍고 댓글을 달면, 스킬이 핀들을 하나의 수정 요청으로 묶어 codex `-i` 재생성(1장)으로 반영하고 다시 리뷰를 연다. "수정 없음(확정)"까지 반복. 한글 문구 수정 핀은 재생성으로 해결되지 않으므로(한글 렌더 불가) 배치처 텍스트 처리로 안내한다.

## License

MIT
