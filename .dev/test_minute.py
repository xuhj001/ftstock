import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "shots_minute"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
shutil.rmtree(futu_app.PROFILE_DIR, ignore_errors=True)
CODE = "TSLA-US"

_orig_console = futu_app.FutuPage.javaScriptConsoleMessage


def _console(self, level, message, line, source):
    if self.role == "detail" and (
            level == futu_app.QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel or "NET" in message):
        print("console", message[:300], flush=True)
    _orig_console(self, level, message, line, source)


futu_app.FutuPage.javaScriptConsoleMessage = _console

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), CODE)
w.show()
page = lambda: w.detail_view.page()  # noqa: E731

SPY_JS = r"""
(function(){
  var open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m, u){ this.__u = u; return open.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(){
    var x = this;
    x.addEventListener('loadend', function(){
      if (!/quote|kline|minute|chart/i.test(x.__u)) return;
      var extra = '';
      try { var d = JSON.parse(x.responseText).data; if (d && d.list) extra = ' LIST=' + d.list.length + ' first=' + JSON.stringify(d.list[0]) + ' last=' + JSON.stringify(d.list[d.list.length-1]); } catch (e) {}
      console.info('NET ' + x.status + ' ' + x.__u.slice(0, 140) + extra + ' => ' + String(x.responseText).slice(0, 120));
    });
    return send.apply(this, arguments);
  };
})();
"""


def shot(name):
    w.grab().save(str(OUT / f"{name}.png"))
    print("shot", name, flush=True)


def click(expr, label):
    js = ("(function(){var e=%s;if(!e)return null;e.scrollIntoView({block:'center'});var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2]);})()") % expr

    def do(raw):
        if not raw:
            print("NOT FOUND", label, flush=True)
            return
        x, y = json.loads(raw)
        QTest.mouseClick(w.detail_view.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked", label, int(x), int(y), flush=True)

    page().runJavaScript(js, 0, do)


def by_text(text):
    return ("[...document.querySelectorAll('section.kline-type *')].filter(e=>e.offsetWidth>0&&e.children.length==0"
            "&&e.innerText.trim()==%s).pop()") % json.dumps(text)


def click_left_row(text):
    js = ("(function(){var e=[...document.querySelectorAll('section.watchlist-modal .list-item .col.name')]"
          ".find(e=>e.innerText.split('\\n')[0].trim()==%s);if(!e)return null;var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2]);})()") % json.dumps(text)

    def do(raw):
        print("left state", w.states["watch"].get("path"), "waf retries", w.waf_retries, flush=True)
        if not raw:
            print("LEFT ROW NOT FOUND", text, flush=True)
            return
        x, y = json.loads(raw)
        QTest.mouseClick(w.watch_view.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked left", text, flush=True)

    w.watch_view.page().runJavaScript(js, 0, do)


steps = [
    (12000, lambda: page().runJavaScript(SPY_JS)),
    (22000, lambda: (shot("0_cold"), click_left_row("AAPL"))),
    (27000, lambda: click("document.querySelector('section.kline-type .minute-select')", "select")),
    (29000, lambda: click(by_text("盘后报价"), "after")),
    (35000, lambda: shot("2_after")),
    (36000, lambda: click("document.querySelector('section.kline-type .minute-select')", "select")),
    (38000, lambda: click(by_text("全部分时"), "all")),
    (44000, lambda: shot("3_all")),
    (45000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
