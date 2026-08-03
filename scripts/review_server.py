#!/usr/bin/env python3
"""One-shot local review server for the gpt-ppt-image skill.

Usage:  python review_server.py IMAGE [IMAGE ...] [--timeout SECONDS] [--mask-dir DIR]

Serves a review page on 127.0.0.1:<random port>, opens the default browser,
waits for a single submission (or timeout), prints the result JSON to stdout,
then exits. Nothing keeps running afterwards.

Two ways to mark a fix:
  pin    — click a spot, leave a comment. Coordinates come back as percentages.
  brush  — paint a region, leave a comment. Saved as a binary mask PNG at the
           image's ORIGINAL resolution, ready for `repair_text.py --mask`.

Brush strokes are stored in normalized (0..1) coordinates and re-rasterized
against naturalWidth/naturalHeight on submit, so the mask is exact regardless
of how the image was scaled on screen.

Output JSON (stdout, single line):
  {"action": "edit"|"none", "reason": "user"|"timeout",
   "images": [{"file": "<abs path>",
               "pins":    [{"n": 1, "x_pct": 12.3, "y_pct": 45.6, "comment": "..."}],
               "regions": [{"n": 1, "mask": "<abs png path>", "comment": "..."}]}]}
  or, when an input file is missing (exit 1):
  {"action": "error", "reason": "file not found: <path>"}
"""
import argparse
import base64
import binascii
import json
import mimetypes
import os
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>이미지 리뷰 — 핀·붓으로 수정 지시</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#16181d;color:#e8e8ea}
 header{padding:12px 20px;background:#1f2229;display:flex;gap:10px;align-items:center;position:sticky;top:0;z-index:10;flex-wrap:wrap}
 header h1{font-size:15px;margin:0;flex:1;font-weight:600;min-width:200px}
 button{border:0;border-radius:8px;padding:9px 16px;font-size:13px;cursor:pointer;font-weight:600}
 #btn-edit{background:#7c5cff;color:#fff} #btn-none{background:#3a3f4b;color:#e8e8ea}
 #btn-back{background:#3a3f4b;color:#e8e8ea;display:none}
 .tool{background:#2a2e38;color:#aab} .tool.on{background:#7c5cff;color:#fff}
 #brushbar{display:none;align-items:center;gap:8px;font-size:12px;color:#aab}
 #brushbar input[type=range]{width:110px}
 main{display:flex;gap:16px;padding:16px 20px;align-items:flex-start}
 #stage{flex:1;min-width:0}
 #gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
 .thumb{background:#1f2229;border-radius:10px;padding:10px;cursor:pointer;border:2px solid transparent}
 .thumb:hover{border-color:#7c5cff}
 .thumb img{width:100%;border-radius:6px;display:block}
 .thumb .cap{font-size:12px;margin-top:8px;color:#aab;display:flex;justify-content:space-between;gap:6px}
 .badge{background:#7c5cff;border-radius:10px;padding:0 8px;color:#fff}
 .badge2{background:#2ea8a0;border-radius:10px;padding:0 8px;color:#fff}
 #imgwrap{position:relative;display:inline-block;max-width:100%;line-height:0}
 #imgwrap img{max-width:100%;display:block;border-radius:8px}
 #paint{position:absolute;left:0;top:0;border-radius:8px;touch-action:none}
 .pin{position:absolute;width:24px;height:24px;margin:-24px 0 0 -12px;background:#7c5cff;color:#fff;
      border-radius:50% 50% 50% 0;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;
      font-size:12px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.5);pointer-events:none}
 .pin span{transform:rotate(45deg)}
 #side{width:310px;flex-shrink:0}
 .row{background:#1f2229;border-radius:10px;padding:10px;margin-bottom:10px;border-left:4px solid #7c5cff}
 .row.rg{border-left-color:#2ea8a0}
 .row.active{outline:2px solid #2ea8a0}
 .row .head{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px;color:#aab;gap:6px;align-items:center}
 .row .del{color:#f66;cursor:pointer;background:none;padding:0;font-size:12px;font-weight:600}
 .row .pick{color:#2ea8a0;cursor:pointer;background:none;padding:0;font-size:12px;font-weight:600}
 textarea{width:100%;box-sizing:border-box;background:#16181d;color:#e8e8ea;border:1px solid #3a3f4b;
          border-radius:6px;padding:6px;font-size:13px;resize:vertical;min-height:48px;font-family:inherit}
 .hint{color:#889;font-size:13px;margin-bottom:10px;line-height:1.5}
 #done{padding:60px;text-align:center;font-size:16px}
</style></head><body>
<header>
 <button id="btn-back" onclick="showGallery()">← 갤러리</button>
 <h1 id="title">이미지 리뷰</h1>
 <button class="tool on" id="t-pin" onclick="setMode('pin')">📍 핀</button>
 <button class="tool" id="t-brush" onclick="setMode('brush')">🖌️ 붓</button>
 <span id="brushbar">
   <button class="tool" onclick="newRegion()">+ 새 영역</button>
   <label>굵기 <input type="range" id="bsize" min="4" max="120" value="28"></label>
   <button class="tool" id="t-erase" onclick="toggleErase()">지우개</button>
 </span>
 <button id="btn-edit">수정 요청 보내기</button>
 <button id="btn-none">수정 없음 (확정)</button>
</header>
<main>
 <div id="stage"></div>
 <div id="side"></div>
</main>
<script>
const IMAGES = __IMAGES__;                 // [{name}]
const pins    = IMAGES.map(()=>[]);        // [{x,y,comment}]  (percent)
const regions = IMAGES.map(()=>[]);        // [{strokes:[{pts:[[x,y]..],r}], comment}]  (0..1)
let cur = 0, mode = 'pin', activeRegion = -1, erasing = false;
const stage = document.getElementById('stage'), side = document.getElementById('side');
const REGION_COLORS = ['#2ea8a0','#e8794a','#4a8ee8','#c95ac9','#9ab63c','#d8b13a'];
const rc = n => REGION_COLORS[n % REGION_COLORS.length];

function setMode(m){
  mode = m;
  document.getElementById('t-pin').classList.toggle('on', m==='pin');
  document.getElementById('t-brush').classList.toggle('on', m==='brush');
  document.getElementById('brushbar').style.display = m==='brush' ? 'flex' : 'none';
  const img = document.getElementById('theimg');
  if(img) img.style.cursor = m==='pin' ? 'crosshair' : 'default';
  const pc = document.getElementById('paint');
  if(pc) pc.style.cursor = m==='brush' ? 'crosshair' : 'default';
  if(m==='brush' && regions[cur].length===0) newRegion();
  render();
}
function toggleErase(){
  erasing = !erasing;
  document.getElementById('t-erase').classList.toggle('on', erasing);
}
function newRegion(){
  regions[cur].push({strokes:[], comment:''});
  activeRegion = regions[cur].length - 1;
  render();
}
function pickRegion(n){ activeRegion = n; render(); }

function showGallery(){
  document.getElementById('btn-back').style.display='none';
  document.getElementById('title').textContent = '갤러리 — 수정할 이미지를 클릭하세요 (' + IMAGES.length + '장)';
  side.innerHTML='';
  stage.innerHTML = '<div id="gallery">' + IMAGES.map((im,i)=>{
    const b = [];
    if(pins[i].length)    b.push('<span class="badge">핀 '+pins[i].length+'</span>');
    const rn = regions[i].filter(r=>r.strokes.length).length;
    if(rn)                b.push('<span class="badge2">영역 '+rn+'</span>');
    return '<div class="thumb" onclick="showImage('+i+')"><img src="/img/'+i+'">'+
           '<div class="cap"><span>'+im.name+'</span><span>'+b.join(' ')+'</span></div></div>';
  }).join('') + '</div>';
}

function showImage(i){
  cur = i;
  activeRegion = regions[i].length ? 0 : -1;
  if(IMAGES.length>1) document.getElementById('btn-back').style.display='inline-block';
  document.getElementById('title').textContent = IMAGES[i].name;
  stage.innerHTML =
    '<div class="hint">📍 <b>핀</b>: 고칠 지점을 클릭 → 댓글. 그림 요소 수정에 씁니다.<br>' +
    '🖌️ <b>붓</b>: 고칠 영역을 칠하고 → 바꿀 <b>정확한 문구</b>를 적습니다. ' +
    '글자가 뭉개졌거나 장식 폰트라 핀이 안 잡힐 때 씁니다.</div>' +
    '<div id="imgwrap"><img id="theimg" src="/img/'+i+'"><canvas id="paint"></canvas></div>';

  const img = document.getElementById('theimg');
  img.addEventListener('load', fitCanvas);
  if(img.complete) fitCanvas();
  window.addEventListener('resize', fitCanvas);
  setMode(mode);
}

function fitCanvas(){
  const img = document.getElementById('theimg'), pc = document.getElementById('paint');
  if(!img || !pc) return;
  pc.width  = img.clientWidth;      // 표시 크기 = 화면 렌더 해상도
  pc.height = img.clientHeight;
  pc.style.width = img.clientWidth+'px';
  pc.style.height = img.clientHeight+'px';
  bindPaint(pc);
  render();
}

let bound = null;
function bindPaint(pc){
  if(bound === pc) return;
  bound = pc;
  let drawing = false;
  const pos = ev => {
    const r = pc.getBoundingClientRect();
    return [(ev.clientX-r.left)/r.width, (ev.clientY-r.top)/r.height];   // 0..1 정규화
  };
  pc.addEventListener('pointerdown', ev=>{
    const [x,y] = pos(ev);
    if(mode==='pin'){
      pins[cur].push({x:x*100, y:y*100, comment:''});
      render();
      return;
    }
    if(activeRegion < 0) newRegion();
    if(erasing){ eraseAt(x,y); render(); return; }
    drawing = true;
    pc.setPointerCapture(ev.pointerId);
    const r = document.getElementById('bsize').value / pc.width / 2;   // 반경도 정규화
    regions[cur][activeRegion].strokes.push({pts:[[x,y]], r:r});
    render();
  });
  pc.addEventListener('pointermove', ev=>{
    if(!drawing || mode!=='brush') return;
    const [x,y] = pos(ev);
    const st = regions[cur][activeRegion].strokes;
    st[st.length-1].pts.push([x,y]);
    render();
  });
  const stop = ()=>{ drawing = false; };
  pc.addEventListener('pointerup', stop);
  pc.addEventListener('pointercancel', stop);
  pc.addEventListener('pointerleave', stop);
}

function eraseAt(x,y){
  // 지우개: 커서에 걸리는 스트로크를 통째로 제거 (픽셀 단위 지우기는 과함)
  const pc = document.getElementById('paint');
  const tol = document.getElementById('bsize').value / pc.width / 2;
  for(const rg of regions[cur]){
    rg.strokes = rg.strokes.filter(s =>
      !s.pts.some(p => Math.hypot(p[0]-x, p[1]-y) < s.r + tol));
  }
}

function paintStrokes(ctx, w, h, strokes, style){
  ctx.strokeStyle = style; ctx.fillStyle = style;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for(const s of strokes){
    const lw = Math.max(1, s.r * 2 * w);
    ctx.lineWidth = lw;
    if(s.pts.length === 1){                       // 점 하나 = 원 하나
      ctx.beginPath(); ctx.arc(s.pts[0][0]*w, s.pts[0][1]*h, lw/2, 0, Math.PI*2); ctx.fill();
      continue;
    }
    ctx.beginPath();
    ctx.moveTo(s.pts[0][0]*w, s.pts[0][1]*h);
    for(let i=1;i<s.pts.length;i++) ctx.lineTo(s.pts[i][0]*w, s.pts[i][1]*h);
    ctx.stroke();
  }
}

function render(){
  const wrap = document.getElementById('imgwrap');
  if(!wrap) return;
  wrap.querySelectorAll('.pin').forEach(p=>p.remove());
  pins[cur].forEach((p,n)=>{
    const d = document.createElement('div'); d.className='pin';
    d.style.left=p.x+'%'; d.style.top=p.y+'%'; d.innerHTML='<span>'+(n+1)+'</span>';
    wrap.appendChild(d);
  });

  const pc = document.getElementById('paint');
  if(pc){
    const ctx = pc.getContext('2d');
    ctx.clearRect(0,0,pc.width,pc.height);
    regions[cur].forEach((rg,n)=>{
      ctx.globalAlpha = (n===activeRegion && mode==='brush') ? 0.55 : 0.32;
      paintStrokes(ctx, pc.width, pc.height, rg.strokes, rc(n));
    });
    ctx.globalAlpha = 1;
    pc.style.pointerEvents = 'auto';
  }

  const pinRows = pins[cur].map((p,n)=>
    '<div class="row"><div class="head"><b>📍 핀 '+(n+1)+'</b>'+
    '<span>'+p.x.toFixed(1)+'%, '+p.y.toFixed(1)+'%</span>'+
    '<button class="del" onclick="delPin('+n+')">삭제</button></div>'+
    '<textarea placeholder="수정 내용 (예: 이 로고 더 크게)" '+
    'oninput="pins['+cur+']['+n+'].comment=this.value">'+esc(p.comment)+'</textarea></div>').join('');

  const rgRows = regions[cur].map((rg,n)=>
    '<div class="row rg'+(n===activeRegion?' active':'')+'" style="border-left-color:'+rc(n)+'">'+
    '<div class="head"><b style="color:'+rc(n)+'">🖌️ 영역 '+(n+1)+'</b>'+
    '<span>'+(rg.strokes.length?rg.strokes.length+'획':'<i>미착색</i>')+'</span>'+
    (n===activeRegion?'<span style="color:#2ea8a0">● 선택됨</span>':
      '<button class="pick" onclick="pickRegion('+n+')">선택</button>')+
    '<button class="del" onclick="delRegion('+n+')">삭제</button></div>'+
    '<textarea placeholder="이 영역에 들어갈 정확한 문구" '+
    'oninput="regions['+cur+']['+n+'].comment=this.value">'+esc(rg.comment)+'</textarea></div>').join('');

  side.innerHTML = (pinRows + rgRows) || '<div class="hint">아직 핀도 영역도 없습니다.</div>';
}
function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function delPin(n){ pins[cur].splice(n,1); render(); }
function delRegion(n){
  regions[cur].splice(n,1);
  if(activeRegion >= regions[cur].length) activeRegion = regions[cur].length-1;
  render();
}

function maskPNG(i, rg){
  // 원본 해상도로 재래스터화 — 화면 표시 배율과 무관하게 정확한 마스크가 나온다.
  const img = document.getElementById('theimg');
  const w = img.naturalWidth, h = img.naturalHeight;
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillRect(0,0,w,h);
  paintStrokes(ctx, w, h, rg.strokes, '#fff');
  return c.toDataURL('image/png');
}

function submit(action){
  const imgs = [];
  for(let i=0;i<IMAGES.length;i++){
    const rs = regions[i].filter(r=>r.strokes.length);
    if(!pins[i].length && !rs.length) continue;
    imgs.push({idx:i,
      pins: pins[i].map((p,n)=>({n:n+1, x_pct:+p.x.toFixed(1), y_pct:+p.y.toFixed(1),
                                 comment:p.comment.trim()})),
      regions: rs.map((r,n)=>({n:n+1, comment:r.comment.trim(),
                               png: i===cur ? maskPNG(i,r) : r._png}))});
  }
  if(action==='edit'){
    if(!imgs.length){
      alert('핀도 영역도 없습니다. 고칠 곳을 표시하거나 "수정 없음 (확정)"을 누르세요.');
      return;
    }
    const empty = [];
    imgs.forEach(x=>{
      x.pins.forEach(p=>{ if(!p.comment) empty.push('핀 '+p.n); });
      x.regions.forEach(r=>{ if(!r.comment) empty.push('영역 '+r.n); });
    });
    if(empty.length){
      alert('댓글이 비어 있습니다: '+empty.join(', ')+'\\n내용을 적거나 삭제하세요.');
      return;
    }
    const lost = imgs.some(x=>x.regions.some(r=>!r.png));
    if(lost){
      alert('다른 이미지의 붓 영역은 그 이미지를 연 상태에서만 저장됩니다.\\n' +
            '갤러리에서 해당 이미지를 열었다가 다시 보내주세요.');
      return;
    }
  }
  if(action==='none'){
    const n = imgs.reduce((s,x)=>s+x.pins.length+x.regions.length,0);
    if(n>0 && !confirm('표시해둔 '+n+'개가 버려집니다. 정말 수정 없이 확정할까요?')) return;
  }
  fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:action, images:imgs})})
    .then(r=>r.json())
    .then(j=>{
      if(!j.ok){ alert('저장 실패: '+(j.error||'unknown')); return; }
      document.body.innerHTML='<div id="done">✅ 전송 완료 — 이 창을 닫고 Claude Code로 돌아가세요.</div>';
    })
    .catch(e=>alert('전송 실패: '+e));
}

// 이미지를 떠나기 전에 그 이미지의 마스크를 굳혀둔다 (canvas 는 현재 이미지만 그린다)
function freezeCurrent(){
  const img = document.getElementById('theimg');
  if(!img || !img.naturalWidth) return;
  regions[cur].forEach(rg=>{ if(rg.strokes.length) rg._png = maskPNG(cur, rg); });
}
const _showGallery = showGallery, _showImage = showImage;
showGallery = function(){ freezeCurrent(); _showGallery(); };
showImage  = function(i){ freezeCurrent(); _showImage(i); };

document.getElementById('btn-edit').onclick = ()=>submit('edit');
document.getElementById('btn-none').onclick = ()=>submit('none');
IMAGES.length>1 ? showGallery() : showImage(0);
</script></body></html>"""


def save_mask(data_url, out_path):
    """'data:image/png;base64,...' -> PNG 파일. 성공하면 절대경로, 실패하면 예외."""
    prefix = "data:image/png;base64,"
    if not isinstance(data_url, str) or not data_url.startswith(prefix):
        raise ValueError("mask is not a base64 png data URL")
    raw = base64.b64decode(data_url[len(prefix):], validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("decoded mask is not a PNG")
    with open(out_path, "wb") as f:
        f.write(raw)
    return os.path.abspath(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--timeout", type=int, default=570, help="seconds to wait before auto-confirm")
    ap.add_argument("--mask-dir", help="brush mask output dir (default: a fresh temp dir)")
    a = ap.parse_args()

    paths = [os.path.abspath(p) for p in a.images]
    for p in paths:
        if not os.path.isfile(p):
            print(json.dumps({"action": "error", "reason": "file not found: " + p}))
            sys.exit(1)

    mask_dir = a.mask_dir or tempfile.mkdtemp(prefix="review-mask-")
    os.makedirs(mask_dir, exist_ok=True)

    result = {}
    done = threading.Event()
    page = HTML.replace("__IMAGES__", json.dumps(
        [{"name": os.path.basename(p)} for p in paths], ensure_ascii=True))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence request logging
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
            elif self.path.startswith("/img/"):
                try:
                    i = int(self.path[5:])
                    if not 0 <= i < len(paths):
                        raise IndexError(i)
                    p = paths[i]
                    ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                    with open(p, "rb") as f:
                        self._send(200, ctype, f.read())
                except (ValueError, IndexError, OSError):
                    self._send(404, "text/plain", b"not found")
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self):
            if self.path != "/submit":
                self._send(404, "text/plain", b"not found")
                return
            try:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                data = json.loads(body.decode("utf-8"))
                images = []
                for img in data.get("images", []):
                    i = int(img["idx"])
                    stem = os.path.splitext(os.path.basename(paths[i]))[0]
                    out = []
                    for rg in img.get("regions", []):
                        dst = os.path.join(mask_dir, "%s-mask-%d.png" % (stem, int(rg["n"])))
                        out.append({"n": int(rg["n"]),
                                    "mask": save_mask(rg["png"], dst),
                                    "comment": rg.get("comment", "")})
                    images.append({"file": paths[i],
                                   "pins": img.get("pins", []),
                                   "regions": out})
            except (ValueError, KeyError, IndexError, TypeError,
                    binascii.Error, OSError) as e:
                # bad submission: report and keep waiting instead of hanging silently
                self._send(400, "application/json",
                           json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                return
            result.update({"action": data.get("action", "none"),
                           "reason": "user", "images": images})
            self._send(200, "application/json", b'{"ok":true}')
            done.set()

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d/" % srv.server_port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("review page: " + url, file=sys.stderr)
    print("mask dir:    " + mask_dir, file=sys.stderr)
    try:
        webbrowser.open(url)
    except Exception:
        pass  # URL already printed to stderr for manual open

    if not done.wait(a.timeout):
        result.update({"action": "none", "reason": "timeout", "images": []})
    srv.shutdown()
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
