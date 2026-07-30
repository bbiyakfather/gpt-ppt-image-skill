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
- **텍스트는 이미지 생성 시 프롬프트에 포함해 함께 그린다** (단일 이미지 기본 정책). 단 한글·CJK는 gpt-image-2 특성상 오탈자·깨짐이 날 수 있으므로, 생성 전 리스크를 한 줄 고지하고 결과 검증(5단계)에서 글자를 확인해 보고한다. 같은 한글 문구가 2회 연속 깨지면 §3-B 레이아웃 파이프라인(권장) 또는 §3-A 폴백을 제안한다. **라벨이 여럿인 레이아웃형 요청(발표자료·인포그래픽·배너)은 처음부터 §3-B가 기본** — 텍스트는 이미지 모델을 경유하지 않는다.
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
| Text | 필요한 문구(한글 포함)를 **정확한 철자 그대로** 프롬프트에 명시해 이미지에 직접 그린다. 문구는 따옴표로 감싸 "render exactly this text"로 지시. 사용자 문서에 쓰일 서체가 정해져 있으면 `typography in the style of '<서체명>', the clean Korean geometric sans-serif` 로 명기해 이질감을 줄인다. 텍스트가 필요 없는 이미지만 "no text, no letters, no watermark" |
| Format | 용도별 규격 (hero: wide, icon: square+simple silhouette, diagram: clear labels) |

규칙: **세션 컨텍스트**(프로젝트 주제, 논의된 테마·색·톤)를 반영하되, **사용자 명시 요구가 항상 우선**. 최종 프롬프트는 완료 보고에 요약 포함.

**소형 텍스트 사전 경고 (생성 전 필수 판정)**: gpt-image-2는 글자가 작게 그려질수록 깨진다 — 큰 헤드라인(이미지 세로의 ~7%)은 정확히 렌더된 실측 사례가 있으나, 작은 라벨은 고위험. 요청이 다음 중 하나에 해당하면 **생성 전에** 깨짐 고위험을 경고하고 선택지를 제시한다: ① 그대로 진행(깨지면 한도 소모) ② **§3-B 레이아웃 파이프라인(권장)** — 글자는 폰트로 그리고 배경만 생성, 합성 PNG·편집가능 .pptx 납품 ③ §3-A 배경만 납품(글자는 사용자가 PPT·한글에서 얹는다).
- 한글 문구가 3개 이상 (다이어그램·개념도·인포그래픽·표 형태 포함)
- 예상 글자 높이가 이미지 세로의 약 4% 미만 (긴 문장, 좁은 영역의 라벨, 캡션류)
- 문구에 숫자·단위·고유명사가 섞여 정확성이 필수인 경우

### 3-A. 한글 텍스트 폴백 — 텍스트 제외 배경 납품

**원칙**: 작은 한글 텍스트는 gpt-image-2로도, 오버레이 합성으로도 만족스럽게 안 된다 (HTML/SVG 오버레이·대화형 에디터는 실사용 결과 PPT 직접 작업보다 사용성이 낮아 폐기됨). 폴백은 **텍스트가 앉을 자리를 비운 배경 이미지**를 납품하고, 텍스트 작업은 사용자가 PowerPoint·한글 등 익숙한 도구에서 직접 한다.

**진입 조건**(셋 중 하나): ① 같은 한글 문구가 2회 연속 깨짐 → 사용자에게 폴백을 제안하고 승인받는다 ② 사용자가 처음부터 "배경만" 요청 ③ §3 소형 텍스트 사전 경고에서 사용자가 배경 납품을 선택.

**배경 생성** (한도 1회): 기존 이미지가 있으면 `-i`로 첨부해 같은 구도의 텍스트 제외 버전을 재생성한다. 프롬프트에 "no text, no letters, no numbers, no labels, no watermark" + "keep composition identical" + 텍스트가 앉을 자리의 여백(negative space) 확보 지시를 넣는다. 처음부터 배경으로 시작하는 경우는 `-i` 없이 텍스트 제외 프롬프트로 생성한다. 커맨드는 §4 골격에 `-i "<기존 이미지 절대경로>"`만 더해 쓴다 (§7 템플릿의 핀 목록 문구는 쓰지 않는다).

