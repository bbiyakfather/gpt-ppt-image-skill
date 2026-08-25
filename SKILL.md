---
name: gpt-ppt-image
description: Codex CLI 내장 gpt-image-2 또는 grok CLI 내장 image_gen으로 이미지·인포그래픽·PPT 슬라이드를 만들고 고친다 (구독 경유, API 키 불필요). 이미지·일러스트·아이콘·로고·배너·히어로·목업·다이어그램·포스터 생성이나 이전 생성물 수정, "PPT/덱/발표자료를 이미지 슬라이드로 만들기", "이미지 프롬프트만 짜줘/공백 프롬프트/프롬프트 컴파일" 요청에 쓴다. "grok으로 이미지/슬라이드 만들어줘"처럼 엔진을 지정한 요청에도 쓴다 — 이미지에 한글 카피가 들어가면 grok이 유리하고, 큰 캔버스가 필요하면 codex가 유리하다. 나중에 글자를 직접 고쳐야 하면 트랙 D(배경만 생성하고 글자는 폰트로 합성)로 이미지 PNG와 텍스트 편집이 되는 .pptx를 낸다. 쓰지 말아야 할 때 — 기존 .pptx를 읽기·수정·병합하거나 처음부터 도형·차트·표로 짠 일반 프레젠테이션이 필요하면 `pptx` 스킬을 쓴다. 기존 이미지 파일 읽기·보기, 이미지 처리 코드 작성(img 태그, 리사이즈 스크립트), 이미지 삭제에도 쓰지 않는다.
---

# gpt-ppt-image: 구독 CLI 경유 이미지·PPT 생성·수정

Claude Code에는 이미지 생성이 없다. 이 스킬은 **다른 CLI의 내장 이미지 도구를 비대화형으로 호출**해 이미지를 만들고, 브라우저 핀·붓 리뷰 팝업으로 수정 루프를 돈다. 비용은 사용자의 해당 구독 한도에서 차감된다 (API 키 불필요).

- **codex** — `codex exec` → gpt-image-2 (ChatGPT Plus). **기본 엔진.**
- **grok** — `grok -p` → image_gen / image_edit (grok.com). 대안 엔진.

## 엔진 선택 — 트랙보다 먼저 정한다

| 조건 | 엔진 |
|---|---|
| 사용자가 엔진을 지정 | 지정대로 |
| **이미지에 한글·CJK 카피가 들어감** | **grok** (실측 우세 — 아래) |
| 2K 이상 큰 캔버스·인쇄물·1920×1080 무손실 | codex (grok은 16:9가 1280×720 고정) |
| 4:3 · 3:4 · 4:5 비율 | codex (grok에 없는 AR) |
| 한쪽 한도 소진 | 다른 쪽으로 폴백하고 그 사실을 고지 |
| 그 외 | codex (기본) |

**이 표는 추천값을 계산하는 근거일 뿐, 최종 결정은 2단계에서 사용자에게 받는다.** 생성은 구독 한도를 실제로 깎으므로 엔진을 말없이 고르지 않는다.

한글 실측(2026-08-25): gpt-image-2는 캔버스를 2048까지 키워야 안정적인 반면, grok은 1280×720에서 `"공정 자동화로 인건비 12% 절감"` 류 4줄 + 숫자까지 오탈자 0으로 냈다(2/2). **표본 2건이라 보증이 아니라 우세로 다루고**, 5단계 자가 검증은 어느 엔진에서도 생략하지 않는다.

**grok을 고르면 `references/engine-grok.md`를 읽는다.** 갈라지는 건 사전 점검·생성 호출·크기·저장/회수 네 곳뿐이고, 프롬프트 철칙·린터·리뷰 팝업·`repair_text.py`·트랙 D·`assemble_ppt.py`는 **그대로 공유한다.** 아래 워크플로에서 `codex exec`가 나오는 자리만 그 문서의 명령으로 바꿔 읽으면 된다.

## 라우팅 — 그다음 어느 트랙인지 정한다

