# codex-image

Claude Code용 이미지 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀-댓글 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates/edits images through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local pin-comment review popup for revision loops, plus a text-free background fallback for Korean text that gpt-image-2 cannot render reliably.

## 텍스트

단일 이미지의 문구(한글 포함)는 프롬프트에 포함해 **직접 그리는 것이 기본**이다. 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으며, 스킬이 생성 전 리스크를 고지하고(소형 텍스트는 고위험 사전 경고) 결과에서 글자를 검증한다.

**라벨이 여럿인 레이아웃형(발표자료·인포그래픽·배너)은 §3-B 레이아웃 파이프라인이 기본**: 글자는 이미지 모델을 경유하지 않는다. `layout.json`(좌표 단일 진실 소스) 하나에서 —

```
layout.json ─┬→ sketch(회색 박스 구도) → codex -i → 글자 없는 배경 PNG
             ├→ render(배경+실제 한글) → Chrome 캡처 → composite PNG (핀 리뷰·웹 납품)
             └→ pptx → 배경 + 네이티브 텍스트박스 .pptx (열어서 바로 편집)
```

한글은 폰트가 그리므로 깨질 수 없고, 문구·배치 수정은 layout.json만 고쳐 재렌더한다(**쿼터 0회**). 배경 수정만 codex 재생성(쿼터 1회)이다. 플랫/그래픽 배경이면 이미지 모델 자체를 생략한다(쿼터 0회). §3-A(배경만 + 라벨 가이드 표)는 의존성이 없을 때의 최소 폴백으로 유지된다.

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 워크플로 8단계 + §3-A 폴백 + §3-B 레이아웃 파이프라인, 오류 대응표 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·댓글을 JSON으로 반환 |
| `scripts/layout_kit.py` | layout.json → 스케치/합성 HTML·Chrome 캡처(뷰포트 결손 자동 보정)·편집가능 .pptx(한글 a:ea 폰트, scrim 알파). pptx 서브커맨드만 python-pptx 필요, 나머지 stdlib |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3, Chrome(§3-B 캡처), python-pptx(§3-B .pptx — 선택)
npm i -g @openai/codex && codex login
pip install python-pptx
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/codex-image"
python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" demo   # 자가 점검
```

이미 설치된 경우 업데이트는 클론 디렉터리에서 `git pull` (수동 복사 설치본이면 재복사 — scripts/layout_kit.py가 있어야 §3-B가 동작한다).

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다. 고칠 곳을 클릭해 핀을 찍고 댓글을 달면 반영한다. §3-B에서는 핀이 이원화된다 — 라벨 박스 안 핀(문구·크기·색·배치)은 layout.json 수정 후 재렌더(쿼터 0, 수 초), 박스 밖 핀(배경)만 codex `-i` 재생성(쿼터 1, `-i`에는 항상 텍스트 없는 배경 원본). "수정 없음(확정)"까지 반복한다.

## License

MIT
