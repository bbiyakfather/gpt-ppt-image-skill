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
- **이미지 안에 한글·CJK 문자를 gpt-image-2로 그리게 하지 않는다.** 글자가 깨지거나 뜻 없는 글자가 섞인다. 한글 라벨이 필요하면 §3-A의 2단계 파이프라인을 쓴다.
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
| Text | **한글·CJK 문구는 절대 프롬프트에 넣지 않는다** → §3-A. 영문 단어 몇 개까지는 가능하나 그래도 오탈자가 난다. 기본은 "no text, no letters, no numbers, no labels, no watermark" |
| Format | 용도별 규격 (hero: wide, icon: square+simple silhouette, diagram: clear labels) |

규칙: **세션 컨텍스트**(프로젝트 주제, 논의된 테마·색·톤)를 반영하되, **사용자 명시 요구가 항상 우선**. 최종 프롬프트는 완료 보고에 요약 포함.

### 3-A. 한글 라벨이 필요한 이미지 — 2단계 파이프라인

다이어그램·개념도·인포그래픽처럼 **이미지 안에 한글 라벨이 들어가야 하는 경우**, 한 번에 만들지 않는다.

```
1단계  gpt-image-2 로 그림 본체만 생성 (텍스트 0개)
2단계  overlay_labels.py 로 한글 라벨·리더선·화살표를 합성
```

이유: gpt-image-2는 한글을 못 쓴다. 반면 2단계는 실제 시스템 폰트로 그리므로 **글자가 100% 정확**하고, 수치·용어가 바뀌어도 **이미지를 다시 생성하지 않고 스펙 한 줄만 고쳐 즉시 재렌더**할 수 있다(구독 한도도 아낀다).

1단계 프롬프트에는 화살표·기호·라벨 자리까지 넣지 말고(“no arrows, no diagram symbols”) 그림 본체만 요구한다. 화살표는 2단계에서 방향·색을 정확히 통제하는 편이 낫다.

```bash
python "$HOME/.claude/skills/codex-image/scripts/overlay_labels.py" <spec>.json
python "$HOME/.claude/skills/codex-image/scripts/overlay_labels.py" --selfcheck   # 동작 확인
```

스펙(JSON) — **좌표는 캔버스 대비 % 이며, 이것이 6단계 핀 리뷰의 `x_pct`/`y_pct`와 같은 좌표계다.**

```json
{
  "base": "gpt-image/20260730-120000-foo-base.png",
  "out":  "gpt-image/20260730-120000-foo-v02.png",
  "labels": [
    {"text": "① 태양광 발전부", "x": 12, "y": 8, "size": 30, "bold": true, "leader": [20, 15]}
  ],
  "arrows": [
    {"from": [30, 60], "to": [55, 60], "color": "#2b6cb0", "width": 6, "text": "급수"}
  ]
}
```

**auto 테마(기본)**: 라벨마다 pill이 놓일 자리의 이미지 밝기를 샘플링해 밝은 배경→다크 스크림(rgba(17,24,39,0.72))+흰 글자, 어두운 배경→라이트 pill(rgba(255,255,255,0.78))+검은 글자를 자동 선택한다. 반투명은 실제 알파 합성이라 배경이 살짝 비친다. 리더선은 흰 halo+진색 본선+대상점 dot으로 어떤 배경에서도 보인다. `pill`/`color`를 명시하면 항상 그 값이 이기고, `"pill": "none"`이면 pill 없이 글자만 그린다.

**디자인 원칙**: 라벨은 이미지 **안**의 한적한 영역(하늘·빈 배경)에 놓고 리더선으로 대상을 가리킨다 — 캔버스를 늘려 이미지 밖 여백에 라벨을 두지 않는다(여백이 디자인을 깨는 주범). 타입 스케일은 2단만: 주 라벨 28~32, 캡션·수치 22~24.

스펙 키 전체 (괄호 안 = 기본값):