| 요청 | 트랙 | 읽을 것 |
|---|---|---|
| 이미지 1~n장 생성·수정 | **A. 단일 이미지** | 아래 워크플로 |
| PPT·덱·발표자료를 슬라이드 이미지로 | **B. 덱** | `docs/deck-workflow.md` |
| "프롬프트만 짜줘", 공백 프롬프트, jsonl 배치 | **C. 프롬프트 컴파일** | `references/` (아래 표) |
| **한글 글자가 정확해야 함** / 나중에 글자를 고쳐야 함 | **D. 레이아웃 합성** | 아래 "트랙 D" |
| 기존 .pptx를 읽기·수정·병합 | **→ `pptx` 스킬로 넘긴다** | — |

B와 C도 실제 생성은 A의 4~7단계를 그대로 쓴다.

## 트랙 D — 글자는 폰트가, 배경만 모델이 (`layout_kit.py`)

gpt-image-2는 한글을 자주 틀린다. **글자를 모델에게 안 그리게 하면 이 문제가 사라진다.** 배경만 생성하고 글자는 프로그램이 폰트로 얹는다.

`layout.json`(좌표 단일 진실 소스) 하나로 세 가지가 나온다:

```
layout.json ─┬─ sketch  회색 박스 구도 → codex에 -i 로 넘겨 그 자리를 비운 배경을 받는다
             ├─ render  배경 + 폰트 글자 → 합성 HTML → capture 로 PNG (오탈자 0)
             └─ pptx    배경 + 진짜 텍스트 상자 → PowerPoint에서 바로 수정 가능
```

```bash
LK="$HOME/.claude/skills/gpt-ppt-image/scripts/layout_kit.py"
python "$LK" sketch  layout.json -o sketch.html
python "$LK" capture sketch.html sketch.png --size 1920x1080   # 이걸 codex -i 로 첨부
# 배경 생성(트랙 A 4단계) 후 layout.json 의 "background" 에 그 경로를 넣고:
python "$LK" render layout.json -o composite.html && python "$LK" capture composite.html final.png --size 1920x1080
python "$LK" pptx slide_01.json slide_02.json slide_03.json -o deck.pptx  # 입력 순서대로 묶는 편집 가능본
```

- **언제 쓰나**: 사용자가 **나중에 글자를 직접 고쳐야 할 때**(이건 엔진이 해결해주지 못한다), 또는 codex로 한글 카피를 정확히 내야 할 때.
- **grok 엔진에서는 강제 조건이 아니다.** 트랙 D는 gpt-image-2의 한글 실패를 우회하려고 만든 트랙인데 grok은 그 실패가 거의 없다(위 실측). 그래도 "발표 후 수치를 고쳐야 한다" 같은 **편집 가능성** 요구가 있으면 엔진과 무관하게 D로 간다.
- **배경 생성 프롬프트에는 반드시 "그 영역을 비워두라"고 넣는다** — sketch 이미지를 `-i`로 주고, 회색 박스는 **묘사하지 말고 여백으로 두라**고 지시한다. 배경에 글자가 그려져 오면 합성 글자와 겹친다.
- 의존성: `pptx` 모드는 python-pptx만, `capture` 모드는 **Chrome/Edge 필요**(헤드리스). `render`·`sketch`는 HTML만 만들어 의존성이 없다.
- `python "$LK" demo` 로 5개 경로(sketch/render/pptx/capture/pixel_probe) 자가점검.
- 한계: 가로형 캔버스(16:9류) 전용. `pptx`는 같은 종횡비의 JSON 한 개 이상을 입력 순서대로 묶으며(절대 크기는 달라도 됨), 좌표는 `x_pct/y_pct/w_pct/h_pct` 백분율.

## 절대 규칙

