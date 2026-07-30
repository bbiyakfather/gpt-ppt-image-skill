#!/usr/bin/env python3
"""One-shot local review server for the codex-image skill.

Usage:  python review_server.py IMAGE [IMAGE ...] [--timeout SECONDS]

Serves a pin-comment review page on 127.0.0.1:<random port>, opens the
default browser, waits for a single submission (or timeout), prints the
result JSON to stdout, then exits. Nothing keeps running afterwards.

Output JSON (stdout, single line):
  {"action": "edit"|"none", "reason": "user"|"timeout",
   "images": [{"file": "<abs path>", "pins": [
       {"n": 1, "x_pct": 12.3, "y_pct": 45.6, "comment": "..."}]}]}
  or, when an input file is missing (exit 1):
  {"action": "error", "reason": "file not found: <path>"}
"""
import argparse
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>이미지 리뷰 — 핀을 찍어 수정 지시</title>
<style>
 body{margin:0;font-family:'Segoe UI',sans-serif;background:#16181d;color:#e8e8ea}
 header{padding:12px 20px;background:#1f2229;display:flex;gap:12px;align-items:center;position:sticky;top:0;z-index:10}
 header h1{font-size:15px;margin:0;flex:1;font-weight:600}
 button{border:0;border-radius:8px;padding:9px 16px;font-size:13px;cursor:pointer;font-weight:600}
 #btn-edit{background:#7c5cff;color:#fff} #btn-none{background:#3a3f4b;color:#e8e8ea}
 #btn-back{background:#3a3f4b;color:#e8e8ea;display:none}
 main{display:flex;gap:16px;padding:16px 20px}
 #stage{flex:1;min-width:0}
 #gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
 .thumb{background:#1f2229;border-radius:10px;padding:10px;cursor:pointer;border:2px solid transparent}
 .thumb:hover{border-color:#7c5cff}
 .thumb img{width:100%;border-radius:6px;display:block}
 .thumb .cap{font-size:12px;margin-top:8px;color:#aab;display:flex;justify-content:space-between}
 .badge{background:#7c5cff;border-radius:10px;padding:0 8px;color:#fff}
 #imgwrap{position:relative;display:inline-block;max-width:100%}
 #imgwrap img{max-width:100%;display:block;border-radius:8px;cursor:crosshair}
 .pin{position:absolute;width:24px;height:24px;margin:-24px 0 0 -12px;background:#7c5cff;color:#fff;
      border-radius:50% 50% 50% 0;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;
      font-size:12px;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.5)}
 .pin span{transform:rotate(45deg)}
 #side{width:300px;flex-shrink:0}
 .pinrow{background:#1f2229;border-radius:10px;padding:10px;margin-bottom:10px}
 .pinrow .head{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px;color:#aab}
 .pinrow .del{color:#f66;cursor:pointer;background:none;padding:0;font-size:12px}
 textarea{width:100%;box-sizing:border-box;background:#16181d;color:#e8e8ea;border:1px solid #3a3f4b;
          border-radius:6px;padding:6px;font-size:13px;resize:vertical;min-height:48px}
 #hint{color:#889;font-size:13px;margin-bottom:10px}
 #done{padding:60px;text-align:center;font-size:16px}
</style></head><body>
<header>
 <button id="btn-back" onclick="showGallery()">← 갤러리</button>
 <h1 id="title">이미지 리뷰</h1>
 <button id="btn-edit">수정 요청 보내기</button>
 <button id="btn-none">수정 없음 (확정)</button>
</header>
<main>
 <div id="stage"></div>
 <div id="side"></div>
</main>
<script>
const IMAGES = __IMAGES__;            // [{name}]
const pins = IMAGES.map(()=>[]);      // per image: [{x,y,comment}]
let cur = 0;
const stage = document.getElementById('stage'), side = document.getElementById('side');

function showGallery(){
  document.getElementById('btn-back').style.display='none';
  document.getElementById('title').textContent = '갤러리 — 수정할 이미지를 클릭하세요 (' + IMAGES.length + '장)';
  side.innerHTML='';
  stage.innerHTML = '<div id="gallery">' + IMAGES.map((im,i)=>
    '<div class="thumb" onclick="showImage('+i+')"><img src="/img/'+i+'"><div class="cap"><span>'+im.name+
    '</span>' + (pins[i].length?'<span class="badge">핀 '+pins[i].length+'</span>':'') + '</div></div>').join('') + '</div>';
}
function showImage(i){
  cur = i;
  if(IMAGES.length>1) document.getElementById('btn-back').style.display='inline-block';
  document.getElementById('title').textContent = IMAGES[i].name + ' — 고칠 곳을 클릭해 핀을 찍으세요';
  stage.innerHTML = '<div id="hint">이미지 위를 클릭하면 핀이 추가됩니다. 핀마다 수정 내용을 댓글로 남기세요.</div>' +
                    '<div id="imgwrap"><img id="theimg" src="/img/'+i+'"></div>';
  document.getElementById('theimg').addEventListener('click', ev=>{
    const r = ev.target.getBoundingClientRect();
    pins[cur].push({x:(ev.clientX-r.left)/r.width*100, y:(ev.clientY-r.top)/r.height*100, comment:''});
    render();
  });
  render();
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
  side.innerHTML = pins[cur].map((p,n)=>
    '<div class="pinrow"><div class="head"><b>📍 핀 '+(n+1)+'</b> <span>'+p.x.toFixed(1)+'%, '+p.y.toFixed(1)+
    '%</span> <button class="del" onclick="delPin('+n+')">삭제</button></div>'+
    '<textarea placeholder="수정 내용 (예: 이 로고 더 크게)" oninput="pins['+cur+']['+n+'].comment=this.value">'+
    (p.comment||'')+'</textarea></div>').join('') || '<div id="hint">아직 핀이 없습니다.</div>';
}
function delPin(n){ pins[cur].splice(n,1); render(); }

function submit(action){
  const imgs = IMAGES.map((im,i)=>({idx:i, pins:pins[i].map((p,n)=>(
    {n:n+1, x_pct:+p.x.toFixed(1), y_pct:+p.y.toFixed(1), comment:p.comment.trim()}))}))
    .filter(x=>x.pins.length>0);
  if(action==='edit' && imgs.length===0){
    alert('핀이 하나도 없습니다. 고칠 곳을 클릭해 핀을 찍거나, "수정 없음 (확정)"을 누르세요.');
    return;
  }
  if(action==='edit'){
    const empty = imgs.flatMap(x=>x.pins.filter(p=>!p.comment).map(p=>'핀 '+p.n));
    if(empty.length){
      alert('댓글이 비어 있는 핀이 있습니다: '+empty.join(', ')+'\\n수정 내용을 적거나 핀을 삭제하세요.');
      return;
    }
  }
  if(action==='none' && imgs.length>0 &&
     !confirm('찍어둔 핀 '+imgs.reduce((s,x)=>s+x.pins.length,0)+'개가 버려집니다. 정말 수정 없이 확정할까요?')){
    return;
  }
  fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:action, images:imgs})})
    .then(()=>{document.body.innerHTML='<div id="done">✅ 전송 완료 — 이 창을 닫고 Claude Code로 돌아가세요.</div>';});
}
document.getElementById('btn-edit').onclick = ()=>submit('edit');
document.getElementById('btn-none').onclick = ()=>submit('none');
IMAGES.length>1 ? showGallery() : showImage(0);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--timeout", type=int, default=570, help="seconds to wait before auto-confirm")
    a = ap.parse_args()

    paths = [os.path.abspath(p) for p in a.images]
    for p in paths:
        if not os.path.isfile(p):
            print(json.dumps({"action": "error", "reason": "file not found: " + p}))
            sys.exit(1)

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
                    images.append({"file": paths[int(img["idx"])],
                                   "pins": img.get("pins", [])})
            except (ValueError, KeyError, IndexError, TypeError) as e:
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
