import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"

HOOK = r"""
(function(){
  if (window.__netHook) return; window.__netHook = 1;
  function log(kind, url){ try{ var u=new URL(url, location.href); console.log('__NET__ '+kind+' '+u.host+u.pathname+' '+(u.search||'').slice(0,160)); }catch(e){ console.log('__NET__ '+kind+' '+url); } }
  var oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(m, url){ log('xhr', url); return oo.apply(this, arguments); };
  var of = window.fetch;
  if (of) window.fetch = function(i){ log('fetch', typeof i==='string'? i : (i&&i.url)); return of.apply(this, arguments); };
  var OW = window.WebSocket;
  if (OW) {
    window.WebSocket = function(url, p){
      log('ws-open', url);
      var ws = p===undefined ? new OW(url) : new OW(url, p);
      var n=0; ws.addEventListener('message', function(ev){ n++; if(n<=3||n%20==0) console.log('__NET__ ws-msg #'+n+' '+url+' len='+(ev.data&&ev.data.length||ev.data&&ev.data.byteLength||0)); });
      ws.addEventListener('close', function(ev){ console.log('__NET__ ws-close '+url+' code='+ev.code); });
      return ws;
    };
    window.WebSocket.prototype = OW.prototype;
    ['CONNECTING','OPEN','CLOSING','CLOSED'].forEach(function(k){ window.WebSocket[k]=OW[k]; });
  }
  var OE = window.EventSource;
  if (OE) window.EventSource = function(url, o){ log('sse', url); return new OE(url, o); };
  var osi = window.setInterval;
  window.setInterval = function(fn, ms){ if (ms>=1000) console.log('__NET__ interval '+ms+' '+String(fn).slice(0,120).replace(/\s+/g,' ')); return osi.apply(this, arguments); };
})();
"""

T0 = time.time()
_orig = futu_app.FutuPage.javaScriptConsoleMessage


def console(self, level, msg, line, src):
    if msg.startswith("__NET__"):
        print(f"{time.time() - T0:6.1f} [{self.role}] {msg[8:]}", flush=True)
        return
    return _orig(self, level, msg, line, src)


futu_app.FutuPage.javaScriptConsoleMessage = console

app = QApplication(sys.argv)
profile = futu_app.create_profile(app)
profile.scripts().insert(futu_app.page_script("net-hook", HOOK))
w = futu_app.MainWindow(profile, "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
NOISE = ("dedog-server", "clarity.ms", "interval", "ft-report", "template-config", "heartbeat", "tourist_sig")
_print_console = console


def console2(self, level, msg, line, src):
    if msg.startswith("__NET__") and any(n in msg for n in NOISE):
        return
    return _print_console(self, level, msg, line, src)


futu_app.FutuPage.javaScriptConsoleMessage = console2

PRICE_DETAIL = """JSON.stringify({p:(document.querySelector('.stock-price, .price-current, .quote-price, [class*=price]')||{}).innerText,
 cls:(document.querySelector('.stock-price, .price-current, .quote-price, [class*=price]')||{}).className})"""
PRICE_LEFT = """JSON.stringify([...document.querySelectorAll('section.watchlist-modal .list-item')].slice(0,3).map(r=>r.innerText.replace(/\\n/g,' ')))"""
PRICE_MARKET = """JSON.stringify([...document.querySelectorAll('a[target=_blank]')].filter(a=>/\\/stock\\//.test(a.href)).slice(0,3).map(a=>a.innerText.replace(/\\n/g,' ').slice(0,80)))"""


def sample(tag):
    w.detail_view.page().runJavaScript(PRICE_MARKET if "market" in tag else PRICE_DETAIL, 0,
                                       lambda r: print(f"{time.time() - T0:6.1f} SAMPLE {tag} right: {r}", flush=True))
    w.watch_view.page().runJavaScript(PRICE_LEFT, 0,
                                      lambda r: print(f"{time.time() - T0:6.1f} SAMPLE {tag} left: {r}", flush=True))


for t in range(15, 45, 6):
    QTimer.singleShot(t * 1000, lambda t=t: sample(f"detail{t}"))
QTimer.singleShot(45000, lambda: (print("==== load market page ====", flush=True),
                                  w.detail_view.setUrl(QUrl("https://www.futunn.com/quote/us"))))
for t in range(57, 75, 6):
    QTimer.singleShot(t * 1000, lambda t=t: sample(f"market{t}"))
QTimer.singleShot(75000, lambda: os._exit(0))
app.exec()
