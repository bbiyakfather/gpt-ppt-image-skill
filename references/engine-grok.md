# 엔진: grok (image_gen / image_edit)

이 스킬의 기본 엔진은 codex(gpt-image-2)다. 이 문서는 **grok CLI로 생성할 때만** 읽는다.
프롬프트 철칙·린터·리뷰 팝업·`repair_text.py`·트랙 D 합성·`assemble_ppt.py`는 **엔진과 무관하게 그대로** 쓴다.
달라지는 건 네 곳뿐이다: 사전 점검 · 생성 호출 · 크기 · 저장/회수.

## 0. 왜 엔진이 둘인가 — 실측 비교

| 항목 | codex (gpt-image-2) | grok (image_gen) |
|---|---|---|
| 한글 카피 정확도 | 캔버스를 2048까지 키워야 안정. 그 아래에선 자주 깨짐 | **1280×720에서 2/2 만점** (숫자·퍼센트 포함, 아래 실측) |
| 해상도 | 6종 화이트리스트, 최대 2048×2048 | **픽셀 지시를 무시**하고 자체 사다리를 씀. 16:9 → 1280×720 |
| 이미지 수정 | `-i` 첨부 재생성 | `image_edit` — 구도·배경·기존 글자 보존 양호 (실측) |
| 저장 실패 모드 | 정책훅이 복사 단계를 차단 | 경로가 **Windows MAX_PATH(260자)** 를 넘으면 저장 실패 |
| 한도 | ChatGPT Plus 구독 | grok.com 구독 |

**실측 근거** (2026-08-25, grok 1.0.5 / grok-4.6):
`"2026년 상반기 사업계획"` + `"매출 성장과 원가 절감"` → 오탈자 0.
`"공정 자동화로 인건비 12% 절감"` 외 3줄 + `"3. 원가 절감 방안"` → 숫자(`3.4%`, `1.1%`, `8억원`) 포함 오탈자 0.
표본이 2건이므로 **보증이 아니라 우세**로 다룬다 — 5단계 자가 검증은 grok에서도 생략하지 않는다.

## 1. 엔진 선택 규칙

- 사용자가 엔진을 지정하면 **그대로 따른다.** ("grok으로 만들어줘" / "codex로")
- 이미지에 **한글·CJK 카피가 들어가면 grok 우선.** 트랙 D(폰트 합성)는 gpt-image-2의 한글 실패를 우회하려고 만든 트랙이라, grok에서는 강제 조건이 아니다.
  다만 **나중에 사용자가 글자를 직접 고쳐야 하면 여전히 트랙 D**다 — 이건 정확도 문제가 아니라 편집 가능성 문제라 엔진이 바꿔주지 못한다.
- **큰 캔버스가 필요하면 codex.** 인쇄물, 2K 이상, 1920×1080 슬라이드를 업스케일 없이 원하는 경우.
- 한쪽 **한도 소진 시 다른 쪽으로 폴백**한다. 이때 사용자에게 엔진이 바뀌었음과 그로 인한 차이(해상도·화풍)를 고지한다.

## 2. 사전 점검 (1단계 대체)

```bash
grok --version                 # 미설치 → 중단, 안내: https://grok.com CLI 설치
grok models                    # 첫 줄이 "You are logged in with ..." 이 아니면 → 중단, `grok login` 안내
mkdir -p gpt-image
```

`grok login`을 사용자 대신 실행하지 않는다 — codex와 동일한 규칙이다.

## 3. 생성 실행 (4단계 대체)

```bash
grok --always-approve --cwd "<짧은 절대경로>" \
  -p "Use your image_gen tool to create an image and save it to <절대경로>/gpt-image/<파일명>.png .
Prompt: <고도화된 영문 프롬프트>
Aspect ratio: <최종 배치처 비율>.
Do not do anything else. Reply with the absolute saved file path." 2>&1 | tail -20
```

- `--always-approve` 없이는 도구 실행 승인에서 멈춘다(비대화형이라 영원히 대기).
- `-p` 는 단발 프롬프트다. 출력은 모델의 진행 서술이 줄바꿈 없이 이어지다가 **마지막 줄에 저장 경로**가 온다. 그 줄만 신뢰하고, 나머지는 진단용으로만 읽는다.
- Bash timeout: **360000ms**(장당). codex와 동일하게 **한 번에 한 장씩 순차**.
- **`--cwd`는 반드시 짧은 경로로.** 이유는 §5.

## 4. 크기 — 픽셀 파라미터가 없다

`image_gen`에는 **size·resolution 파라미터가 존재하지 않는다.** 있는 것은 `aspect_ratio` 하나뿐이고, 값은
`auto`(기본) · `1:1` · `16:9` · `9:16` · `3:2` · `2:3` 이다. `Resolution: 1792x1024` 같은 지시는 조용히 무시된다
(실측: 1792×1024 요청 → 1280×720 반환, "1920×1080은 요청할 수 없다"고 도구가 직접 보고).

그래서 프롬프트에는 **AR만** 넣는다. 4단계 본문의 "한글이면 캔버스를 2048로 키운다"는 **codex 전용 지침**이라 grok에는 적용하지 않는다.

| AR | 반환 크기 | 근거 |
|---|---|---|
| 1:1 | 1024×1024 | 실측 |
| 16:9 | 1280×720 | 실측(2회) |
| 9:16 | 720×1280 | 실측 |
| 3:2 · 2:3 | 미실측 (긴 변 1280 계열로 추정) | 필요하면 한 장 뽑아 확인 |

