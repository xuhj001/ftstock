import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).with_name("qt_profile_test2")

app = QApplication(sys.argv)
prof = futu_app.create_profile(app)
from PyQt6.QtWebEngineCore import QWebEngineProfile
prof.setHttpUserAgent(QWebEngineProfile.defaultProfile().httpUserAgent())
prof.cookieStore().cookieAdded.connect(lambda c: print('CK', repr(c.domain()), bytes(c.name()).decode(), flush=True))
w = futu_app.MainWindow(prof, 'TSLA-US')
w.login_prompted = True
w.want_watch = False
w.show()

JS = r"""
(async () => {
  const enc = new TextEncoder();
  const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
  async function token(p) {
    const k = await crypto.subtle.importKey('raw', enc.encode('quote_web'), {name: 'HMAC', hash: 'SHA-512'}, false, ['sign']);
    const h = hex(await crypto.subtle.sign('HMAC', k, enc.encode(p))).slice(0, 10);
    return hex(await crypto.subtle.digest('SHA-256', enc.encode(h))).slice(0, 10);
  }
  const csrf = decodeURIComponent((document.cookie.match(/csrfToken=([^;]*)/) || [])[1] || '');
  const p = {page: '0', page_size: '20', t: String(Date.now())};
  const r = await fetch('/quote-api/quote-v2/get-watch-list?' + new URLSearchParams(p),
    {headers: {'futu-x-csrf-token': csrf, 'quote-token': await token(JSON.stringify(p))}});
  const q = await fetch('/quote-api/quote-v2/get-stock-quote?stockId=201335&marketType=2&marketCode=11&lotSize=1&spreadCode=45&underlyingStockId=0&instrumentType=3&subInstrumentType=3002');
  return JSON.stringify({
    status: r.status, body: (await r.text()).slice(0, 300),
    q: q.status + ' ' + (await q.text()).slice(0, 120),
    cookie: document.cookie.split(';').map(s => s.split('=')[0].trim()),
    ua: navigator.userAgent,
    h1: (document.querySelector('h1') || {}).innerText
  });
})()
"""


def run():
    w.page.runJavaScript("window.__dbg=null;(" + JS.strip() + ").then(v=>window.__dbg=v)")
    QTimer.singleShot(5000, lambda: w.page.runJavaScript("window.__dbg", 0, done))


def done(v):
    print("PAGE:", v, flush=True)
    print("STORE:", sorted(w.cookies), flush=True)
    print("PROFILE UA:", w.profile.httpUserAgent(), flush=True)
    app.quit()


QTimer.singleShot(12000, run)
app.exec()