- **API 키를 요구하거나 사용하지 않는다.** 구독 CLI 경로(`codex exec` / `grok -p`)만 사용한다.
- 사용자를 대신해 `codex login`·`grok login`을 실행하지 않는다. 미로그인 시 안내만 한다.
- **엔진을 말없이 고르거나 바꾸지 않는다.** 후보가 둘이면 2단계에서 AskUserQuestion으로 확정받고, 폴백했으면 어느 엔진으로 무엇이 달라졌는지(해상도·화풍) 보고에 적는다.
- 프롬프트에 세션 내 비밀 정보(API 키, 자격 증명, 개인정보)를 절대 넣지 않는다.
- 기존 이미지 파일을 덮어쓰지 않는다. 수정본도 항상 새 파일이다.
- **텍스트 정책은 트랙별로 다르다.** A/B/C는 필요한 문구를 프롬프트에 넣어 이미지와 함께 그리고, 한글·CJK 오탈자·깨짐 리스크를 생성 전에 고지한 뒤 5단계에서 확인한다(당분간 유지). D는 카피를 배경 프롬프트에서 빼고 글자 영역을 비운다. A/B/C는 생성 글자를 검증·수리하는 트랙이고 D는 그 실패 모드 자체를 폰트 합성으로 없애는 트랙이기 때문이다.
- 콘텐츠 정책 거부 시 우회용 자동 변형 재시도를 하지 않는다.
- 같은 요청의 자동 재시도는 1회까지. 그 이상은 사용자에게 묻는다.
- **한 번에 한 장씩 순차 생성한다.** 저장이 막혔을 때 런타임 홈의 최신 생성물을 집어오는 우회(4단계)가 동시 생성에서 깨져 엉뚱한 이미지를 조용히 가져온다. 엔진이 codex든 grok이든 같다.

## 프롬프트 철칙 (references/ 가 "철칙 #N"으로 인용하는 목록)

위 **절대 규칙**은 운영 안전이고, 아래는 **프롬프트를 어떻게 쓰는가**다. 대부분 `check_prompt.mjs`가 기계적으로 잡는다 (괄호 안이 해당 코드).

1. **끝 토큰은 `AR x:y` 하나.** 앞머리 대괄호 금지, 슬롯은 한 글자도 남기지 않는다. (`E-AR-END`·`E-HEAD-BRACKET`·`E-SLOT-LEAK`)
2. **긍정형이 기본.** 배제는 "clean unbranded finish"처럼 긍정 상태로 쓴다. `no ~` 부정문은 Tier-1(텍스트 가드)·Tier-2(컴플라이언스 페어)의 캐노니컬 문구로만, 그것도 티어를 명시 선언했을 때만. (`E-NEG-001`·`E-NEG-SECTION`·`E-NEG-TIER`·`E-TIER2-*`)
3. **죽은 단어를 환원한다.** "beautiful", "high quality" 같은 채움말 대신 보이는 결과를 쓴다. SD 품질태그·MJ 플래그·가중치 문법은 쓰지 않는다. (`W-FILLER`·`E-SD-VOCAB`·`E-MJ-FLAG`·`E-WEIGHT`)
4. **장비명이 아니라 결과로 쓴다.** gpt-image-2는 카메라·조명 기재를 모른다. 빛·심도·질감·색으로 환원한다. (`E-CAM-LANG`·`E-LIGHT-LANG`)
5. **색은 HEX로 박고, 컷당 3~5색.** (`E-FMT-B-HEX`·`W-HEX-MISS`)
6. **1행 = 1컷 = 1호출.** 한 프롬프트가 여러 장을 그리게 하지 않는다. 그리드가 **단일 산출물 그 자체**일 때만 캔버스 내부 그리드를 허용한다 (`references/typography-layout.md` §6).
7. **모든 카피는 한 번씩만.** 이미지에 그릴 문구는 따옴표로 감싸 정확히 한 번 지정한다. 중복하면 모델이 두 번 그린다. (`E-TEXT-DUP`·`E-TEXT-QUOTE`)
8. **실재 상표·브랜드 폰트명 금지.** 서체는 계열+성격으로 서술한다. (`E-CAT-LANG`·`E-TEX-LANG`)
9. **트랙 A/B/C는 후처리 합성 금지.** 여러 생성물을 오려 붙이지 않는다. 틀린 컷만 다시 만들거나 7단계 국소 수리를 쓴다. 트랙 D의 배경+폰트 합성은 설계된 예외다.

## 워크플로 (트랙 A)

1. **사전 점검** → 2. **엔진·방향 확인 (AskUserQuestion 1회)** → 3. **프롬프트 고도화** → 4. **생성** → 5. **자가 검증** → 6. **리뷰 팝업** → 7. **수정 루프** → 8. **최종 보고**

