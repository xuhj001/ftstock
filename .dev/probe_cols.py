import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).resolve().parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
w.switch_page("site")

JS = r"""JSON.stringify((function(){
  var head = document.querySelector('section.watchlist-modal .list-head') || document.querySelector('section.watchlist-modal .list-item');
  var row = document.querySelector('section.watchlist-modal .list-item');
  function cols(el){ return el ? [...el.querySelectorAll('.col')].map(function(c){ var s=getComputedStyle(c);
    return c.className.replace('col ','')+' w='+Math.round(c.getBoundingClientRect().width)+' css='+s.width+' flex='+s.flex+' minW='+s.minWidth+' pad='+s.paddingLeft+'/'+s.paddingRight; }) : null; }
  var content = document.querySelector('section.watchlist-modal .content');
  return {head: head && head.className, headCols: cols(head), rowCols: cols(row), rowPad: row && getComputedStyle(row).padding,
          contentPad: content && getComputedStyle(content).padding};
})())"""


def run():
    w.watch_box.set_inner_width(1000)
    w.splitter.setSizes([1000, 0, 440])
    QTimer.singleShot(1500, lambda: w.watch_view.page().runJavaScript(JS, 0, lambda r: print(r, flush=True)))


QTimer.singleShot(15000, run)
QTimer.singleShot(19000, lambda: os._exit(0))
app.exec()