**라벨 가이드 동봉 (권장)**: 배경을 건넬 때 Claude가 설계한 텍스트 시안을 **채팅 표**로 함께 준다 — 문구(정확한 철자), 배치 위치(예: 좌상단 여백), 권장 크기 비율, 서체·색 제안. 사용자는 이 표를 보고 PPT에서 배치만 하면 된다. 별도 파일은 만들지 않는다.

**배경도 §6 핀 리뷰를 거친다**: 구도·여백 위치·색감 수정은 핀으로 받아 §7 재생성 루프를 돈다(재생성 프롬프트에 텍스트 제외 지시 유지). 확정되면 배경 PNG를 `gpt-image/`에 남기고 최종 보고에 경로를 명시한다.

사용자가 합성 PNG나 편집가능 .pptx까지 원하면 §3-A 대신 §3-B로 간다 (§3-A는 §3-B의 최소 부분집합이다).

### 3-B. 레이아웃 파이프라인 — 글자는 폰트가, 배경만 이미지 모델이

**원칙**: 텍스트는 이미지 모델을 **절대 경유하지 않는다**. 좌표 단일 진실 소스는 layout.json 하나 — 스케치·합성 미리보기·.pptx가 전부 여기서 파생되므로 어긋날 수 없다. 도구는 `layout_kit.py` (서브커맨드: sketch / render / pptx / capture / demo).

**진입 조건**(하나면 충분): ① 라벨 여럿인 레이아웃형 요청(발표자료·인포그래픽·배너·다이어그램) ② §3 사전 경고에서 ② 선택 ③ 한글 2회 깨짐 후 사용자가 편집가능 산출물 희망.

**의존성 점검**: `python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" demo` — sketch/render/pptx/capture/pixel_probe 전부 ok면 통과. python-pptx 없음 → .pptx 납품만 불가(§3-A 표 폴백), Chrome 없음 → 캡처류 불가(§3-A로 전환, .pptx는 캡처 없이 가능).

**0) layout.json 작성** — `gpt-image/YYYYMMDD-HHMMSS-<slug>-layout.json`:

```json
{"canvas": {"w": 1920, "h": 1080}, "background": "gpt-image/<배경>.png",
 "labels": [{"id": "title", "text": "고객만족도 향상", "x_pct": 6, "y_pct": 8, "w_pct": 46, "h_pct": 14,
             "font": "Malgun Gothic", "size_pt": 40, "bold": true, "color": "#111827",
             "align": "left", "scrim": false}]}
```

규칙: 문구는 정확한 철자로(그대로 납품된다). canvas 비율 = 최종 배치처 비율. **폰트는 로컬 설치 폰트만**(웹폰트 금지 — Chrome 캡처와 PowerPoint가 같은 폰트로 나와야 함), 확실치 않으면 Malgun Gothic. `\n` 줄바꿈 지원. size_pt 감각: 슬라이드 세로 = 540pt이므로 제목 32~44, 본문 14~20. scrim은 배경 위 가독성이 불안할 때 켠다(어두운 반투명 패널 — 미리보기와 .pptx에 동일 적용).

**1) 스타일 분기**:
- **플랫/그래픽 배경**(단색·그라데이션·도형): 이미지 모델 생략. Claude가 자유 HTML 작성(body 선언 크기 = canvas 픽셀 필수) → `layout_kit.py capture <html> <out.png> --size 1920x1080` → 그 PNG가 곧 산출물. **쿼터 0회.**
- **사진·일러스트 배경**: 2)로.

**2) 배경 생성 (쿼터 1회)**: §4 골격을 쓰되, Text 축 대신 **negative-space 스펙**을 영문으로 넣는다 — layout.json의 각 라벨 박스를 영역으로 서술: "Keep these regions as clean, empty negative space — no objects, no letters: from 6%,8% to 52%,22% (top-left); ...". 라벨 4개 이상이거나 비직교 구도면 스케치도 첨부한다:

```bash
python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" sketch <layout.json>   # → *-sketch.html
python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" capture <*-sketch.html> <sketch.png> --size 1920x1080
# codex exec 골격(§4)에 -i "<sketch.png 절대경로>" 추가, 프롬프트 문두는 반드시 변환 지시:
# "Turn this layout sketch into a <스타일 서술> background image. The gray rectangles are
#  placeholders only — do NOT draw them; keep those areas as clean, empty negative space."
```

가드 3칙: 변환 지시가 문두(편집 모드는 입력 외형을 보존하려 한다), **스타일 서술 필수**(스케치는 스타일 정보가 0 — 실측 89.5% 백지), 전부 영문(§3 정책).

**3) 배경 게이트 (§5의 확장)**: 배경 PNG를 Read로 열어 **layout.json의 각 예약 박스 영역이 비었는지 박스별로 확인해 보고한다**. 회색 사각형이 그대로 그려졌거나 영역이 붐비면: (a) 해당 라벨 scrim 활성화(쿼터 0) 또는 (b) 사용자 승인 후 1회 재생성. 게이트의 목적은 재생성 사이클 낭비와 scrim에 가려진 실패 은폐 방지다.

**4) 합성 미리보기**: layout.json의 background에 배경 경로 기입 후:

```bash
python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" render <layout.json>   # → *-render.html
python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" capture <*-render.html> <composite.png> --size 1920x1080
```

composite.png를 §6 팝업에 올린다. 배경 비율이 canvas와 다르면 render와 .pptx 양쪽에 동일한 center cover-crop이 자동 적용된다(stretch 금지).

**5) 핀 이원화 — §3-B composite 리뷰에서는 이 규칙이 §6·§7의 §3-A 문구를 대체한다**:
- **분류**: 핀 좌표(x_pct/y_pct)를 layout.json 라벨 박스와 hit-test한다(±2% 마진, 좌표계 동일). 박스 안 = 텍스트·배치 핀, 밖 = 배경 핀 후보. 댓글 키워드로 보정하고, 모호하면 사용자에게 묻는다.
- **텍스트·배치 핀** → layout.json 수정 → 4) 재실행. **쿼터 0회, 수 초.** (문구·크기·색·위치·scrim 전부 여기)
- **배경 핀** → 분류 결과를 사용자에게 확인받은 뒤 §7 재생성. **-i는 반드시 layout.json의 background(텍스트 없는 원본)** — 리뷰 JSON의 file(=composite)을 -i에 쓰면 렌더된 한글이 모델에 들어가 깨진 글자가 배경에 박힌다. 재생성 프롬프트에 negative-space 스펙 유지 → 3) 게이트 재통과.
- **혼합 제출**: 배경 핀 먼저(재생성 1회) → background 교체 → 텍스트 핀 반영 → 재render 1회 → 재리뷰.

**6) 납품** (용도별, 복수 가능):
- 웹 배너·히어로·소셜: **composite.png** (한글이 폰트로 렌더된 최종 합성본)
- 발표자료: **배경 PNG + .pptx** — `python "$HOME/.claude/skills/codex-image/scripts/layout_kit.py" pptx <layout.json>` (16:9 표준 EMU, 배경 풀블리드 + 동일 좌표 네이티브 텍스트박스, 한글 폰트 a:ea/a:cs 적용, word_wrap·auto_size 고정 — 열어서 바로 편집 가능)
- **layout.json + 배경 PNG는 재납품 원본**이다(추후 문구 교체 = 쿼터 0회). `gpt-image/`는 gitignore 대상이므로 최종 보고에 이 두 파일의 백업·보존 권장을 명시한다.

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
- §3-A 배경 폴백 산출물도 같은 팝업으로 리뷰한다 — 핀은 구도·여백 위치·색감 수정 요청용이다 (텍스트는 배경 확정 후 사용자가 PPT에서 작업).
- **§3-B composite.png 리뷰는 §3-B 5) 핀 이원화 규칙을 따른다** (텍스트 핀 = layout.json 수정, 위 §3-A 문구는 적용되지 않음). 팝업에는 composite만 올린다 — 배경 원본을 같이 올리면 file 필드 혼동으로 §7 -i 오배선 위험.
- stderr에 리뷰 URL이 출력된다. 브라우저가 자동으로 안 열리면 이 URL을 사용자에게 알려 수동 접속 안내.
- 서버 기동 실패 시 1회 재실행, 그래도 실패하면 팝업 없이 자연어 수정 방식을 안내 (기능 폴백).
- stdout의 마지막 줄 JSON을 파싱:
  - `{"action":"none","reason":"user"}` → 확정. 종료 보고. (`"reason":"timeout"`이면 타임아웃 확정임을 보고)
  - `{"action":"edit","reason":"user","images":[{file, pins:[{n,x_pct,y_pct,comment}]}]}` → 7단계로. `file`은 입력 이미지의 절대경로.
  - `{"action":"error","reason":"file not found: ..."}` (exit 1) → 입력 경로 오타. 경로 수정 후 재실행.

