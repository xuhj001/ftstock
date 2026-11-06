import os
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
futu_app.MainWindow._start_watch = lambda self: None
futu_app.FutuPage.javaScriptConsoleMessage = lambda self, lvl, msg, line, src: print("console", msg[:400], flush=True) \
    if msg.startswith("SRCH") else None

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
dv = w.detail_view
dv.setUrl(QUrl("https://www.futunn.com/quote/us"))

TYPE = r"""
(function(){
  var css = document.getElementById('fa-style'); if (css) css.remove();
  var inputs = [...document.querySelectorAll('#header input, .hk-cs-search-container input, input')];
  console.error('SRCH inputs ' + inputs.map(i => (i.className||'') + '|' + (i.placeholder||'')).join(' ;; ').slice(0, 300));
  var inp = inputs.find(i => /search|搜索|代码/i.test((i.className||'') + (i.placeholder||'')));
  if (!inp) { var btn = document.querySelector('.hk-cs-js-header-search-icon-wrapper, .search'); if (btn) btn.click(); return 'clicked icon'; }
  inp.focus(); inp.value = 'TSLA';
  ['input','keyup','change'].forEach(t => inp.dispatchEvent(new Event(t, {bubbles:true})));
  return 'typed';
})()
"""
TYPE2 = r"""
(function(){
  var inp = [...document.querySelectorAll('input')].find(i => /search|搜索|代码/i.test((i.className||'') + (i.placeholder||'')));
  if (!inp) return 'no input';
  inp.focus(); inp.value = 'TSLA';
  ['input','keyup','change'].forEach(t => inp.dispatchEvent(new Event(t, {bubbles:true})));
  return 'typed ' + inp.className;
})()
"""
DUMP = r"""
(function(){
  performance.getEntriesByType('resource').map(e => e.name).filter(u => !/\.(js|css|png|svg|jpg|woff2?|gif|webp)(\?|$)/.test(u) && /search|suggest|query|keyword/i.test(u))
    .forEach(u => console.error('SRCH url ' + u));
  return 1;
})()
"""

QTimer.singleShot(10000, lambda: dv.page().runJavaScript(TYPE, 0, lambda r: print("step1", r, flush=True)))
QTimer.singleShot(14000, lambda: dv.page().runJavaScript(TYPE2, 0, lambda r: print("step2", r, flush=True)))
QTimer.singleShot(19000, lambda: dv.page().runJavaScript(DUMP))
QTimer.singleShot(20000, lambda: os._exit(0))
app.exec()
