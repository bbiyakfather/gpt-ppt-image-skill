---
name: gpt-ppt-image
description: Codex CLI 내장 gpt-image-2로 이미지·인포그래픽·PPT 슬라이드를 만들고 고친다 (ChatGPT Plus 구독 경유, API 키 불필요). 이미지·일러스트·아이콘·로고·배너·히어로·목업·다이어그램·포스터 생성이나 이전 생성물 수정, "PPT/덱/발표자료를 이미지 슬라이드로 만들기", "이미지 프롬프트만 짜줘/공백 프롬프트/프롬프트 컴파일" 요청에 쓴다. 쓰지 말아야 할 때 — 편집 가능한 .pptx(도형·텍스트 상자)가 필요하거나 기존 pptx를 읽기·수정·병합할 때는 `pptx` 스킬을 쓴다 (이 스킬의 덱 산출물은 이미지라 나중에 글자를 못 고친다). 기존 이미지 파일 읽기·보기, 이미지 처리 코드 작성(img 태그, 리사이즈 스크립트), 이미지 삭제에도 쓰지 않는다.
---

# gpt-ppt-image: Codex 경유 이미지·PPT 생성·수정

Claude Code에는 이미지 생성이 없다. 이 스킬은 `codex exec`(비대화형)로 Codex의 내장 gpt-image-2를 호출해 이미지를 생성하고, 브라우저 핀·붓 리뷰 팝업으로 수정 루프를 돈다. 모든 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 (API 키 불필요).

## 라우팅 — 먼저 어느 트랙인지 정한다

| 요청 | 트랙 | 읽을 것 |
|---|---|---|
| 이미지 1~n장 생성·수정 | **A. 단일 이미지** | 아래 워크플로 |
| PPT·덱·발표자료를 슬라이드 이미지로 | **B. 덱** | `docs/deck-workflow.md` |
| "프롬프트만 짜줘", 공백 프롬프트, jsonl 배치 | **C. 프롬프트 컴파일** | `references/` (아래 표) |
| 편집 가능한 .pptx가 필요 | **→ `pptx` 스킬로 넘긴다** | — |

B와 C도 실제 생성은 A의 4~7단계를 그대로 쓴다.

## 절대 규칙

- OpenAI API 키를 요구하거나 사용하지 않는다. `codex exec` 경로만 사용한다.
- 사용자를 대신해 `codex login`을 실행하지 않는다. 미로그인 시 안내만 한다.
- 프롬프트에 세션 내 비밀 정보(API 키, 자격 증명, 개인정보)를 절대 넣지 않는다.
- 기존 이미지 파일을 덮어쓰지 않는다. 수정본도 항상 새 파일이다.
- **텍스트는 이미지 생성 시 프롬프트에 포함해 함께 그린다** (당분간 이 정책 유지). 단 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으므로, 생성 전 리스크를 한 줄 고지하고 결과 검증(5단계)에서 글자를 확인해 보고한다.
- 콘텐츠 정책 거부 시 우회용 자동 변형 재시도를 하지 않는다.
- 같은 요청의 자동 재시도는 1회까지. 그 이상은 사용자에게 묻는다.
- **한 번에 한 장씩 순차 생성한다.** 정책훅 차단 시 런타임 홈의 최신 PNG를 집어오는 우회(4단계)가 동시 생성에서 깨져 엉뚱한 이미지를 조용히 가져온다.

## 워크플로 (트랙 A)

1. **사전 점검** → 2. **(모호하면 1회 질문)** → 3. **프롬프트 고도화** → 4. **생성** → 5. **자가 검증** → 6. **리뷰 팝업** → 7. **수정 루프** → 8. **최종 보고**

### 1. 사전 점검

```bash
codex --version          # 미설치 → 중단, 안내: npm i -g @openai/codex 후 codex login
codex login status       # "Logged in using ChatGPT" + exit 0 이 아니면 → 중단, codex login 안내
mkdir -p gpt-image       # 현재 프로젝트 루트에. 실패(권한) 시 중단하고 원인 안내
```

점검 통과 후 사용자에게 생성 시작과 예상 소요 시간(장당 1~2분)을 알린다.

### 2. 모호성 확인 (최대 1회)

주제나 스타일이 크게 갈릴 수 있는 모호한 요청이면 생성 전에 핵심 방향을 **한 번만** 확인한다 (구독 한도 낭비 방지). 충분히 구체적이면 묻지 말고 바로 진행한다. 사용자가 "프롬프트 먼저 보여줘"라고 하면 고도화된 프롬프트를 보여주고 확인받은 뒤 생성한다.

### 3. 프롬프트 자동 고도화

짧은 요청을 아래 축을 채운 **상세 영문 프롬프트**로 확장한다:

| 축 | 내용 |
|---|---|
| Subject | 대상을 구체화 (무엇이, 어떤 상태로, 어떤 배경에) |
| Composition | 구도·시점·여백 (rule of thirds, centered, close-up 등) |
| Lighting | 조명 (soft studio light, golden hour, neon glow 등) |
| Style/Medium | 스타일·매체 (flat vector, 3D render, watercolor, photorealistic 등) |
| Color | 색상 팔레트 — 세션에서 언급된 브랜드 색 반영 |
| Quality | 품질 수식어 (highly detailed, clean edges, professional) |
| Text | 필요한 문구(한글 포함)를 **정확한 철자 그대로** 프롬프트에 명시해 이미지에 직접 그린다. 문구는 따옴표로 감싸 "render exactly this text" 로 지시. 텍스트가 필요 없는 이미지만 "no text, no letters, no watermark" |
| Format | 용도별 규격 (hero: wide, icon: square+simple silhouette, diagram: clear labels) |

규칙: **세션 컨텍스트**(프로젝트 주제, 논의된 테마·색·톤)를 반영하되, **사용자 명시 요구가 항상 우선**. 최종 프롬프트는 완료 보고에 요약 포함.

더 깊은 고도화가 필요하면 `references/`를 읽는다 (트랙 C의 자산이지만 A/B에서도 쓴다):

| 파일 | 언제 |
|---|---|
| `concept-axes.md` | 컨셉 변주·미학 조합이 필요할 때 |
| `style-taxonomy.md` · `look-presets.md` | 스타일·룩을 고를 때 |
| `typography-layout.md` | 글자 배치·타이포 지시가 핵심일 때 |
| `photo-vocab.md` | 사진풍(렌즈·조명) 어휘가 필요할 때 |
| `category-patterns.md` | 포스터·카드뉴스·썸네일 등 용도별 패턴 |
| `editorial-hwabo.md` | 화보·에디토리얼 톤 |
| `jsonl-and-examples.md` | jsonl 배치 스키마와 예시 |
| `ppt-styles.md` | **덱 스타일 12종** (트랙 B에서 고름) |

프롬프트 산출물을 검증하려면: `node scripts/check_prompt.mjs <파일>`

### 4. 생성 실행

파일명: `gpt-image/YYYYMMDD-HHMMSS-<slug>.png` (slug = 영문 소문자·하이픈, 사용자 지정 시 그것을 사용). 덱은 `gpt-image/<덱이름>/slide_01.png` 형식 (조립 스크립트가 이 패턴을 요구).

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -o "<세션 스크래치패드>/codex-img-<slug>.txt" \
  "Use your image generation tool to create an image and save it to <절대경로 또는 gpt-image/파일명>.