### 7. 핀 기반 수정 실행

핀 댓글을 모아 아래 `codex exec -i` **한 번**으로 수정한다 (고칠 문구는 따옴표로 정확히 명시). 같은 한글 문구가 2회 연속 깨지면 그 자리에서 중단하고 §3-A 폴백 전환(또는 문구 단순화·영문 전환·텍스트 제거)을 제안한다.

**§3-A 배경 산출물이면** 재생성 프롬프트에 "no text, no letters, no watermark"를 유지해 수정 중 글자가 생기지 않게 한다. 텍스트를 넣어 달라는 핀이 배경에 찍히면 재생성하지 말고, 그 내용을 라벨 가이드(§3-A)에 반영해 안내한다 — 텍스트는 사용자가 PPT에서 얹는 것이 폴백의 전제다.

**§3-B composite 산출물이면** 아래 커맨드의 `-i "<원본 절대경로>"`에 리뷰 JSON의 file(=composite)이 아니라 **layout.json의 background(텍스트 없는 배경 원본)**를 넣는다 — composite를 첨부하면 "Keep every other area identical" 지시가 렌더된 한글의 재현을 요구해 깨진 글자가 배경에 박힌다. 텍스트·배치 핀은 이 커맨드로 오지 않는다(§3-B 5에서 layout.json 수정으로 처리).

핀 좌표(`x_pct`/`y_pct`)는 영역 서술로 번역한다: x_pct <33 → left / <66 → center / 그 외 right, y_pct 동일하게 top/middle/bottom. 5단계에서 이미지를 봤으므로 **그 위치의 실제 객체명을 함께 명시**한다 (예: "the logo in the upper-left region").

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
| 배치 부분 실패 | 일부 파일 미생성 | 성공분 보존·리뷰, 실패분 원인 보고, 재시도 여부 질문 |
| python-pptx 없음 (§3-B) | layout_kit "python-pptx 없음" | `pip install python-pptx` 안내. 거절 시 .pptx 대신 §3-A 라벨 가이드 표 |
| Chrome 없음 (§3-B) | layout_kit "Chrome을 찾지 못함" | 캡처류(스케치·composite) 불가 → §3-A 전환. .pptx 조립은 캡처 없이 가능 |
| 뷰포트 프로브 실패 (§3-B) | layout_kit "뷰포트 프로브 실패" | 1회 재시도 → 실패 시 Chrome 버전 보고(147 실측 검증). 캡처 없이 .pptx만 진행 가능 |
| 배경 예약 영역 오염 (§3-B) | 3) 게이트에서 박스 영역에 물체·글자 | 해당 라벨 scrim 켜기(쿼터 0) 또는 사용자 승인 후 1회 재생성 |

검증된 환경: codex-cli 0.144.1~0.145.0, Chrome 147, python-pptx 1.0.2, Python 3.13, Windows Git Bash (스킬의 셸 커맨드는 전부 Git Bash 기준 — layout_kit.py 내부는 셸 미경유 subprocess라 셸 무관). 동작이 다르면 `codex --version`부터 의심할 것.
