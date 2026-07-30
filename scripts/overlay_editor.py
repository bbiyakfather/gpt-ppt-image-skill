#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대화형 오버레이 에디터 v2 — 서체·박스 스타일·레이어·핀 메모·참고 이미지·통짜 생성.

사용법:
    python overlay_editor.py <base.png> [--labels <labels.json>] [--timeout 570] [--no-open]

브라우저 기능:
  라벨   : [+ 라벨] → 더블클릭 타이핑 · 드래그 배치 · 서체/굵기/크기/글자색
  박스   : 모양(없음/둥근/각진) · 배경색 · 투명도 · 테두리색 — 색상마다 스포이드(💧, 이미지에서 추출)
  레이어 : [앞으로]/[뒤로]
  핀     : [📌 핀] 모드에서 클릭 → 번호 핀 + 메모 + 참고 이미지 첨부 (수정 지시용)
  제출   : [완료]=오버레이 캡처용 JSON / [통짜 생성]=텍스트 포함 AI 재생성 요청 / [취소]

stdout 마지막 줄 JSON 계약:
    {"action":"apply"|"generate","labels":[{text,x,y,size,family,weight,color,
        shape,bg,bgAlpha,border,z}],"pins":[{n,x,y,comment,image}]}
      x,y = 이미지 대비 % (중심) · size = 배경 원본 px · shape = none|pill|rect
      border = ""(없음) 또는 색상 hex · z = 레이어 순서 · pins[].image = 저장된 파일 경로 또는 null
    {"action":"cancel"} / {"action":"none","reason":"timeout"}