### 1. 사전 점검 — 두 엔진의 가용성을 함께 본다

엔진은 2단계에서 정하므로, 여기서는 **어느 쪽이 후보가 될 수 있는지**를 먼저 확정한다. 쓸 수 없는 엔진을 선택지로 내밀면 사용자를 헛걸음시킨다.

```bash
codex --version && codex login status   # "Logged in using ChatGPT" + exit 0 → codex 사용 가능
grok  --version && grok models          # 첫 줄이 "You are logged in with ..." → grok 사용 가능
node --version           # 미설치 → 중단 아님. 3단계 린터만 건너뛰고 진행, 사용자에게 한 줄 고지
mkdir -p gpt-image       # 현재 프로젝트 루트에. 실패(권한) 시 중단하고 원인 안내
```

- **둘 다 불가면 중단**하고 안내한다 (`npm i -g @openai/codex` + `codex login` / `grok login`). 로그인은 대신 실행하지 않는다.
- **하나만 가능하면** 그 엔진으로 진행하고 2단계에서 엔진은 **묻지 않는다** — 선택지가 없는 질문은 방해일 뿐이다. 대신 어느 엔진을 왜 쓰는지 한 줄로 알린다.
- 사용자가 요청에서 엔진을 이미 지정했다면 그 엔진만 점검한다.
- grok 점검의 상세·실패 대응은 `references/engine-grok.md` §2·§7.

점검 통과 후 사용자에게 예상 소요 시간(장당 1~2분)을 알린다.

### 2. 엔진·방향 확인 (AskUserQuestion, 호출 1회)

생성 전에 **AskUserQuestion을 한 번** 호출해 엔진을 확정한다. 이미지 생성은 구독 한도를 실제로 깎고 장당 1~2분이 걸린다 — 엔진을 잘못 골라 다 만든 뒤 되돌리는 비용이 미리 묻는 비용보다 훨씬 크다. 반대로 여러 번 끊어 묻는 것도 낭비이므로 **호출은 한 번, 질문은 최대 2개**로 묶는다.

**묻지 않는 경우** (그냥 진행한다):
- 사용자가 엔진을 이미 지정했다 ("grok으로 만들어줘").
- 1단계에서 한쪽 엔진만 가용으로 판명됐다.
- **7단계 수정 루프의 재호출.** 엔진을 도중에 바꾸면 화풍이 튄다.

**질문 1 — 엔진 (항상 넣는다).** 위 엔진 선택 표로 추천을 먼저 계산해 **첫 번째 선택지에 놓고 라벨 끝에 "(추천)"** 을 붙인다. 왜 추천인지는 `description`에 이번 요청 기준으로 한 줄 적는다 — "한글이 유리해서"가 아니라 "이 슬라이드에 한글 카피 4줄이 들어가서"처럼 구체적으로.

```
AskUserQuestion(questions=[
  {header: "엔진", multiSelect: false,
   question: "이미지 생성 엔진을 골라주세요. 구독 한도가 차감됩니다.",
   options: [
     {label: "grok (추천)", description: "한글 카피가 4줄 들어감 — 1280×720에서 오탈자 0 실측. 16:9는 1280×720 고정."},
     {label: "codex",       description: "gpt-image-2. 최대 2048²·4:3 가능. 한글은 캔버스를 키워야 안정적."}]},
  # 아래는 모호할 때만 추가
  {header: "톤", multiSelect: false,
   question: "어떤 톤으로 갈까요?",
   options: [{label: "...", description: "..."}, {label: "...", description: "..."}]}
])
```

**질문 2 — 방향 (모호할 때만).** 주제·스타일이 크게 갈리는 요청이면 함께 묻는다. 충분히 구체적이면 이 질문은 **넣지 않는다.** 사용자가 "프롬프트 먼저 보여줘"라고 하면 고도화된 프롬프트를 보여주고 확인받은 뒤 생성한다.