- **codex에 있고 grok에 없는 AR이 있다** — `4:3` · `3:4` · `4:5`. 이 비율이 요구되면 codex로 보내거나, 가장 가까운 비율로 뽑아 트랙 D 합성에서 배치한다. AR을 사후 크롭으로 맞추지 않는다(구도가 깨진다).
- 덱(16:9)은 **1280×720**으로 나온다. 1920×1080 슬라이드에 넣으면 1.5배 업스케일이므로, **인쇄물이나 대형 스크린이면 codex로 보낸다.** 화면 발표용이면 실사용상 충분하다.
- 트랙 C jsonl의 `size` 필드는 그대로 6종 화이트리스트 값을 쓴다 — grok은 무시하지만, 그 값은 "의도한 산출 규격" 선언이라 린터를 통과시키고 나중에 codex로 재생성할 때 그대로 쓰인다.

## 5. 저장과 회수 (4단계 우회 대체)

grok은 생성물을 먼저 **세션 폴더**에 넣고 목적지로 복사한다:

```
~/.grok/sessions/<URL인코딩된 cwd>/<세션UUID>/images/<n>.jpg
```

경로에 cwd가 통째로 인코딩돼 들어가므로, **cwd가 길면 이 경로가 Windows MAX_PATH(260자)를 넘어 저장이 실패한다.**
실측: 세션 스크래치패드(약 130자) 아래에서 실행하니 `image_gen` 저장이 반복 실패했고, `F:/tmp/gk`에서는 한 번에 성공했다.

- **예방이 우선**: `--cwd`를 프로젝트 루트처럼 짧은 경로로 준다. 목적지 파일 경로도 짧게 유지한다.
- 그래도 실패했거나 마지막 줄에 경로가 없으면 **재생성하지 말고** codex와 같은 회수 경로를 쓴다. `latest_image.py`가 grok 세션 폴더도 훑는다 (`GROK_HOME` 존중, 신선도 하드 게이트 동일):

```bash
T0=$(python "$HOME/.claude/skills/gpt-ppt-image/scripts/latest_image.py" --now)   # 생성 전에 찍는다
grok --always-approve --cwd ... -p "..."
python "$HOME/.claude/skills/gpt-ppt-image/scripts/latest_image.py" \
  --since "$T0" --copy-to gpt-image/<파일명>.png
```

- exit 1이면 그 시각 이후 생성물이 **없다는 뜻**이다. 낡은 이미지를 대신 집어오지 않으니 그대로 실패로 보고한다. 진단은 `--list`.
- 세션 원본은 `.jpg`이고, `image_edit` 결과는 **`.png` 이름인데 내용이 JPEG**인 경우가 있다(실측). 파이프라인(PIL·cv2·python-pptx)은 확장자가 아니라 내용을 보므로 그대로 동작한다. 어떤 도구가 거부하면 `python -c "from PIL import Image; p=r'<경로>'; Image.open(p).save(p)"` 로 한 번 다시 저장한다.

## 6. 수정 (7-c 대체)

그림 요소 수정은 `image_edit`로 간다. 좌표→영역 번역 규칙(x <33 left / <66 center / 그 외 right, y도 동일)과 **2회차 이상에서 보존 목록을 매번 다시 나열**하는 드리프트 방지는 codex와 똑같이 적용한다.

```bash
grok --always-approve --cwd "<짧은 절대경로>" \
  -p "Edit the attached image <원본 절대경로> using your image_edit tool. Apply ONLY the following changes:
1) In the <region> region (about <x>% from left, <y>% from top), on the <객체명>: <핀 댓글>.
Keep every other area, style, composition, background and lighting identical to the source image.
Save the result to <절대경로>/gpt-image/<새 타임스탬프 파일명>.png.
Do not do anything else. Reply with the absolute saved file path."
```

- 실측상 구도·배경 질감·그림자·기존 글자를 잘 보존한다. 다만 지시한 변경이 **부분만 적용**될 수 있다(예: 머그 외벽만 바뀌고 내벽은 원색 유지). 5단계에서 확인하고, 남은 부분은 다음 라운드에 명시한다.
- **텍스트 교체는 여전히 `repair_text.py`가 먼저다** (쿼터 0, 다른 영역 변형 0). 재생성은 그림 요소 수정일 때만.

## 7. 오류 대응 (grok 전용 행)

| 상황 | 감지 | 대응 |
|---|---|---|
| grok 미설치 | `grok --version` 실패 | 중단. 설치 안내 |
| 미로그인 | `grok models` 첫 줄에 "logged in" 없음 | 중단. `grok login` 안내 |
| 승인 대기로 멈춤 | 타임아웃, 출력에 승인 문구 | `--always-approve` 누락. 플래그 추가 후 재실행 |
| 저장 실패(경로 길이) | 출력에 260/long path/persist 실패 | **재생성 금지.** 짧은 `--cwd`로 재시도하거나 `latest_image.py --since` 로 회수 |
| 마지막 줄에 경로 없음 | 출력 파싱 실패 | `latest_image.py --since` 로 회수. 그래도 없으면 실패 보고 |
| 한도 초과 | 출력에 usage/rate limit 류 | 재시도 금지. 구독 한도 고지 + codex 폴백을 제안 |
| 정책 거부 | 출력에 content policy 류 | 재시도 금지. 우회 변형 금지 — codex와 동일 |

검증된 환경: grok 1.0.5 (grok-4.6), Windows 11, Git Bash. `grok models` 로 사용 가능 모델을 확인한다.
