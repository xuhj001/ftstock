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
OUT = HERE / "shots_split"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
futu_app.PROFILE_DIR = HERE / "qt_profile_split"

_orig_console = futu_app.FutuPage.javaScriptConsoleMessage


def _console(self, level, message, line, source):
    if level == futu_app.QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel or "__FA" in message:
        print("console", self.role, message[:200], flush=True)
    _orig_console(self, level, message, line, source)


futu_app.FutuPage.javaScriptConsoleMessage = _console

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "TSLA-US")
w.show()

INFO_JS = ("JSON.stringify({path:location.pathname,title:document.title,"
           "modal:!!document.querySelector('section.watchlist-modal'),"
           "head:(document.querySelector('section.watchlist-modal .header')||{}).innerText,"
           "active:(document.querySelector('section.watchlist-modal .list-item.active .name')||{}).innerText})")


def shot(name):
    w.grab().save(str(OUT / f"{name}.png"))
    for role, view in w.views.items():
        view.page().runJavaScript(INFO_JS, 0, lambda raw, r=role: print(name, r, raw, flush=True))


def click_row(index):
    js = ("(function(){var e=document.querySelectorAll('section.watchlist-modal .list-item .col.name')[%d];"
          "if(!e)return null;var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2,e.innerText]);})()") % index

    def do(raw):
        if not raw:
            print("ROW NOT FOUND", index, flush=True)
            return
        x, y, text = json.loads(raw)
        QTest.mouseClick(w.watch_view.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked row", index, text.replace("\n", " "), flush=True)

    w.watch_view.page().runJavaScript(js, 0, do)


SPY_JS = """
['mousedown','mouseup','click'].forEach(function(t){document.addEventListener(t,function(e){
  var it=e.target.closest&&e.target.closest('.list-item');
  console.error('SPY '+t+' trusted='+e.isTrusted+' xy='+e.clientX+','+e.clientY+' row='+(it?it.innerText.split('\\n')[0]:'-'));
},true);});
"""

steps = [
    (14000, lambda: w.watch_view.page().runJavaScript(SPY_JS)),
    (15000, lambda: shot("1_start")),
    (16000, lambda: click_row(2)),
    (23000, lambda: shot("2_row2")),
    (24000, lambda: click_row(4)),
    (31000, lambda: shot("3_row4")),
    (32000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
