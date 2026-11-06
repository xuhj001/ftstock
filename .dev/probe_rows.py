import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_rows.json"
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.resize(1440, 900)
w.show()

PROBE = r"""(function(){
var m=document.querySelector('section.watchlist-modal'); if(!m) return 'no modal';
var row=m.querySelector('.list-item'); var out={};
function desc(el){var cs=getComputedStyle(el);return el.tagName+'.'+[...el.classList].join('.')+' ['+[...el.attributes].map(a=>a.name).filter(n=>n.startsWith('data-v')).join(',')+'] oy='+cs.overflowY+' h='+el.clientHeight+' sh='+el.scrollHeight+' pos='+cs.position;}
var chain=[]; for(var e=row;e&&e!==document.body;e=e.parentElement) chain.push(desc(e)); out.chain=chain;
out.rowHTML=row.outerHTML.slice(0,1500);
out.rows=m.querySelectorAll('.list-item').length;
out.rowRect=JSON.stringify(row.getBoundingClientRect());
out.vnodeKey=row.__vue__?('vm '+row.__vue__.$options.name):'no vm';
out.listeners=typeof getEventListeners;
return JSON.stringify(out,null,1);})()"""

QTimer.singleShot(18000, lambda: w.watch_view.page().runJavaScript(PROBE, 0, lambda r: (print(r, flush=True), os._exit(0))))
QTimer.singleShot(30000, lambda: os._exit(1))
app.exec()