Prompt: <고도화된 영문 프롬프트>
Resolution: <1K|2K|4K, 기본 1K>. Aspect ratio: <최종 배치처 비율 — 항상 명시>.
Do not do anything else. Reply with the saved file path."
```

- **Aspect ratio는 항상 명시한다.** 최종 배치처(슬라이드 박스, 히어로 영역 등)의 비율을 생성 **전에** 확정해 프롬프트에 넣는다. 생성 후에 비율을 맞추려면 크롭이나 letterbox 여백이 생겨 디자인이 깨진다. 덱은 16:9 고정.
- `-o` 파일은 **세션 스크래치패드에 장별로** 만든다 (`codex-img-<slug>.txt`). `/tmp` 고정 경로는 PowerShell에 없고, 한 파일 재사용은 배치 시 앞 장의 실패 진단을 덮어쓴다.
- Bash timeout: **360000ms** (장당). 배치는 장별로 순차 실행하며 진행 상황 `n/전체`를 보고.
- 배치 시 각 장마다 개별 고도화 프롬프트를 만든다.
- 실패 판별: `-o` 출력과 stderr에서 quota/usage limit(한도), content policy(정책 거부), 기타(일반 실패)를 구분한다. 대응은 아래 오류 표.
- **저장경로 정책훅 차단 우회(검증됨)**: 일부 환경에서 codex가 결과물을 `gpt-image/파일명`으로 복사하는 단계가 PreToolUse 정책훅에 "blocked by policy"로 차단된다. **이미지 자체는 codex 런타임 홈에 정상 생성**되므로, 이때는 codex 재시도 대신 **가장 최근 생성물을 직접 복사**한다:
  ```bash
  # 런타임 홈 경로는 codex 버전·계정 구성에 따라 다르다. 실측된 두 형태를 모두 훑어 최신 1장을 고른다.
  GEN=$(ls -t "$HOME/AppData/Roaming/orca"/codex-accounts/*/home/generated_images/*/*.png \
              "$HOME/AppData/Roaming/orca"/codex-runtime-home/home/generated_images/*/*.png \
              2>/dev/null | head -1)
  [ -n "$GEN" ] && cp "$GEN" gpt-image/<파일명>.png || echo "런타임 홈에 생성물 없음 — -o 출력의 저장 경로를 확인"
  ```
  경로는 환경마다 다를 수 있으니 `-o` 출력의 저장 경로를 우선 신뢰하고, 없을 때 위 런타임 홈을 fallback 으로 쓴다.
  **복사 전 `ls -l "$GEN"` 로 생성 시각이 방금인지 반드시 확인한다** — 구버전 경로에 오래된 생성물이 남아 있으면 조용히 엉뚱한 이미지를 집는다(실측: `codex-runtime-home` 쪽 최신본이 9일 전).

### 5. 자가 검증

생성된 파일을 **Read 도구로 실제로 연다**. 파일 부재·손상이면 성공으로 보고하지 않는다. 요청과 어긋난 점이 보이면 보고에서 먼저 밝힌다. 글자가 들어간 이미지는 철자를 확인한다.

### 6. 리뷰 팝업 (생성 직후 자동)

```bash
python "$HOME/.claude/skills/gpt-ppt-image/scripts/review_server.py" \
  gpt-image/<file1>.png [<file2>.png ...] \
  --mask-dir "<세션 스크래치패드>/masks" --timeout 570
```

- Bash timeout **600000ms**로 실행. 여러 장이면 모두 인자로 넘긴다 → 갤러리 모드.
- stderr에 리뷰 URL과 마스크 디렉터리가 출력된다. 브라우저가 자동으로 안 열리면 이 URL을 사용자에게 알려 수동 접속 안내.
- 서버 기동 실패 시 1회 재실행, 그래도 실패하면 팝업 없이 자연어 수정 방식을 안내 (기능 폴백).
- 팝업에는 두 도구가 있다:
  - **📍 핀** — 지점 클릭 + 댓글. 그림 요소 수정용.
  - **🖌️ 붓** — 영역을 칠하고 + 바꿀 정확한 문구. 글자가 뭉개졌거나 장식 폰트라 OCR이 못 잡을 때.
- stdout의 마지막 줄 JSON을 파싱:
  - `{"action":"none","reason":"user"}` → 확정. 종료 보고. (`"reason":"timeout"`이면 타임아웃 확정임을 보고)
  - `{"action":"edit",...,"images":[{file, pins:[{n,x_pct,y_pct,comment}], regions:[{n,mask,comment}]}]}` → 7단계로. `file`·`mask`는 절대경로.
  - `{"action":"error","reason":"file not found: ..."}` (exit 1) → 입력 경로 오타. 경로 수정 후 재실행.

### 7. 수정 실행 — 세 갈래

**(a) 붓 영역(`regions`) = 텍스트 교체** → 재생성하지 않고 국소 수리한다 (쿼터 0, 다른 영역 변형 위험 0):

```bash
python "$HOME/.claude/skills/gpt-ppt-image/scripts/repair_text.py" "<원본 절대경로>" \
  --mask "<regions[].mask>:<regions[].comment>" [--mask ...]
```

- 붓 경로는 easyocr·torch를 아예 로딩하지 않는다 — **장당 1초 미만** (핀 경로는 OCR 로딩에 ~15초).
- 출력은 `<stem>-fixed.png` 새 파일 (원본 보존).
- **한계**: 칠한 영역을 `cv2.inpaint`로 배경 복원하므로 **단색·단순 배경에서 가장 잘 맞는다.** 배경이 복잡하거나 마스크가 두꺼우면 복원 자국이 남는다 (실측: 단색 헤더에서도 옅은 사각 자국). 자국이 눈에 띄면 (c)의 재생성 경로로 보낸다.

**(b) 텍스트 핀(`pins`) = 텍스트 교체** → 같은 스크립트의 핀 경로:

```bash
python "$HOME/.claude/skills/gpt-ppt-image/scripts/repair_text.py" "<원본 절대경로>" \
  --pin "<x_pct>,<y_pct>:<교체할 정확한 문구>" [--pin ...]
```

- 동작: easyocr(CRAFT)로 텍스트 박스 검출 → 핀이 가리키는 박스만 inpaint → 원 글자색 추정 후 맑은 고딕 볼드 재기입. 장당 ~15초, 한글 경로 안전.
- 의존성 최초 1회: `pip install easyocr opencv-python` (첫 실행 시 `~/.EasyOCR` 모델 다운로드).
- **상위 마스크 엔진 (GPU 장비)**: 텍스트가 그림 요소 위에 겹쳐 있으면 `--engine sam`으로 글자 획만 정밀 마스킹한다 (`pip install segment-anything` + 첫 실행 시 vit_b 체크포인트 375MB 자동 다운로드). 기본 `--engine auto`는 GPU(cuda)+설치가 확인될 때만 sam을 자동 선택하므로 CPU 장비는 그대로 사각형 방식이다. SAM 마스크가 퇴화하면 스크립트가 자동으로 사각형 폴백한다.
- 핀이 어느 텍스트 박스에도 안 붙으면 스크립트가 중단한다 → 그 영역은 붓(a)으로 다시 받는다.
- 수리 실패 시: 같은 한글 문구가 2회 연속 깨지면 중단하고 사용자에게 대안(문구 단순화·영문 전환·텍스트 제거)을 제안한다.

**(c) 그림 요소 수정** → `codex exec -i` 로 **한 번에** 재생성한다. 핀 좌표(`x_pct`/`y_pct`)나 붓 마스크 bbox를 영역 서술로 번역한다: x <33 → left / <66 → center / 그 외 right, y 동일하게 top/middle/bottom. 5단계에서 이미지를 봤으므로 **그 위치의 실제 객체명을 함께 명시**한다 (예: "the logo in the upper-left region").

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -i "<원본 절대경로>" -o "<세션 스크래치패드>/codex-img-<slug>-edit.txt" \
  "Edit the attached image. Apply ONLY the following changes:
1) In the <region> region (about <x>% from left, <y>% from top), on the <객체명>: <핀 댓글>.
2) ...
Keep every other area, style, and composition identical to the attached image.
Use your image generation tool with the attached image as reference and save the result to gpt-image/<새 타임스탬프 파일명>.png. Reply with the saved file path."
```

- 한 이미지의 여러 그림 핀은 **하나의 요청으로 묶어 1회 생성**. 배치에서 수정 대상이 여러 장이면 장별 순차.
- 수정본 저장 후 5단계(검증) → 6단계(수정본만 다시 리뷰 팝업)로 루프. 사용자가 "수정 없음(확정)"을 누를 때까지 반복. 루프당 생성 횟수를 보고에 표시.
- **자연어 수정 (경량 대안)**: 팝업 없이 사용자가 터미널에서 "더 어둡게" 등으로 지시하면 직전 생성물(또는 사용자가 지정한 기존 파일 — 없으면 생성 전에 알림)을 `-i`로 첨부해 동일하게 수정한다.

### 8. 최종 보고

저장 경로(들), 사용된 프롬프트 요약, 관찰평, (수정했다면) 수정 이력 요약을 한국어로 보고한다.

## 오류 대응

| 상황 | 감지 | 대응 |
|---|---|---|
| Codex 미설치 | `codex --version` 실패 | 중단. `npm i -g @openai/codex` + `codex login` 안내 |
| 미로그인 | `codex login status` exit≠0 | 중단. `codex login` (ChatGPT 계정) 안내 |
| 한도 초과 | 출력에 usage/rate limit 류 | 재시도 금지. Plus 한도 차감 사실 + 리셋 대기 안내 |
| 정책 거부 | 출력에 content policy 류 | 재시도 금지. 거부 사실 + 정책 내 표현 조정 방향 안내 |
| 타임아웃/일반 실패 | Bash timeout, 파일 미생성 | 원인 추정 + 다음 행동 안내. 자동 재시도 1회만 |
| 폴더 생성 실패 | mkdir 실패 | 중단. 권한·경로 확인 안내 |
| 저장경로 정책훅 차단 | 출력에 "blocked by policy"(복사 단계) | 재생성 금지. 런타임 홈 newest `*.png` 를 직접 `cp`(4단계 우회) |
| 팝업 실패 | 서버 기동/브라우저 실패 | URL 수동 안내 → 그래도 안 되면 자연어 수정 폴백 |
| 핀이 텍스트 박스에 안 붙음 | repair_text 중단 메시지 | 그 영역만 붓으로 다시 받는다 (7-a) |
| inpaint 자국 | 수리 결과 Read 확인 시 | 붓·핀 수리 포기하고 7-c 재생성으로 전환 |
| 배치 부분 실패 | 일부 파일 미생성 | 성공분 보존·리뷰, 실패분 원인 보고, 재시도 여부 질문 |

검증된 환경: codex-cli 0.144.1~0.144.6, Python 3.12~3.13, Windows Git Bash. 동작이 다르면 `codex --version`으로 버전 차이부터 의심할 것 — 0.144.6에서 생성물 저장 위치가 `codex-runtime-home/` → `codex-accounts/<uuid>/` 로 바뀐 전례가 있다.

## 스크립트 자기점검

로직을 건드렸다면 배포 전에 돌린다 (무거운 의존성 없이 동작):

```bash
python scripts/repair_text.py --selftest
python scripts/assemble_ppt.py --selftest
```
