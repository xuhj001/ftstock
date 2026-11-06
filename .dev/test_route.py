import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtGui import QDesktopServices  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
QDesktopServices.openUrl = staticmethod(lambda url: print("SYSTEM BROWSER", url.toString(), flush=True) or True)
_cw = futu_app.FutuPage.createWindow
futu_app.FutuPage.createWindow = lambda self, t: (print("createWindow", self.role, flush=True), _cw(self, t))[1]
_ru = futu_app.MainWindow.route_url
futu_app.MainWindow.route_url = lambda self, u: (print("route_url", u.toString()[:70], flush=True), _ru(self, u))[1]
futu_app.MainWindow._start_watch = lambda self: None  # 只测右侧，少发请求

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
dv = w.detail_view
dv.setUrl(QUrl("https://www.futunn.com/quote/us"))

CLICK = """(function(){
  var a=document.querySelector('a.list-item[target="_blank"][href*="/stock/"]');
  if(!a) return 'no row';
  a.click(); return a.getAttribute('href').slice(0,30);
})()"""


def report(tag):
    print(tag, "detail url:", dv.url().toString()[:80], flush=True)


QTimer.singleShot(9000, lambda: report("before"))
QTimer.singleShot(9500, lambda: dv.page().runJavaScript(CLICK, 0, lambda r: print("clicked", r, flush=True)))
QTimer.singleShot(13000, lambda: report("after"))
QTimer.singleShot(13500, lambda: os._exit(0))
app.exec()