폰트 팔레트: assets/fonts/fonts.css (setup_fonts.py 선실행).
"""
import argparse
import base64
import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

FAMILIES = [
    ("Malgun Gothic", "맑은 고딕 (시스템)", [400, 700]),
    ("NanumSquare", "나눔스퀘어", [400, 700, 800]),
    ("Gmarket Sans", "G마켓 산스", [300, 400, 700]),
    ("KoPub Dotum", "KoPub 돋움", [300, 400, 700]),
    ("Noto Sans KR", "Noto Sans KR", [400, 700, 800]),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>overlay editor</title>
<link rel="stylesheet" href="/fonts.css">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#1e2430; font-family:'Malgun Gothic'; overflow:hidden; }
  #bars { position:fixed; top:0; left:0; right:0; z-index:50; background:#2a3242;
          color:#dfe6f0; font-size:12.5px; }
  .row { display:flex; align-items:center; gap:8px; padding:6px 12px; flex-wrap:nowrap; }
  .row + .row { border-top:1px solid #38445a; }
  .grp { display:flex; align-items:center; gap:4px; white-space:nowrap; }
  select,input,button { font-size:12.5px; padding:4px 7px; border-radius:6px;
          border:1px solid #46536a; background:#37415a; color:#eef2f8; }
  button { cursor:pointer; }
  input[type=color] { padding:1px; width:30px; height:26px; }
  input[type=range] { width:80px; padding:0; }
  input[type=number] { width:58px; }
  .drop { padding:4px 6px; }
  #add { background:#2b6cb0; }
  #pinmode.on { background:#b7791f; }
  #gen { background:#6b46c1; font-weight:700; }
  #done { background:#2f855a; font-weight:700; }
  #cancel { background:#823c3c; }
  .right { margin-left:auto; display:flex; gap:8px; }
  #wrap { position:absolute; top:76px; left:0; right:0; bottom:0;
          display:flex; align-items:center; justify-content:center; }
  #stage { position:relative; box-shadow:0 6px 30px rgba(0,0,0,.5); }
  #stage img.bg { display:block; user-select:none; -webkit-user-drag:none; }
  #stage.pinning { cursor:crosshair; }
  .lbl { position:absolute; transform:translate(-50%,-50%); white-space:pre;
         cursor:grab; outline:none; line-height:1.25; }
  .lbl.sel { box-shadow:0 0 0 2px #4c9aff !important; }
  .lbl[contenteditable="true"] { cursor:text; box-shadow:0 0 0 2px #f6ad55 !important; }
  .pin { position:absolute; transform:translate(-50%,-50%); width:26px; height:26px;
         border-radius:50%; background:#e53e3e; color:#fff; font-weight:700;
         display:flex; align-items:center; justify-content:center; cursor:grab;
         box-shadow:0 0 0 2px #fff, 0 2px 8px rgba(0,0,0,.4); z-index:900; font-size:13px; }
  #pop { position:fixed; z-index:1000; background:#2a3242; border:1px solid #46536a;
         border-radius:10px; padding:10px; width:280px; display:none; color:#dfe6f0; }
  #pop textarea { width:100%; height:64px; background:#1e2430; color:#eef2f8;
         border:1px solid #46536a; border-radius:6px; padding:6px; font-size:12.5px; resize:vertical; }
  #pop .thumb { max-width:100%; max-height:110px; margin-top:6px; border-radius:6px; display:none; }
  #pop .btns { display:flex; gap:6px; margin-top:8px; }
  #hint { position:fixed; bottom:8px; left:12px; color:#8fa0b8; font-size:11.5px; z-index:50; }
</style></head><body>
<div id="bars">
  <div class="row">
    <button id="add">+ 라벨</button>
    <button id="pinmode" title="핀 모드: 이미지를 클릭해 메모 핀 추가">📌 핀</button>
    <span class="grp">서체 <select id="family">__FAMILY_OPTIONS__</select>
      <select id="weight"></select></span>
    <span class="grp">크기 <input id="size" type="number" min="8" max="400" value="48"></span>
    <span class="grp">글자 <input id="color" type="color" value="#1b2f42">
      <button class="drop" data-pick="color" title="이미지에서 색 추출">💧</button></span>
    <button id="front">앞으로</button><button id="back">뒤로</button>
    <button id="del">삭제</button>
    <span class="right">
      <button id="gen" title="배치한 문구·위치·서체로 AI가 텍스트까지 통으로 그린 이미지를 생성">통짜 생성</button>
      <button id="done">완료</button><button id="cancel">취소</button></span>
  </div>
  <div class="row">
    <span class="grp">박스 <select id="shape">
      <option value="none">없음</option><option value="pill">둥근 박스</option>
      <option value="rect">각진 박스</option></select></span>
    <span class="grp">배경 <input id="bg" type="color" value="#ffffff">
      <button class="drop" data-pick="bg">💧</button></span>
    <span class="grp">투명도 <input id="bgAlpha" type="range" min="0" max="100" value="85">
      <span id="alphaVal">85%</span></span>
    <span class="grp"><label><input id="borderOn" type="checkbox"> 테두리</label>
      <input id="border" type="color" value="#123a5e">
      <button class="drop" data-pick="border">💧</button></span>
  </div>
</div>
<div id="wrap"><div id="stage"><img id="bg-img" class="bg" src="/img" draggable="false"></div></div>
<div id="pop">
  <div style="font-weight:700; margin-bottom:6px">핀 <span id="popN"></span> 메모</div>
  <textarea id="popText" placeholder="수정 지시나 메모를 남기세요"></textarea>
  <input id="popFile" type="file" accept="image/*" style="margin-top:6px; width:100%">
  <img id="popThumb" class="thumb">
  <div class="btns"><button id="popSave">저장</button><button id="popDel">핀 삭제</button></div>
</div>
<div id="hint">더블클릭=문구 입력 · 드래그=이동 · Delete=삭제 · 📌 핀 모드에서 이미지 클릭=메모 핀 · 💧=화면에서 색 추출</div>
<script>
const WEIGHTS = __WEIGHTS_JSON__;
const INIT = __INIT_LABELS__;
const bg = document.getElementById('bg-img'), stage = document.getElementById('stage');
const $ = id => document.getElementById(id);
const famSel=$('family'), wSel=$('weight'), sizeIn=$('size'), colorIn=$('color');
const shapeSel=$('shape'), bgIn=$('bg'), alphaIn=$('bgAlpha'), alphaVal=$('alphaVal');
const borderOn=$('borderOn'), borderIn=$('border');
let sel=null, natW=0, natH=0, scale=1, zTop=10, zBot=9, pinN=0, pinning=false, popPin=null;

function weightName(w){ return w>=800?'ExtraBold':(w>=700?'Bold':(w<=300?'Light':'Normal')); }
function fillWeights(fam, cur){
  wSel.innerHTML='';
  (WEIGHTS[fam]||[400,700]).forEach(w=>{
    const o=document.createElement('option'); o.value=w; o.textContent=weightName(w)+' ('+w+')';
    if(String(w)===String(cur)) o.selected=true; wSel.appendChild(o);
  });
}
function hexRgba(hex, pct){
  const n=parseInt(hex.slice(1),16);
  return `rgba(${n>>16&255},${n>>8&255},${n&255},${pct/100})`;
}
function fit(){
  scale=Math.min((innerWidth-40)/natW,(innerHeight-76-56)/natH,1);
  bg.style.width=(natW*scale)+'px'; bg.style.height=(natH*scale)+'px';
  document.querySelectorAll('.lbl').forEach(render);
  document.querySelectorAll('.pin').forEach(p=>{p.style.left=p.dataset.x+'%';p.style.top=p.dataset.y+'%';});
}
function render(el){
  const d=el.dataset;
  el.style.left=d.x+'%'; el.style.top=d.y+'%';
  el.style.fontFamily="'"+d.family+"'"; el.style.fontWeight=d.weight;
  el.style.fontSize=(d.size*scale)+'px'; el.style.color=d.color;
  el.style.zIndex=d.z;
  if(d.shape!=='none'){
    el.style.background=hexRgba(d.bg, +d.bgAlpha);
    el.style.borderRadius=d.shape==='pill' ? (12*scale)+'px' : '0';
    el.style.padding='0.28em 0.55em';
    el.style.border=d.border ? Math.max(1,3*scale)+'px solid '+d.border : 'none';
  } else {
    el.style.background='none'; el.style.border='none';
    el.style.padding='0'; el.style.borderRadius='0';
  }
}
function syncBar(el){
  const d=el.dataset;
  famSel.value=d.family; fillWeights(d.family,d.weight);
  sizeIn.value=d.size; colorIn.value=d.color;
  shapeSel.value=d.shape; bgIn.value=d.bg; alphaIn.value=d.bgAlpha;
  alphaVal.textContent=d.bgAlpha+'%';
  borderOn.checked=!!d.border; borderIn.value=d.border||'#123a5e';
}
function select(el){
  if(sel) sel.classList.remove('sel');
  sel=el;
  if(el){ el.classList.add('sel'); syncBar(el); }
}
function makeDraggable(el){
  el.addEventListener('pointerdown', ev=>{
    if(el.contentEditable==='true') return;
    if(el.classList.contains('lbl')) select(el);
    ev.preventDefault(); ev.stopPropagation();
    const r=stage.getBoundingClientRect();
    const move=mv=>{
      el.dataset.x=Math.min(100,Math.max(0,(mv.clientX-r.left)/r.width*100)).toFixed(2);
      el.dataset.y=Math.min(100,Math.max(0,(mv.clientY-r.top)/r.height*100)).toFixed(2);
      el.style.left=el.dataset.x+'%'; el.style.top=el.dataset.y+'%';
      if(el.classList.contains('lbl')) render(el);
    };
    const up=()=>{ removeEventListener('pointermove',move); removeEventListener('pointerup',up); };
    addEventListener('pointermove',move); addEventListener('pointerup',up);
  });
}
function addLabel(p){
  const el=document.createElement('div'); el.className='lbl'; el.contentEditable=false;
  el.textContent=p.text||'문구를 입력하세요';
  Object.assign(el.dataset,{x:p.x??50,y:p.y??50,size:p.size??48,
    family:p.family??'Malgun Gothic',weight:p.weight??700,color:p.color??'#1b2f42',
    shape:p.shape??'none',bg:p.bg??'#ffffff',bgAlpha:p.bgAlpha??85,
    border:p.border??'',z:p.z??(++zTop)});
  stage.appendChild(el); render(el); select(el); makeDraggable(el);
  el.addEventListener('dblclick',()=>{ el.contentEditable=true; el.focus();
    document.execCommand('selectAll',false,null); });
  el.addEventListener('blur',()=>{ el.contentEditable=false;
    if(!el.textContent.trim()){ el.remove(); if(sel===el) select(null); } });
  return el;
}
function addPin(xPct,yPct){
  const el=document.createElement('div'); el.className='pin';
  el.textContent=++pinN;
  Object.assign(el.dataset,{n:pinN,x:xPct.toFixed(2),y:yPct.toFixed(2)});
  el._comment=''; el._img=null; el._imgName='';
  el.style.left=el.dataset.x+'%'; el.style.top=el.dataset.y+'%';
  stage.appendChild(el); makeDraggable(el);
  el.addEventListener('click',ev=>{ ev.stopPropagation(); openPop(el); });
  openPop(el);
  return el;
}
function openPop(pin){
  popPin=pin;
  $('popN').textContent=pin.dataset.n;
  $('popText').value=pin._comment;
  const t=$('popThumb');
  if(pin._img){ t.src=pin._img; t.style.display='block'; } else t.style.display='none';
  $('popFile').value='';
  const pop=$('pop'), r=pin.getBoundingClientRect();
  pop.style.display='block';
  pop.style.left=Math.min(innerWidth-300,r.right+8)+'px';
  pop.style.top=Math.min(innerHeight-260,r.top)+'px';
}
$('popSave').onclick=()=>{ if(popPin) popPin._comment=$('popText').value;
  $('pop').style.display='none'; };
$('popDel').onclick=()=>{ if(popPin){ popPin.remove(); popPin=null; }
  $('pop').style.display='none'; };
$('popFile').addEventListener('change',e=>{
  const f=e.target.files[0]; if(!f||!popPin) return;
  const rd=new FileReader();
  rd.onload=()=>{ popPin._img=rd.result; popPin._imgName=f.name;
    const t=$('popThumb'); t.src=rd.result; t.style.display='block'; };
  rd.readAsDataURL(f);
});
famSel.addEventListener('change',()=>{ if(!sel) return;
  sel.dataset.family=famSel.value; fillWeights(famSel.value,null);
  sel.dataset.weight=wSel.value; render(sel); });
wSel.addEventListener('change',()=>{ if(sel){ sel.dataset.weight=wSel.value; render(sel);} });
sizeIn.addEventListener('input',()=>{ if(sel){ sel.dataset.size=sizeIn.value; render(sel);} });
colorIn.addEventListener('input',()=>{ if(sel){ sel.dataset.color=colorIn.value; render(sel);} });
shapeSel.addEventListener('change',()=>{ if(sel){ sel.dataset.shape=shapeSel.value; render(sel);} });
bgIn.addEventListener('input',()=>{ if(sel){ sel.dataset.bg=bgIn.value; render(sel);} });
alphaIn.addEventListener('input',()=>{ alphaVal.textContent=alphaIn.value+'%';
  if(sel){ sel.dataset.bgAlpha=alphaIn.value; render(sel);} });
borderOn.addEventListener('change',()=>{ if(sel){
  sel.dataset.border=borderOn.checked?borderIn.value:''; render(sel);} });
borderIn.addEventListener('input',()=>{ if(sel && borderOn.checked){
  sel.dataset.border=borderIn.value; render(sel);} });
document.querySelectorAll('.drop').forEach(btn=>{
  btn.addEventListener('click',async()=>{
    if(!window.EyeDropper){ alert('이 브라우저는 스포이드(EyeDropper)를 지원하지 않습니다'); return; }
    try{
      const {sRGBHex}=await new EyeDropper().open();
      const input=$(btn.dataset.pick); input.value=sRGBHex;
      input.dispatchEvent(new Event('input'));
      if(btn.dataset.pick==='border'){ borderOn.checked=true;
        borderOn.dispatchEvent(new Event('change')); }
    }catch(e){}
  });
});
$('front').onclick=()=>{ if(sel){ sel.dataset.z=++zTop; render(sel);} };
$('back').onclick=()=>{ if(sel){ sel.dataset.z=--zBot; render(sel);} };
$('add').onclick=()=>addLabel({});
$('del').onclick=()=>{ if(sel){ sel.remove(); select(null);} };
$('pinmode').onclick=()=>{ pinning=!pinning;
  $('pinmode').classList.toggle('on',pinning); stage.classList.toggle('pinning',pinning); };
stage.addEventListener('click',e=>{
  if(!pinning) return;
  if(e.target.closest('.lbl')||e.target.closest('.pin')) return;
  const r=stage.getBoundingClientRect();
  addPin((e.clientX-r.left)/r.width*100,(e.clientY-r.top)/r.height*100);
});
addEventListener('keydown',e=>{
  if(e.key==='Delete'&&sel&&sel.contentEditable!=='true'){ sel.remove(); select(null); }});
document.addEventListener('pointerdown',e=>{
  if(!e.target.closest('.lbl')&&!e.target.closest('#bars')&&!e.target.closest('#pop')
     &&!e.target.closest('.pin')) select(null); });
function collect(){
  return [...document.querySelectorAll('.lbl')].map(el=>({
    text:el.innerText, x:+el.dataset.x, y:+el.dataset.y, size:+el.dataset.size,
    family:el.dataset.family, weight:+el.dataset.weight, color:el.dataset.color,
    shape:el.dataset.shape, bg:el.dataset.bg, bgAlpha:+el.dataset.bgAlpha,
    border:el.dataset.border, z:+el.dataset.z }));
}
function collectPins(){
  return [...document.querySelectorAll('.pin')].map(el=>({
    n:+el.dataset.n, x:+el.dataset.x, y:+el.dataset.y,
    comment:el._comment, image:el._img, image_name:el._imgName }));
}
function post(action){
  fetch('/done',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action, labels:collect(), pins:collectPins()})})
  .then(()=>{ document.body.innerHTML=
    '<p style="color:#dfe6f0;padding:40px;font-size:18px">전송 완료 — 이 창을 닫아도 됩니다.</p>'; });
}
$('gen').onclick=()=>post('generate');
$('done').onclick=()=>post('apply');
$('cancel').onclick=()=>post('cancel');
bg.onload=()=>{ natW=bg.naturalWidth; natH=bg.naturalHeight; fit();
  INIT.forEach(addLabel); select(null); };
addEventListener('resize',fit);
</script></body></html>"""


