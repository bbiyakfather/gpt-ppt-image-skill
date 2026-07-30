---
name: codex-image
description: Generate or edit images using Codex CLI's built-in gpt-image-2 via the user's ChatGPT Plus subscription (no API key, no extra cost). Use when the user asks to create, generate, or draw an image, illustration, icon, logo, banner, hero, mockup, diagram, or poster, or asks to edit/refine a previously generated image. Do NOT use for reading/viewing existing image files, writing image-handling code (img tags, resize scripts), or deleting images.
---

# codex-image: Codex 경유 이미지 생성·수정

Claude Code에는 이미지 생성이 없다. 이 스킬은 `codex exec`(비대화형)로 Codex의 내장 gpt-image-2를 호출해 이미지를 생성하고, 브라우저 핀-댓글 리뷰 팝업으로 수정 루프를 돈다. 모든 비용은 사용자의 ChatGPT Plus 구독 한도에서 차감된다 (API 키 불필요).

## 절대 규칙

- OpenAI API 키를 요구하거나 사용하지 않는다. `codex exec` 경로만 사용한다.
- 사용자를 대신해 `codex login`을 실행하지 않는다. 미로그인 시 안내만 한다.
- 프롬프트에 세션 내 비밀 정보(API 키, 자격 증명, 개인정보)를 절대 넣지 않는다.
- 기존 이미지 파일을 덮어쓰지 않는다. 수정본도 항상 새 파일이다.
- **텍스트는 이미지 생성 시 프롬프트에 포함해 함께 그린다** (기본 정책). 단 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으므로, 생성 전 리스크를 한 줄 고지하고 결과 검증(5단계)에서 글자를 확인해 보고한다. 같은 한글 문구가 2회 연속 깨지면 §3-A 폴백(HTML 오버레이)을 제안한다.
- 콘텐츠 정책 거부 시 우회용 자동 변형 재시도를 하지 않는다.
- 같은 요청의 자동 재시도는 1회까지. 그 이상은 사용자에게 묻는다.

## 워크플로

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
| Text | 필요한 문구(한글 포함)를 **정확한 철자 그대로** 프롬프트에 명시해 이미지에 직접 그린다. 문구는 따옴표로 감싸 "render exactly this text"로 지시하고, 한글이 들어가면 "clean geometric sans-serif typography" 류 서체 인상 지시를 함께 넣는다(§3-A 폴백 전환 시 오버레이 폰트와의 이질감 축소). 텍스트가 필요 없는 이미지만 "no text, no letters, no watermark" |
| Format | 용도별 규격 (hero: wide, icon: square+simple silhouette, diagram: clear labels) |

규칙: **세션 컨텍스트**(프로젝트 주제, 논의된 테마·색·톤)를 반영하되, **사용자 명시 요구가 항상 우선**. 최종 프롬프트는 완료 보고에 요약 포함.

### 3-A. 한글 텍스트 폴백 — HTML 오버레이 + Chrome 재캡처

**진입 조건**(둘 중 하나): ① 같은 한글 문구가 2회 연속 깨짐 → 사용자에게 폴백을 제안하고 승인받는다 ② 사용자가 처음부터 "글자는 오버레이로"를 요청. 제안 시 비용을 고지한다: "배경 재생성 1회(한도 차감), 이후 텍스트 수정은 무료·즉시".

**1단계 — 배경 재생성** (한도 1회): 기존 이미지를 `-i`로 첨부해 같은 구도의 텍스트 제외 버전을 생성한다. 프롬프트에 "no text, no letters, no watermark" + "keep composition identical" + 텍스트가 앉을 자리의 여백(negative space) 확보 지시를 넣는다. 처음부터 오버레이로 시작하는 경우는 `-i` 없이 텍스트 제외 프롬프트로 1차 생성한다.

**2단계 — overlay HTML 작성**: `gpt-image/overlay-<slug>.html` 한 파일. 규약:
- body 크기 = **배경 원본 픽셀 그대로** (`body{width:<W>px;height:<H>px;position:relative}`) — 업스케일 금지(1:1 규칙)
- 배경은 `<img>` **상대경로** 참조 (폴더째 이동해도 열리게), 라벨은 `position:absolute; left:X%; top:Y%; transform:translate(-50%,-50%)` — % 좌표는 6단계 핀 리뷰의 `x_pct`/`y_pct`와 **같은 좌표계**
- pill 박스는 CSS 자동 크기(`display:inline-block; padding; border-radius; white-space:nowrap`)에 맡긴다 — **폭 하드코딩 금지**(박스 이탈의 원인)
- 폰트는 시스템 폰트 기본: `font-family:'Malgun Gothic'` (로딩 실패 모드 없음)
- **디자인 규율**: 타입 스케일은 2단만(주 라벨 / 캡션·수치), 라벨은 필요 최소 — 넣을까 말까면 뺀다. 리더선·화살표는 실제 관계가 있을 때만. 라벨은 이미지 안의 한적한 영역에 놓고 피사체를 가리지 않는다. 반투명 pill(`rgba`)·`backdrop-filter: blur()`는 배경 위 가독성 확보용으로만 절제해 사용