사용자가 "Other"로 답하면 그 지시가 추천보다 우선한다. 확정된 엔진은 8단계 보고에 명시한다.

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
| Text | **A/B/C:** 필요한 문구(한글 포함)를 **정확한 철자 그대로** 프롬프트에 명시해 이미지에 직접 그린다. 문구는 따옴표로 감싸 "render exactly this text" 로 지시하고, 텍스트가 필요 없는 이미지만 "no text, no letters, no watermark". **D:** 카피를 배경 프롬프트에 넣지 않고 sketch의 글자 영역을 여백으로 둔다. |
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
| `engine-grok.md` | **grok 엔진으로 생성할 때** (사전 점검·호출·AR·회수·수정) |

**프롬프트 린터 — 생성 전에 돌린다** (쿼터를 쓰기 전에 잡는 게 싸다):

```bash
node "$HOME/.claude/skills/gpt-ppt-image/scripts/check_prompt.mjs" <프롬프트파일>
node "$HOME/.claude/skills/gpt-ppt-image/scripts/check_prompt.mjs" --jsonl <배치파일>   # 트랙 C
```

`ok:false` 면 **생성하지 말고** errors를 반영해 프롬프트를 고친 뒤 다시 돌린다. `E-INPUT` 은 프롬프트 문제가 아니라 파일 경로 오류다 — "통과"로 오해하지 말 것.

### 4. 생성 실행

파일명: `gpt-image/YYYYMMDD-HHMMSS-<slug>.png` (slug = 영문 소문자·하이픈, 사용자 지정 시 그것을 사용). 덱은 `gpt-image/<덱이름>/slide_01.png` 형식 (조립 스크립트가 이 패턴을 요구).

**grok 엔진이면 여기서부터 `references/engine-grok.md` §3~5로 간다** — 아래 size 표·`codex exec` 명령·정책훅 우회는 전부 codex 전용이다. grok에는 size 파라미터 자체가 없다(AR만 받는다). 파일명 규칙과 아래 AR 확정 원칙은 공통이다.

**Resolution은 `1K`/`2K` 같은 라벨이 아니라 실제 픽셀로 지시한다** — 검증 가능한 값은 6종 화이트리스트뿐이다 (`references/jsonl-and-examples.md` §1, `scripts/check_prompt.mjs`의 `SIZE_WHITELIST`):

| AR | size |
|---|---|
| 1:1 | `1024x1024` |
| 2:3 · 3:4 · 4:5 | `1024x1536` |
| 3:2 · 4:3 | `1536x1024` |
| 16:9 | `1792x1024` (덱 고정) |
| 9:16 | `1024x1792` |

한글 등 렌더 텍스트가 들어가면 **캔버스를 키운다.** 실측(`references/typography-layout.md`)상 글리프 정확도는 quality가 아니라 canvas 크기가 좌우한다 — `2048x2048`은 한글 카피 전 반복 만점(12/12), 실패는 전부 1024에서 발생했다. 1:1이면 `2048x2048`, 그 외 AR은 화이트리스트 상한인 1536 장변(`1536x1024`/`1024x1536`)으로 올린다.

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -o "<세션 스크래치패드>/codex-img-<slug>.txt" \
  "Use your image generation tool to create an image and save it to <절대경로 또는 gpt-image/파일명>.