def build_page(init_labels):
    fam_opts = "".join(f'<option value="{v}">{label}</option>' for v, label, _ in FAMILIES)
    weights = {v: ws for v, _, ws in FAMILIES}
    return (
        PAGE.replace("__FAMILY_OPTIONS__", fam_opts)
        .replace("__WEIGHTS_JSON__", json.dumps(weights, ensure_ascii=False))
        .replace("__INIT_LABELS__", json.dumps(init_labels, ensure_ascii=False))
    )


def save_pin_images(pins, base: Path):
    """pins[].image(dataURL) → base 옆 파일로 저장하고 경로로 치환."""
    out = []
    for p in pins:
        q = {k: p.get(k) for k in ("n", "x", "y", "comment")}
        data = p.get("image")
        if data and data.startswith("data:"):
            m = re.match(r"data:image/(\w+);base64,(.*)", data, re.S)
            if m:
                ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1), m.group(1))
                f = base.with_name(f"{base.stem}-pin{p['n']}.{ext}")
                f.write_bytes(base64.b64decode(m.group(2)))
                q["image"] = str(f)
            else:
                q["image"] = None
        else:
            q["image"] = None
        out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--labels")
    ap.add_argument("--timeout", type=int, default=570)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    base = Path(args.base).resolve()
    if not base.exists():
        print(json.dumps({"action": "error", "reason": f"file not found: {base}"}))
        sys.exit(1)
    init = []
    if args.labels:
        init = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    page = build_page(init).encode("utf-8")
    img = base.read_bytes()
    fonts_css = FONTS_DIR / "fonts.css"
    css = fonts_css.read_text(encoding="utf-8") if fonts_css.exists() else ""
    css = css.replace("url('", "url('/fonts/").encode("utf-8")

    result = {}
    done = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(page, "text/html; charset=utf-8")
            elif self.path == "/img":
                self._send(img, "image/png")
            elif self.path == "/fonts.css":
                self._send(css, "text/css")
            elif self.path.startswith("/fonts/"):
                f = FONTS_DIR / Path(self.path).name
                if f.exists():
                    self._send(f.read_bytes(), "font/ttf")
                else:
                    self.send_error(404)
            elif self.path == "/favicon.ico":
                self._send(b"", "image/x-icon")
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            action = body.get("action", "cancel")
            if action in ("apply", "generate"):
                result.update({
                    "action": action,
                    "labels": body.get("labels", []),
                    "pins": save_pin_images(body.get("pins", []), base),
                })
            else:
                result.update({"action": "cancel"})
            self._send(b"{}", "application/json")
            done.set()

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"editor: {url}", file=sys.stderr)
    if not args.no_open:
        webbrowser.open(url)
    if not done.wait(timeout=args.timeout):
        result.update({"action": "none", "reason": "timeout"})
    srv.shutdown()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
