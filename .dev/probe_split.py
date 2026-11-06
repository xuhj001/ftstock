import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_split"
app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "TSLA-US")
w.show()

WATCH_JS = """JSON.stringify((function(){
var cs=[...document.querySelectorAll('section.watchlist-modal .list-head .col')].map(c=>c.className+':'+c.offsetWidth+':'+getComputedStyle(c).flex+':'+getComputedStyle(c).width);
var h=document.querySelector('section.watchlist-modal .list-head');
return {vw:innerWidth,cols:cs,head:h&&getComputedStyle(h).display,headW:h&&h.scrollWidth};})())"""
DETAIL_JS = """JSON.stringify((function(){
var d=document.documentElement;var out=[];
document.querySelectorAll('body *').forEach(function(e){var mw=getComputedStyle(e).minWidth;if(mw&&mw!=='0px'&&mw!=='auto'&&parseInt(mw)>500)out.push(e.tagName+'.'+e.className+':'+mw);});
return {vw:innerWidth,sw:d.scrollWidth,minw:out.slice(0,10)};})())"""


def probe():
    print("screen", app.primaryScreen().availableGeometry(), "win", w.size(), flush=True)
    w.watch_view.page().runJavaScript(WATCH_JS, 0, lambda r: print("watch", r, flush=True))
    w.detail_view.page().runJavaScript(DETAIL_JS, 0, lambda r: print("detail", r, flush=True))


QTimer.singleShot(14000, probe)
QTimer.singleShot(16000, lambda: os._exit(0))
app.exec()