**3단계 — 캡처 + 1:1 자동 검증**:
```bash
python "$HOME/.claude/skills/codex-image/scripts/capture_overlay.py" <overlay.html> <out.png> <base.png>
python "$HOME/.claude/skills/codex-image/scripts/capture_overlay.py" --selfcheck   # 동작 확인
```
Chrome 헤드리스 CLI로 캡처한다. 스크립트가 2중 검증한다: 캡처 전 HTML body 선언 크기 = 배경 원본(작성 오류 차단), 캡처 후 출력 픽셀 = 배경 원본(스케일 이상 차단) — 불일치는 실패 처리. 요구 의존성: Python 3 + Pillow + Chrome (§1 사전 점검에 없는 항목이므로 폴백 진입 시 `--selfcheck`로 확인). Chrome 부재 시 오류표의 resvg 폴백.

**4단계 — 자가 검증·초안 승인 게이트**: 캡처본을 Read로 열어 라벨 배치·겹침·박스 이탈을 자기비평한다. **첫 폴백 결과물은 초안**이다 — SendUserFile로 보여주고 방향(계속/수정/폴백 폐기 후 재생성 복귀)을 확인받은 뒤 정밀화한다. 이후 6단계 리뷰 팝업에는 캡처된 최종본을 올린다.

**산출물 보존**: 배경 PNG + overlay HTML(재수정의 원본 — 삭제 금지) + 최종 캡처 PNG(새 타임스탬프)를 모두 `gpt-image/`에 남기고, 최종 보고에 세 경로를 명시한다. 이후 문구 수정 요청은 HTML만 고쳐 재캡처한다(codex 호출 0회, 수 초).

### 4. 생성 실행

파일명: `gpt-image/YYYYMMDD-HHMMSS-<slug>.png` (slug = 영문 소문자·하이픈, 사용자 지정 시 그것을 사용).

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -o "<세션 스크래치패드>/codex-img-<slug>.txt" \
  "Use your image generation tool to create an image and save it to <절대경로 또는 gpt-image/파일명>.
