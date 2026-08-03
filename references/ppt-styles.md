# 덱 스타일 12종 — 슬라이드 이미지 생성용

`docs/deck-workflow.md` 3단계에서 하나를 고른다. 고른 스타일의 **프롬프트 조각을 모든 장에 동일하게** 붙여야 덱이 통일된다.

조각은 영문이다 (gpt-image-2는 영문 지시에 더 안정적). 슬라이드에 들어갈 **문구 자체는 한국어 원문 그대로** 따옴표로 감싸 넘긴다.

| # | 스타일 | 언제 쓰나 |
|---|---|---|
| 1 | 클린 프로페셔널 | 기본값. 사내 보고, 범용 발표 |
| 2 | 크리에이티브 매거진 | 브랜드·마케팅, 시선을 끌어야 할 때 |
| 3 | 전자잉크 매거진 | 텍스트 위주, 차분한 읽을거리 |
| 4 | 데이터 대시보드 | 지표·차트가 주인공일 때 |
| 5 | 레트로 플랫 일러스트 | 친근한 설명, 대중 강연 |
| 6 | 손그림 기술 설명 | 구조·원리 설명, 엔지니어링 |
| 7 | 손그림 화이트보드 | 워크숍, 브레인스토밍 |
| 8 | 따뜻한 핸드메이드 | 사회공헌, 교육, 커뮤니티 |
| 9 | 연구 발표 | 학술 발표, 논문 요약 |
| 10 | 컨설팅 (맥킨지풍) | 경영 제안, 전략 보고 |
| 11 | 공공기관 정중체 | 정부·공공 보고, 사업 성과 |
| 12 | 교육용 코스웨어 | 강의자료, 교재 |

---

## 1. 클린 프로페셔널

깔끔한 여백, 절제된 색, 또렷한 위계. 어디에 내도 무난한 기본값.

```
Clean professional presentation slide, generous white space, single accent color
on a neutral light background, strong typographic hierarchy with one bold headline
and short supporting lines, thin rules as dividers, subtle flat icons, no clutter,
corporate but not stiff, 16:9 slide composition.
```

## 2. 크리에이티브 매거진

에디토리얼 레이아웃. 큰 사진, 과감한 여백, 비대칭 구성.

```
Editorial magazine-style presentation slide, bold asymmetric layout, oversized
display headline, full-bleed photography with a duotone treatment, generous
negative space, thin sans-serif captions, one confident accent color, art-directed
composition, 16:9 slide.
```

## 3. 전자잉크 매거진

흑백 위주 저채도, 종이 질감. 글을 읽히게 하는 스타일.

```
E-ink reader aesthetic presentation slide, near-monochrome palette, warm paper
white background with subtle grain, high-contrast black serif headline, calm
grey body text, minimal hairline rules, no gradients, no saturation, quiet and
highly legible, 16:9 slide.
```

## 4. 데이터 대시보드

지표 카드와 차트 중심. 숫자가 주인공.

```
Data dashboard presentation slide, dark navy background, KPI cards with large
numerals, clean line and bar charts with a restrained 3-color palette, thin grid
lines, monospaced figures, clear axis labels, analytical and precise, no decorative
illustration, 16:9 slide.
```

> 차트에 들어갈 **수치는 프롬프트에 정확히 명시**한다. 명시하지 않으면 모델이 그럴듯한 가짜 숫자를 그린다 — 정부·정산 문서에서는 치명적이다.

## 5. 레트로 플랫 일러스트

70~80년대 인쇄물 색감의 플랫 벡터.

```
Retro flat illustration presentation slide, muted vintage palette of mustard,
burnt orange, teal and cream, simple geometric shapes, halftone texture overlay,
thick friendly sans-serif headline, flat vector characters without gradients,
1970s print poster feel, 16:9 slide.
```

## 6. 손그림 기술 설명

노트에 그린 다이어그램 느낌. 구조·흐름 설명에 강하다.

```
Hand-drawn technical explainer slide, off-white paper background, ink-pen line
diagram with arrows and labeled callouts, light pencil shading, one highlighter
accent color, handwritten-style annotations, engineering notebook feel, clear
left-to-right flow, 16:9 slide.
```

## 7. 손그림 화이트보드

마커로 그린 화이트보드. 워크숍 톤.

```
Whiteboard sketch presentation slide, pure white background, bold marker strokes
in black with red and blue accents, rough hand-drawn boxes and arrows, sticky-note
shapes, informal workshop energy, generous space between elements, 16:9 slide.
```

## 8. 따뜻한 핸드메이드

수채·콜라주 질감. 사람 냄새 나는 주제에.

```
Warm handmade presentation slide, textured watercolor and torn-paper collage,
soft earth-tone palette of terracotta, sage and cream, gentle organic shapes,
rounded friendly typography, subtle paper fiber texture, human and approachable,
16:9 slide.
```

## 9. 연구 발표

학회 슬라이드. 정확하고 담백하게.

```
Academic research presentation slide, clean white background, structured sections
with numbered headings, precise diagrams and labeled figures, restrained blue and
grey palette, serif headline with sans-serif body, space reserved for citations,
rigorous and uncluttered, 16:9 slide.
```

## 10. 컨설팅 (맥킨지풍)

한 장 한 메시지. 액션 타이틀 + 근거 구조.

```
Management consulting presentation slide, white background, single action-title
headline across the top, structured horizontal framework of boxes and arrows
beneath it, disciplined navy and grey palette with one red highlight, dense but
orderly, source note in small type at the bottom, boardroom-ready, 16:9 slide.
```

> 이 스타일의 핵심은 **제목이 결론**이라는 것이다. "매출 현황"이 아니라 "매출은 3분기부터 반등했다"처럼 문장형 제목을 쓴다.

## 11. 공공기관 정중체

정부·공공 보고용. 단정하고 권위 있게.

```
Official public-sector report slide, clean white background with a solid header
band in deep navy or dark red, formal centered title, structured tables and
numbered sections, restrained accent color, conservative sans-serif typography,
ample margins, dignified and orderly, no playful elements, 16:9 slide.
```

> 기관명·사업명은 **공식 명칭 그대로** 프롬프트에 넣는다. 확인 안 된 기관명·인명은 넣지 않는다 (빈칸 > 잘못된 데이터).

## 12. 교육용 코스웨어

강의 자료. 단계와 예시가 잘 보이게.

```
Educational courseware slide, bright friendly background, clear numbered steps
with generous spacing, simple explanatory icons, one concept per slide, highlighted
key term in an accent color, rounded shapes, large readable type sized for a
classroom projector, 16:9 slide.
```

---

## 공통 주의

- **문구는 적게.** 내장 gpt-image-2는 해상도가 높지 않아 잔글씨가 먼저 뭉개진다. 한 장에 핵심 문구 3개 이내를 권한다.
- **한글 문구는 따옴표로 감싸 정확한 철자를 지시**하고, 생성 후 반드시 Read로 철자를 확인한다.
- 색·폰트 톤을 사용자가 지정했다면 스타일 조각보다 **사용자 지정이 우선**이다.
- 사용자 고유 스타일이 생기면 이 파일에 13번으로 추가한다.