Prompt: <고도화된 영문 프롬프트>
Resolution: <위 표에서 고른 size, 예 1024x1536>. Aspect ratio: <최종 배치처 비율 — 항상 명시>.
Do not do anything else. Reply with the saved file path."
```

- **Aspect ratio는 항상 명시한다.** 최종 배치처(슬라이드 박스, 히어로 영역 등)의 비율을 생성 **전에** 확정해 프롬프트에 넣는다. 생성 후에 비율을 맞추려면 크롭이나 letterbox 여백이 생겨 디자인이 깨진다. 덱은 16:9 고정.
- `-o` 파일은 **세션 스크래치패드에 장별로** 만든다 (`codex-img-<slug>.txt`). `/tmp` 고정 경로는 PowerShell에 없고, 한 파일 재사용은 배치 시 앞 장의 실패 진단을 덮어쓴다.
- Bash timeout: **360000ms** (장당). 배치는 장별로 순차 실행하며 진행 상황 `n/전체`를 보고.
- 배치 시 각 장마다 개별 고도화 프롬프트를 만든다.
- 실패 판별: `-o` 출력과 stderr에서 quota/usage limit(한도), content policy(정책 거부), 기타(일반 실패)를 구분한다. 대응은 아래 오류 표.
- **저장경로 정책훅 차단 우회(검증됨)**: 일부 환경에서 codex가 결과물을 `gpt-image/파일명`으로 복사하는 단계가 PreToolUse 정책훅에 "blocked by policy"로 차단된다. **이미지 자체는 codex 런타임 홈에 정상 생성**되므로, 이때는 codex 재시도 대신 런타임 홈에서 직접 회수한다.

  런타임 홈 경로는 codex 버전마다 바뀐다(0.144.1 → 0.144.6 → 0.145.0에서 3번 이동). **직접 glob 하지 말고 `latest_image.py`를 쓴다** — 이 스크립트는 알려진 경로를 모두 훑고 `CODEX_HOME`을 존중하며, 무엇보다 **신선도를 하드 게이트로 걸어** 오래된 생성물을 조용히 집어오지 않는다:

  ```bash
  T0=$(python "$HOME/.claude/skills/gpt-ppt-image/scripts/latest_image.py" --now)   # 생성 전에 찍는다
  codex exec ...                                                                    # 4단계 생성
  python "$HOME/.claude/skills/gpt-ppt-image/scripts/latest_image.py" \
    --since "$T0" --copy-to gpt-image/<파일명>.png
  ```

  - `-o` 출력에 저장 경로가 있으면 **그쪽을 우선 신뢰**하고, 없을 때만 위 회수를 쓴다.
  - exit 1이면 **그 시각 이후 생성물이 없다는 뜻**이다. 오래된 이미지를 대신 집어오지 않으니 그대로 실패로 보고한다. 원인 진단은 `latest_image.py --list`(루트별 최신 시각).
  - `T0`를 못 찍었으면 `--max-age 300`(최근 5분)으로 대체한다.

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

- 붓 경로는 easyocr·torch를 아예 로딩하지 않는다 — **장당 1초 미만** (핀 경로는 OCR 때문에 ~5초).
- 출력은 `<stem>-fixed.png` 새 파일 (원본 보존).
- 배경 복원은 자동으로 갈린다(`--fill auto`): 마스크 주변이 **단색이면 그 색으로 채워 오차 0**, 복잡하면 `cv2.inpaint`. 어느 쪽을 썼는지 `배경 복원:` 줄에 찍힌다.
- **한계**: 사진·그라디언트처럼 배경이 복잡하면 inpaint 자국이 남는다. `배경 복원: cv2.inpaint` 가 찍혔고 결과에 자국이 보이면 (c)의 재생성 경로로 보낸다. (단색 배경 자국은 해결됨 — 예전 문서의 '단색 헤더에도 옅은 사각 자국'은 더 이상 해당 없음)

**(b) 텍스트 핀(`pins`) = 텍스트 교체** → 같은 스크립트의 핀 경로:

```bash
python "$HOME/.claude/skills/gpt-ppt-image/scripts/repair_text.py" "<원본 절대경로>" \
  --pin "<x_pct>,<y_pct>:<교체할 정확한 문구>" [--pin ...]
