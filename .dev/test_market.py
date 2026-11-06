import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QDesktopServices  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "shots_market"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
QDesktopServices.openUrl = staticmethod(lambda url: print("SYSTEM BROWSER", url.toString(), flush=True) or True)

_cw = futu_app.FutuPage.createWindow
futu_app.FutuPage.createWindow = lambda self, t: (print("createWindow", self.role, t, flush=True), _cw(self, t))[1]
_op = futu_app.MainWindow.open_path
futu_app.MainWindow.open_path = lambda self, p, item=None: (print("open_path", p, bool(item), flush=True),
                                                             _op(self, p, item))[1]
_an = futu_app.FutuPage.acceptNavigationRequest
futu_app.FutuPage.acceptNavigationRequest = lambda self, u, t, m: (
    print("nav", self.role, u.toString()[:90], t, m, flush=True) if m else None, _an(self, u, t, m))[1]

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
dv = w.detail_view


def info(name):
    w.grab().save(str(OUT / f"{name}.png"))
    dv.page().runJavaScript("JSON.stringify([location.pathname, document.title])", 0,
                            lambda r: print(name, r, "| code", w.code, flush=True))


def click(expr, label):
    js = ("(function(){var e=%s;if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2,e.innerText||e.href]);})()") % expr

    def do(raw):
        if not raw:
            print("NOT FOUND", label, flush=True)
            return
        x, y, text = json.loads(raw)
        QTest.mouseClick(dv.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked", label, repr(text[:40]), flush=True)

    dv.page().runJavaScript(js, 0, do)


ROW = ("[...document.querySelectorAll('a[href*=\"/stock/\"]')].filter(a=>a.offsetWidth>0"
       "&&a.getBoundingClientRect().top>0)[3]")

from PyQt6.QtCore import QUrl  # noqa: E402

steps = [
    (1000, lambda: dv.setUrl(QUrl("https://www.futunn.com/quote/us"))),
    (12000, lambda: info("2_market")),
    (12500, lambda: os._exit(0) if "--quick" not in sys.argv else None),
] if "--route" in sys.argv else [
    (11000, lambda: info("1_detail")),
    (12000, lambda: click("document.querySelector('.crumb a')", "crumb")),
    (22000, lambda: info("2_market")),
    (22500, lambda: dv.page().runJavaScript(
        "(function(){var a=" + ROW + ";return a.outerHTML.slice(0,300)+' | parent: '+a.parentElement.outerHTML.slice(0,200)})()",
        0, lambda r: print("ROWHTML", r, flush=True))),
    (23000, lambda: click(ROW, "market row")),
    (31000, lambda: info("3_stock")),
    (32000, lambda: dv.back()),
    (38000, lambda: info("4_back")),
    (39000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
