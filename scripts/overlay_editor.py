#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대화형 오버레이 에디터 — 배경 이미지 위에서 서체 선택·드래그 배치·직접 타이핑.

사용법:
    python overlay_editor.py <base.png> [--labels <labels.json>] [--timeout 570]

브라우저가 열리면: [라벨 추가] → 더블클릭으로 문구 입력, 드래그로 배치,
상단 툴바에서 서체/굵기/크기/색 변경 → [완료].

stdout 마지막 줄 JSON 계약:
    {"action":"apply","labels":[{"text","x","y","size","family","weight","color"}]}
      x,y = 이미지 대비 % (라벨 중심), size = 배경 원본 픽셀 기준 px
    {"action":"cancel"} / {"action":"none","reason":"timeout"}

폰트: assets/fonts/ 의 팔레트(fonts.css)를 서버가 서빙 — setup_fonts.py 선실행 필요.
"""
import argparse
import base64
import json
import socket
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
  #bar { position:fixed; top:0; left:0; right:0; height:52px; background:#2a3242;
         display:flex; align-items:center; gap:10px; padding:0 14px; z-index:50;
         color:#dfe6f0; font-size:13px; }
  #bar select,#bar input,#bar button { font-size:13px; padding:5px 8px; border-radius:6px;
         border:1px solid #46536a; background:#37415a; color:#eef2f8; }
  #bar button { cursor:pointer; }
  #add { background:#2b6cb0 !important; }
  #done { background:#2f855a !important; margin-left:auto; font-weight:700; }
  #cancel { background:#823c3c !important; }
  #size { width:64px; }
  #wrap { position:absolute; top:52px; left:0; right:0; bottom:0;
          display:flex; align-items:center; justify-content:center; }
  #stage { position:relative; box-shadow:0 6px 30px rgba(0,0,0,.5); }
  #stage img { display:block; user-select:none; -webkit-user-drag:none; }
  .lbl { position:absolute; transform:translate(-50%,-50%); white-space:pre;
         cursor:grab; outline:none; line-height:1.25; }
  .lbl.sel { box-shadow:0 0 0 2px #4c9aff; }
  .lbl[contenteditable="true"] { cursor:text; box-shadow:0 0 0 2px #f6ad55; }
  #hint { position:fixed; bottom:10px; left:14px; color:#8fa0b8; font-size:12px; z-index:50; }
</style></head><body>
<div id="bar">
  <button id="add">+ 라벨 추가</button>
  <select id="family">__FAMILY_OPTIONS__</select>
  <select id="weight"></select>
  <input id="size" type="number" min="8" max="400" value="48" title="크기(원본 px)">
  <input id="color" type="color" value="#1b2f42" title="색">
  <button id="del">삭제</button>
  <button id="done">완료</button>
  <button id="cancel">취소</button>
</div>
<div id="wrap"><div id="stage"><img id="bg" src="/img" draggable="false"></div></div>
<div id="hint">더블클릭=문구 입력 · 드래그=이동 · Delete=삭제 · 라벨 밖 클릭=선택 해제</div>
<script>
const WEIGHTS = __WEIGHTS_JSON__;
const INIT = __INIT_LABELS__;
const bg = document.getElementById('bg'), stage = document.getElementById('stage');
const famSel = document.getElementById('family'), wSel = document.getElementById('weight');
const sizeIn = document.getElementById('size'), colorIn = document.getElementById('color');
let sel = null, natW = 0, natH = 0, scale = 1;

function weightName(w){ return w>=800?'ExtraBold':(w>=700?'Bold':(w<=300?'Light':'Normal')); }
function fillWeights(fam, cur){
  wSel.innerHTML='';
  (WEIGHTS[fam]||[400,700]).forEach(w=>{
    const o=document.createElement('option'); o.value=w; o.textContent=weightName(w)+' ('+w+')';
    if(String(w)===String(cur)) o.selected=true; wSel.appendChild(o);
  });
}
function fit(){
  scale = Math.min((innerWidth-40)/natW, (innerHeight-52-60)/natH, 1);
  bg.style.width = (natW*scale)+'px'; bg.style.height = (natH*scale)+'px';
  document.querySelectorAll('.lbl').forEach(render);
}
function render(el){
  const d = el.dataset;
  el.style.left = d.x+'%'; el.style.top = d.y+'%';
  el.style.fontFamily = "'"+d.family+"'";
  el.style.fontWeight = d.weight;
  el.style.fontSize = (d.size*scale)+'px';
  el.style.color = d.color;
}
function select(el){
  if(sel) sel.classList.remove('sel');
  sel = el;
  if(el){ el.classList.add('sel');
    famSel.value = el.dataset.family; fillWeights(el.dataset.family, el.dataset.weight);
    sizeIn.value = el.dataset.size; colorIn.value = el.dataset.color; }
}
function addLabel(p){
  const el = document.createElement('div'); el.className='lbl'; el.contentEditable=false;
  el.textContent = p.text||'문구를 입력하세요';
  Object.assign(el.dataset, {x:p.x??50, y:p.y??50, size:p.size??48,
    family:p.family??'Malgun Gothic', weight:p.weight??700, color:p.color??'#1b2f42'});
  stage.appendChild(el); render(el); select(el);
  el.addEventListener('pointerdown', ev=>{
    if(el.contentEditable==='true') return;
    select(el); ev.preventDefault();
    const r = stage.getBoundingClientRect();
    const move = mv=>{
      el.dataset.x = Math.min(100, Math.max(0, (mv.clientX-r.left)/r.width*100)).toFixed(2);
      el.dataset.y = Math.min(100, Math.max(0, (mv.clientY-r.top)/r.height*100)).toFixed(2);
      render(el);
    };
    const up = ()=>{ removeEventListener('pointermove',move); removeEventListener('pointerup',up); };
    addEventListener('pointermove',move); addEventListener('pointerup',up);
  });
  el.addEventListener('dblclick', ()=>{ el.contentEditable=true; el.focus();
    document.execCommand('selectAll',false,null); });
  el.addEventListener('blur', ()=>{ el.contentEditable=false;
    if(!el.textContent.trim()){ el.remove(); if(sel===el) select(null); } });
  return el;
}
famSel.addEventListener('change', ()=>{ if(!sel) return;
  sel.dataset.family=famSel.value; fillWeights(famSel.value, null);
  sel.dataset.weight=wSel.value; render(sel); });
wSel.addEventListener('change', ()=>{ if(sel){ sel.dataset.weight=wSel.value; render(sel);} });
sizeIn.addEventListener('input', ()=>{ if(sel){ sel.dataset.size=sizeIn.value; render(sel);} });
colorIn.addEventListener('input', ()=>{ if(sel){ sel.dataset.color=colorIn.value; render(sel);} });
document.getElementById('add').onclick = ()=>addLabel({});
document.getElementById('del').onclick = ()=>{ if(sel){ sel.remove(); select(null);} };
addEventListener('keydown', e=>{
  if(e.key==='Delete' && sel && sel.contentEditable!=='true'){ sel.remove(); select(null); }});
document.addEventListener('pointerdown', e=>{
  if(!e.target.closest('.lbl') && !e.target.closest('#bar')) select(null); });
function collect(){
  return [...document.querySelectorAll('.lbl')].map(el=>({
    text: el.innerText, x:+el.dataset.x, y:+el.dataset.y, size:+el.dataset.size,
    family: el.dataset.family, weight:+el.dataset.weight, color: el.dataset.color }));
}
function post(path, body){
  fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)}).then(()=>{ document.body.innerHTML =
    '<p style="color:#dfe6f0;padding:40px;font-size:18px">전송 완료 — 이 창을 닫아도 됩니다.</p>'; });
}
document.getElementById('done').onclick = ()=>post('/done',{labels:collect()});
document.getElementById('cancel').onclick = ()=>post('/cancel',{});
bg.onload = ()=>{ natW=bg.naturalWidth; natH=bg.naturalHeight; fit();
  INIT.forEach(addLabel); select(null); };
addEventListener('resize', fit);
</script></body></html>"""


def build_page(init_labels):
    fam_opts = "".join(
        f'<option value="{v}">{label}</option>' for v, label, _ in FAMILIES
    )
    weights = {v: ws for v, _, ws in FAMILIES}
    return (
        PAGE.replace("__FAMILY_OPTIONS__", fam_opts)
        .replace("__WEIGHTS_JSON__", json.dumps(weights, ensure_ascii=False))
        .replace("__INIT_LABELS__", json.dumps(init_labels, ensure_ascii=False))
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--labels")
    ap.add_argument("--timeout", type=int, default=570)
    ap.add_argument("--no-open", action="store_true", help="브라우저 자동 열기 생략(자동화 테스트용)")
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
    fonts_css = (FONTS_DIR / "fonts.css")
    css = fonts_css.read_text(encoding="utf-8") if fonts_css.exists() else ""
    # fonts.css 의 상대 url() 을 서버 경로로 치환
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
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/done":
                result.update({"action": "apply", "labels": body.get("labels", [])})
            else:
                result.update({"action": "cancel"})
            self._send(b"{}", "application/json")
            done.set()

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = HTTPServer(("127.0.0.1", port), H)
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