```

- 동작: easyocr(CRAFT)로 텍스트 박스 검출 → 핀이 가리키는 박스만 배경 복원 → 원 글자색 추정 후 맑은 고딕 볼드 재기입. 장당 ~5초(모델 캐시 후), 한글 경로 안전.
- 의존성 최초 1회: `pip install easyocr opencv-python` (첫 실행 시 `~/.EasyOCR` 모델 다운로드).
- **상위 마스크 엔진 (GPU 장비)**: 텍스트가 그림 요소 위에 겹쳐 있으면 `--engine sam`으로 글자 획만 정밀 마스킹한다 (`pip install segment-anything` + 첫 실행 시 vit_b 체크포인트 375MB 자동 다운로드). 기본 `--engine auto`는 GPU(cuda)+설치가 확인될 때만 sam을 자동 선택하므로 CPU 장비는 그대로 사각형 방식이다. SAM 마스크가 퇴화하면 스크립트가 자동으로 사각형 폴백한다.
- 핀이 어느 텍스트 박스에도 안 붙으면 스크립트가 중단한다 → 그 영역은 붓(a)으로 다시 받는다.
- 수리 실패 시: 같은 한글 문구가 2회 연속 깨지면 중단하고 사용자에게 대안(문구 단순화·영문 전환·텍스트 제거)을 제안한다.

**(c) 그림 요소 수정** → `codex exec -i` 로 **한 번에** 재생성한다 (grok 엔진이면 `image_edit` — `references/engine-grok.md` §6. 좌표 번역·드리프트 방지 규칙은 동일하다). 핀 좌표(`x_pct`/`y_pct`)나 붓 마스크 bbox를 영역 서술로 번역한다: x <33 → left / <66 → center / 그 외 right, y 동일하게 top/middle/bottom. 5단계에서 이미지를 봤으므로 **그 위치의 실제 객체명을 함께 명시**한다 (예: "the logo in the upper-left region").

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
- **2회차 이상 루프에서는 보존 목록을 매번 다시 나열한다.** "Keep everything else identical" 한 줄만 반복하면 라운드가 거듭될수록 원본에서 멀어진다(드리프트). 앞 라운드에서 확정된 것을 범주별로 명시한다: `Keep unchanged: composition, palette, typography, and the <이전 라운드에서 승인된 요소>.`
- 수정본 저장 후 5단계(검증) → 6단계(수정본만 다시 리뷰 팝업)로 루프. 사용자가 "수정 없음(확정)"을 누를 때까지 반복. 루프당 생성 횟수를 보고에 표시.
- **자연어 수정 (경량 대안)**: 팝업 없이 사용자가 터미널에서 "더 어둡게" 등으로 지시하면 직전 생성물(또는 사용자가 지정한 기존 파일 — 없으면 생성 전에 알림)을 `-i`로 첨부해 동일하게 수정한다.

### 8. 최종 보고

저장 경로(들), 사용된 프롬프트 요약, 관찰평, (수정했다면) 수정 이력 요약을 한국어로 보고한다.

## 워크플로 (트랙 C)

1. **컴파일** — 요청을 jsonl 스키마(`references/jsonl-and-examples.md` §2)에 맞춰 1행 1컷으로 작성한다. `full_prompt` 끝에 `AR x:y`, `size`는 4단계 표에서 AR에 맞는 값, `output_path`는 `gpt-image/<카테고리>/<id>.png`.
2. **린트** — `node "$HOME/.claude/skills/gpt-ppt-image/scripts/check_prompt.mjs" --jsonl <배치파일>`. `ok:false`면 생성하지 말고 errors를 반영해 고친 뒤 재실행.
3. **핸드오프 또는 생성**
   - "프롬프트만 짜줘"류 요청 → 린트 통과한 jsonl을 산출물로 제출하고 종료한다.
   - 생성까지 요청이면 → jsonl의 각 행에 대해 트랙 A **4~7단계**를 순차 실행한다 (한 번에 한 컷, 배치는 챕터 단위 ≤10장/호출).
4. **보고** — 트랙 A 8단계와 동일하게 저장 경로들과 성공/실패 건수를 보고한다.

## 오류 대응

| 상황 | 감지 | 대응 |
|---|---|---|
| 한쪽 엔진 미설치·미로그인 | `codex login status` exit≠0 / `grok models`에 "logged in" 없음 | 중단 아님. 남은 엔진으로 진행하고 2단계에서 엔진은 묻지 않는다. 설치·로그인 안내는 한 줄만 |
| **양쪽 다 불가** | 위 두 점검이 모두 실패 | 중단. `npm i -g @openai/codex` + `codex login` / `grok login` 안내. 로그인을 대신 실행하지 않는다 |
| Node 미설치 | `node --version` 실패 | 중단 아님. 3단계 프롬프트 린터(`check_prompt.mjs`)를 건너뛰고 육안 검수로 대체, 생성은 그대로 진행 |
| 한도 초과 | 출력에 usage/rate limit 류 | 재시도 금지. Plus 한도 차감 사실 + 리셋 대기 안내 |
| 정책 거부 | 출력에 content policy 류 | 재시도 금지. 거부 사실 + 정책 내 표현 조정 방향 안내 |
| 타임아웃/일반 실패 | Bash timeout, 파일 미생성 | 원인 추정 + 다음 행동 안내. 자동 재시도 1회만 |
| 폴더 생성 실패 | mkdir 실패 | 중단. 권한·경로 확인 안내 |
| 저장경로 정책훅 차단 | 출력에 "blocked by policy"(복사 단계) | 재생성 금지. `latest_image.py --since` 로 회수(4단계 우회) |
| 회수 실패 (exit 1) | `latest_image.py` 가 신선한 생성물 없음 | **오래된 이미지로 대체하지 않는다.** `--list` 로 루트별 최신 시각 확인 후 실패 보고 |
| 팝업 실패 | 서버 기동/브라우저 실패 | URL 수동 안내 → 그래도 안 되면 자연어 수정 폴백 |
| 핀이 텍스트 박스에 안 붙음 | repair_text 중단 메시지 | 그 영역만 붓으로 다시 받는다 (7-a) |
| inpaint 자국 | `배경 복원: cv2.inpaint` + 결과 Read 확인 시 | 복잡한 배경이라는 뜻. 붓·핀 수리 포기하고 7-c 재생성으로 전환 |
| 배치 부분 실패 | 일부 파일 미생성 | `assemble_ppt.py <덱디렉터리> --status` 로 빠진 장 번호를 뽑아 **그 장만** 재생성. 성공분은 보존 |
| 한글이 계속 깨짐 | 같은 문구가 2회 연속 오탈자 | 재생성을 반복하지 말고 **트랙 D**로 전환한다. 덱은 장별 JSON을 `pptx`에 순서대로 넘겨 한 파일로 묶는다 |
| capture 실패 | Chrome/Edge 없음 | `pptx` 모드는 Chrome 없이 동작한다. 합성 PNG가 꼭 필요하면 Chrome 설치 안내 |
| grok 엔진의 실패 | 미설치·미로그인·승인 대기·경로 길이 초과 | `references/engine-grok.md` §7 표를 따른다 |

검증된 환경: codex-cli 0.144.1~0.145.0, grok 1.0.5(grok-4.6), Python 3.12~3.13, Node 20+, Windows Git Bash.

**생성물 저장 위치는 버전마다 바뀐다** — 실측 전례: codex 0.144.1 `codex-runtime-home/`, 0.144.6 `codex-accounts/<uuid>/`, 0.145.0 `CODEX_HOME` 또는 `~/.codex/`; grok 1.0.5 `~/.grok/sessions/<URL인코딩 cwd>/<세션UUID>/images/`. 그래서 경로를 문서에 박지 않고 `latest_image.py`가 두 엔진을 함께 흡수한다(`CODEX_HOME`·`GROK_HOME` 존중). 동작이 다르면 `codex --version`·`grok --version` 과 `latest_image.py --list` 부터 본다.

**Windows 인코딩 함정**: 값을 쉘로 뽑아 다시 넘기지 말 것. `python -c "print(...)"` 의 기본 stdout 은 cp949 라 한글이 깨진 채 다음 명령에 전달된다. 스크립트가 낸 JSON 은 **직접 읽어 파싱하고**, 명령에는 문구를 리터럴로 적는다.

## 스크립트 자기점검

로직을 건드렸다면 배포 전에 **전부** 돌린다 (무거운 의존성 없이 동작):

```bash
python scripts/repair_text.py  --selftest
python scripts/assemble_ppt.py --selftest    # 순수 로직 + build() 실제 실행
python scripts/latest_image.py --selftest
python scripts/sync_skill.py   --selftest
python scripts/test_coords.py  --selftest    # 붓 좌표 정규화→래스터화 수학
python scripts/layout_kit.py   demo          # sketch/render/pptx/capture/pixel_probe
node   scripts/check_prompt.mjs --test       # 픽스처 14종
```

이 저장소는 개발본이고 실제로 로드되는 것은 `~/.claude/skills/gpt-ppt-image/` 사본이다 — **심볼릭 링크가 아니라 실제 복사본이라, 고쳐도 복사하기 전까지는 반영되지 않는다.**

```bash
python scripts/sync_skill.py --check     # 어긋나면 exit 1 (커밋 전 게이트)
python scripts/sync_skill.py             # 반영
```
