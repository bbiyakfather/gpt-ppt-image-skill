# gpt-ppt-image

Claude Code용 이미지·PPT 생성·수정 스킬. `codex exec`(비대화형)로 Codex CLI의 내장 **gpt-image-2**를 호출해 이미지를 만들고, 로컬 브라우저 **핀·붓 리뷰 팝업**으로 수정 루프를 돈다. 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 — OpenAI API 키가 필요 없다.

> **English**: A Claude Code skill that generates and edits images — including full image-slide PPT decks — through Codex CLI's built-in gpt-image-2 (billed to your ChatGPT Plus subscription, no API key). It adds a local review popup with pin comments and brush-painted regions for revision loops.

구 `codex-image` + `image-prompt` 스킬을 통합한 것이다.

## 세 갈래

| 요청 | 트랙 |
|---|---|
| 이미지 1~n장 생성·수정 | **A. 단일 이미지** — `SKILL.md` 8단계 |
| PPT·덱·발표자료를 슬라이드 이미지로 | **B. 덱** — `docs/deck-workflow.md` |
| "프롬프트만 짜줘", jsonl 배치 | **C. 프롬프트 컴파일** — `references/` |

**편집 가능한 .pptx(도형·텍스트 상자)가 필요하면 이 스킬이 아니라 `pptx` 스킬을 쓴다.** 트랙 B의 산출물은 이미지 슬라이드라 나중에 글자를 고칠 수 없다.

## 텍스트

문구(한글 포함)는 이미지 생성 시 프롬프트에 포함해 **직접 그린다**. 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으며, 스킬이 생성 전 리스크를 고지하고 결과에서 글자를 검증한다.

깨진 글자는 **전체 재생성 없이 국소 수리**한다 (구독 한도 소모 0):

- **붓** — 팝업에서 영역을 칠하고 정확한 문구를 적는다. OCR을 돌지 않아 **장당 1초 미만**. 장식 폰트·저대비처럼 검출이 안 되는 글자도 잡힌다.
- **핀** — 지점을 찍으면 easyocr(CRAFT)이 그 자리의 텍스트 박스를 찾는다. 장당 ~15초.

두 경로 모두 원 글자색을 추정해 맑은 고딕으로 다시 쓴다. 배경 복원은 `cv2.inpaint` 기반이라 **단색·단순 배경에서 가장 잘 맞고**, 복잡한 배경에서는 자국이 남을 수 있다 — 그때는 재생성 경로로 넘어간다.

## 구성

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 스킬 본문 — 라우팅, 워크플로 8단계, 오류 대응표 |
| `docs/deck-workflow.md` | 덱 트랙 절차 (아웃라인 → 스타일 → 샘플 → 전체 → 조립) |
| `references/*.md` | 프롬프트 자산 — 컨셉 축, 스타일 분류, 타이포, 사진 어휘, 카테고리 패턴 |
| `references/ppt-styles.md` | 덱 스타일 12종 + 영문 프롬프트 조각 |
| `scripts/review_server.py` | 일회성 로컬 리뷰 서버 (stdlib only). 핀 좌표·붓 마스크를 JSON으로 반환 |
| `scripts/repair_text.py` | 핀·붓 기반 국소 텍스트 수리 |
| `scripts/assemble_ppt.py` | 슬라이드 이미지 + 발표노트 → .pptx |
| `scripts/check_prompt.mjs` | 프롬프트 산출물 검증기 |

## 설치

```bash
# 요구: Codex CLI 로그인(ChatGPT 계정), Python 3.12+
npm i -g @openai/codex && codex login
git clone https://github.com/bbiyakfather/codex-image-skill "$HOME/.claude/skills/gpt-ppt-image"

# 국소 수리용 (붓만 쓸 거면 easyocr 없이도 된다)
pip install opencv-python Pillow
pip install easyocr          # 핀 경로에 필요
pip install python-pptx      # 덱 조립에 필요
```

## 리뷰 루프

생성 직후 브라우저 팝업이 열린다.

- **📍 핀** — 고칠 지점을 클릭하고 댓글을 단다. 그림 요소 수정은 핀들을 하나의 요청으로 묶어 codex `-i` 재생성(1장)으로 반영한다.
- **🖌️ 붓** — 고칠 영역을 칠하고 바꿀 문구를 적는다. 스트로크는 정규화 좌표로 저장돼 **원본 해상도 마스크 PNG**로 떨어지므로, 화면 표시 배율과 무관하게 정확하다.

"수정 없음(확정)"까지 반복한다.

## 자기점검

```bash
python scripts/repair_text.py --selftest
python scripts/assemble_ppt.py --selftest
```

## License

MIT