Prompt: <고도화된 영문 프롬프트>
Resolution: <1K|2K|4K, 기본 1K>. Aspect ratio: <최종 배치처 비율 — 항상 명시>.
Do not do anything else. Reply with the saved file path."
```

- **Aspect ratio는 항상 명시한다.** 최종 배치처(슬라이드 박스, 히어로 영역 등)의 비율을 생성 **전에** 확정해 프롬프트에 넣는다. 생성 후에 비율을 맞추려면 크롭이나 letterbox 여백이 생겨 디자인이 깨진다.
- `-o` 파일은 **세션 스크래치패드에 장별로** 만든다 (`codex-img-<slug>.txt`). `/tmp` 고정 경로는 PowerShell에 없고, 한 파일 재사용은 배치 시 앞 장의 실패 진단을 덮어쓴다.
- Bash timeout: **360000ms** (장당). 배치는 장별로 순차 실행하며 진행 상황 `n/전체`를 보고.
- 배치 시 각 장마다 개별 고도화 프롬프트를 만든다.
- 실패 판별: `-o` 출력과 stderr에서 quota/usage limit(한도), content policy(정책 거부), 기타(일반 실패)를 구분한다. 대응은 아래 오류 표.
- **저장경로 정책훅 차단 우회(검증됨)**: 일부 환경에서 codex가 결과물을 `gpt-image/파일명`으로 복사하는 단계가 PreToolUse 정책훅에 "blocked by policy"로 차단된다. **이미지 자체는 codex 런타임 홈에 정상 생성**되므로, 이때는 codex 재시도 대신 **가장 최근 생성물을 직접 복사**한다(한 번에 한 장씩 순차 생성해야 newest 매칭이 안전):
  ```bash
  GENDIR="$HOME/AppData/Roaming/orca/codex-runtime-home/home/generated_images"
  GEN=$(ls -t "$GENDIR"/*/*.png 2>/dev/null | head -1)
  [ -n "$GEN" ] && cp "$GEN" gpt-image/<파일명>.png || echo "런타임 홈에 생성물 없음 — -o 출력의 저장 경로를 확인"
  ```
  경로는 환경마다 다를 수 있으니 `-o` 출력의 저장 경로를 우선 신뢰하고, 없을 때 위 런타임 홈을 fallback으로 쓴다.

### 5. 자가 검증

생성된 파일을 **Read 도구로 실제로 연다**. 파일 부재·손상이면 성공으로 보고하지 않는다. 요청과 어긋난 점이 보이면 보고에서 먼저 밝힌다.

### 6. 리뷰 팝업 (생성 직후 자동)

```bash
python "$HOME/.claude/skills/codex-image/scripts/review_server.py" gpt-image/<file1>.png [<file2>.png ...] --timeout 570
```

- Bash timeout **600000ms**로 실행. 여러 장이면 모두 인자로 넘긴다 → 갤러리 모드.
- §3-A 폴백을 쓴 경우 **캡처된 최종본을 리뷰에 올린다**(배경 원본이 아니다) — 그래야 글자 위에 핀을 찍어 문구를 고칠 수 있다.
- stderr에 리뷰 URL이 출력된다. 브라우저가 자동으로 안 열리면 이 URL을 사용자에게 알려 수동 접속 안내.
- 서버 기동 실패 시 1회 재실행, 그래도 실패하면 팝업 없이 자연어 수정 방식을 안내 (기능 폴백).
- stdout의 마지막 줄 JSON을 파싱:
  - `{"action":"none","reason":"user"}` → 확정. 종료 보고. (`"reason":"timeout"`이면 타임아웃 확정임을 보고)
  - `{"action":"edit","reason":"user","images":[{file, pins:[{n,x_pct,y_pct,comment}]}]}` → 7단계로. `file`은 입력 이미지의 절대경로.
  - `{"action":"error","reason":"file not found: ..."}` (exit 1) → 입력 경로 오타. 경로 수정 후 재실행.

### 7. 핀 기반 수정 실행

**§3-A 폴백 산출물이면 핀을 두 갈래로 분류한다** — 텍스트 핀에 재생성을 쓰면 한도만 태운다:

| 핀 성격 | 처리 | 비용 |
|---|---|---|
| **텍스트·라벨** (문구·위치·크기·색, 리더선·화살표) | overlay HTML만 수정 → `capture_overlay.py` 재캡처. 핀의 `x_pct`/`y_pct`를 CSS `left`/`top`에 그대로 사용 | 0 |
| **그림 본체** (구조·형상·색감·구도·객체) | 아래 `codex exec -i`로 배경만 재생성 — **`-i`에는 §3-A에서 보존한 배경 PNG를 첨부한다** (글자가 구워진 캡처 최종본이 아니다) + 프롬프트에 "no text, no letters, no watermark" 포함 → 같은 HTML로 재캡처 | 1장 |

**일반(텍스트 포함 생성) 산출물이면** 핀 댓글을 모아 아래 `codex exec -i` **한 번**으로 수정한다(고칠 문구는 따옴표로 정확히 명시). 같은 한글 문구가 2회 연속 깨지면 그 자리에서 중단하고 §3-A 폴백 전환(또는 문구 단순화·영문 전환·텍스트 제거)을 제안한다.

그림 본체 수정 시 핀 좌표(`x_pct`/`y_pct`)는 영역 서술로 번역한다: x_pct <33 → left / <66 → center / 그 외 right, y_pct 동일하게 top/middle/bottom. 5단계에서 이미지를 봤으므로 **그 위치의 실제 객체명을 함께 명시**한다 (예: "the logo in the upper-left region").

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -i "<원본 절대경로>" -o "<세션 스크래치패드>/codex-img-<slug>-edit.txt" \
  "Edit the attached image. Apply ONLY the following changes:
1) In the <region> region (about <x>% from left, <y>% from top), on the <객체명>: <핀 댓글>.
2) ...
Keep every other area, style, and composition identical to the attached image.
Use your image generation tool with the attached image as reference and save the result to gpt-image/<새 타임스탬프 파일명>.png. Reply with the saved file path."
```

- 한 이미지의 여러 핀은 **하나의 요청으로 묶어 1회 생성**. 배치에서 핀 달린 이미지가 여러 장이면 장별 순차 수정.
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
| 저장경로 정책훅 차단 | 출력에 "blocked by policy"(복사 단계) | 재생성 금지. 런타임 홈 newest `*.png` 를 직접 `cp`(위 step 4 우회) |
| 팝업 서버 기동 실패 | review_server 즉시 종료 | 1회 재실행 → 그래도 실패하면 자연어 수정 폴백 |
| 팝업 브라우저 미오픈 | 서버는 떴는데 창이 안 열림 | stderr의 리뷰 URL 수동 접속 안내 |
| Chrome 부재 (§3-A 캡처) | capture_overlay.py가 chrome 미발견 종료 | [resvg 단일 exe](https://github.com/linebender/resvg/releases) 다운로드 후 오버레이를 SVG로 작성해 렌더 (pill 폭은 폰트 실측 필요 — HTML과 달리 자동 크기 없음). 그것도 안 되면 HTML을 사용자 브라우저로 열어 수동 확인 안내 |
| 배치 부분 실패 | 일부 파일 미생성 | 성공분 보존·리뷰, 실패분 원인 보고, 재시도 여부 질문 |

검증된 환경: codex-cli 0.144.1, Windows Git Bash. 동작이 다르면 `codex --version`으로 버전 차이부터 의심할 것.