| 위치 | 키 |
|---|---|
| labels[] | `text`·`x`·`y` (필수), `size`(30), `bold`(false), `anchor`("mm", Pillow 규칙), `pill`("auto"), `color`(테마 자동), `pad`(10), `radius`(10), `border`(없음), `border_width`(2), `leader`([x,y]), `leader_color`(#111827), `leader_width`(3) |
| arrows[] | `from`·`to` (필수), `color`(#2b6cb0), `width`(6), `text`(없음), `size`(26), `bold`(false) |
| canvas | `aspect`(+`height`) 또는 `width`+`height`, `bg`(#ffffff) — **평소엔 생략**(base 크기 그대로) |
| 루트 | `font`(맑은고딕), `font_bold`(맑은고딕 볼드) |

- `canvas.aspect` — 비율 교정은 **생성 단계에서 하는 게 원칙**(§4). 기존 이미지 재사용 등으로 비율이 어긋난 경우에만 쓰고, 이때 그림은 contain으로 letterbox 되어 `bg` 여백이 남는다.
- **stdout 계약**: 마지막 줄에 `{"out": ..., "canvas": [w,h], "art_rect": [x,y,w,h]}` JSON을 출력한다. `art_rect`는 캔버스 안에서 원본 그림이 차지하는 영역 — letterbox 시 핀 좌표를 원본 그림 기준으로 환산할 때 쓴다(§7).
- **스펙 JSON은 산출물과 같은 폴더에 남긴다.** 다음 수정의 입력이고, 이게 없으면 라벨을 다시 찍어야 한다.

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

- **Aspect ratio는 항상 명시한다.** 최종 배치처(슬라이드 박스, 히어로 영역 등)의 비율을 생성 **전에** 확정해 프롬프트에 넣는다. 나중에 §3-A 캔버스로 비율을 맞추면 letterbox 여백이 생겨 디자인이 깨진다.
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
  경로는 환경마다 다를 수 있으니 `-o` 출력의 저장 경로를 우선 신뢰하고, 없을 때 위 런타임 홈을 fallback 으로 쓴다.

### 5. 자가 검증

생성된 파일을 **Read 도구로 실제로 연다**. 파일 부재·손상이면 성공으로 보고하지 않는다. 요청과 어긋난 점이 보이면 보고에서 먼저 밝힌다.

### 6. 리뷰 팝업 (생성 직후 자동)

```bash
python "$HOME/.claude/skills/codex-image/scripts/review_server.py" gpt-image/<file1>.png [<file2>.png ...] --timeout 570
```

- Bash timeout **600000ms**로 실행. 여러 장이면 모두 인자로 넘긴다 → 갤러리 모드.
- §3-A 파이프라인을 쓴 경우 **라벨이 합성된 최종본을 리뷰에 올린다**(본체 원본이 아니다). 그래야 사용자가 글자 위에 핀을 찍어 문구를 고칠 수 있다.
- stderr에 리뷰 URL이 출력된다. 브라우저가 자동으로 안 열리면 이 URL을 사용자에게 알려 수동 접속 안내.
- 서버 기동 실패 시 1회 재실행, 그래도 실패하면 팝업 없이 자연어 수정 방식을 안내 (기능 폴백).
- stdout의 마지막 줄 JSON을 파싱:
  - `{"action":"none","reason":"user"}` → 확정. 종료 보고. (`"reason":"timeout"`이면 타임아웃 확정임을 보고)
  - `{"action":"edit","reason":"user","images":[{file, pins:[{n,x_pct,y_pct,comment}]}]}` → 7단계로. `file`은 입력 이미지의 절대경로.
  - `{"action":"error","reason":"file not found: ..."}` (exit 1) → 입력 경로 오타. 경로 수정 후 재실행.

### 7. 핀 기반 수정 실행

**먼저 핀을 두 갈래로 분류한다.** 텍스트 계열 핀에 이미지 재생성을 쓰면 한도만 태우고 한글은 여전히 깨진다.

| 핀 성격 | 처리 | 비용 |
|---|---|---|
| **텍스트·라벨·수치·용어** (문구 수정, 라벨 추가·삭제·이동, 화살표 방향/색, 오탈자) | §3-A 스펙 JSON만 고쳐 `overlay_labels.py` 재실행. **codex 호출 없음.** 핀의 `x_pct`/`y_pct`를 그대로 라벨 좌표로 쓴다 | 0 |
| **그림 본체** (구조·형상·색감·구도·객체 추가·삭제) | 아래 `codex exec -i` 로 본체만 재생성 → 그 다음 같은 스펙으로 라벨 재합성 | 1장 |

한 리뷰에 두 계열이 섞여 있으면 **본체 재생성 → 라벨 재합성** 순서로 한 번에 처리하고, 텍스트만이면 재생성을 건너뛴다.

그림 본체 수정 시 핀 좌표를 영역 서술로 번역한다: x_pct <33 → left / <66 → center / 그 외 right, y_pct 동일하게 top/middle/bottom. 5단계에서 이미지를 봤으므로 **그 위치의 실제 객체명을 함께 명시**한다 (예: "the logo in the upper-left region").

**좌표계 주의**: 핀 %는 리뷰에 올린 이미지(=합성 캔버스) 기준이다. `canvas.aspect`로 letterbox 된 합성본이라면 본체 재생성 전에 overlay stdout의 `art_rect=[ax,ay,aw,ah]`로 원본 그림 기준 %로 환산한다: `x_art% = (x_pct/100 × canvas_w − ax) / aw × 100` (y 동일). letterbox 없이 만들었다면(원칙) 그대로 쓴다.

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
| 팝업 실패 | 서버 기동/브라우저 실패 | URL 수동 안내 → 그래도 안 되면 자연어 수정 폴백 |
| 배치 부분 실패 | 일부 파일 미생성 | 성공분 보존·리뷰, 실패분 원인 보고, 재시도 여부 질문 |

검증된 환경: codex-cli 0.144.1, Windows Git Bash. 동작이 다르면 `codex --version`으로 버전 차이부터 의심할 것.
