import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "shots_market"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
dv = w.detail_view
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.futunn.com/quote/us"

LINKS_JS = r"""JSON.stringify((function(){
var m={};document.querySelectorAll('a[href]').forEach(function(a){var u=new URL(a.href);var k=u.host+u.pathname.replace(/\/[^\/]+$/,'/*');m[k]=(m[k]||0)+1;});
return {path:location.pathname,title:document.title,links:m,scrollH:document.documentElement.scrollHeight,
 sw:document.documentElement.scrollWidth, vw:innerWidth};})())"""


def shot(name, scroll=0):
    dv.page().runJavaScript(f"window.scrollTo(0,{scroll})")
    QTimer.singleShot(800, lambda: w.grab().save(str(OUT / f"{name}.png")))


QTimer.singleShot(9000, lambda: (dv.setUrl(QUrl(URL)), print("loading", URL, flush=True)))
QTimer.singleShot(19000, lambda: dv.page().runJavaScript(LINKS_JS, 0, lambda r: print("market", r, flush=True)))
QTimer.singleShot(19500, lambda: shot("m1", 0))
QTimer.singleShot(21000, lambda: shot("m2", 600))
QTimer.singleShot(22500, lambda: shot("m3", 1300))
QTimer.singleShot(24500, lambda: os._exit(0))
app.exec()
