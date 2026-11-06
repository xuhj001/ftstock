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

JS = r"""JSON.stringify((function(){
  var out = [];
  for (var s of document.styleSheets) {
    var rules; try { rules = s.cssRules; } catch (e) { continue; }
    (function walk(list){ for (var r of list) {
      if (r.cssRules && !r.selectorText) { walk(r.cssRules); continue; }
      if (r.selectorText && /data-v-918a5560/.test(r.selectorText) && /content|modal|list/.test(r.selectorText)
          && (r.style.width || r.style.maxWidth || r.style.minWidth))
        out.push((r.parentRule && r.parentRule.conditionText ? '@' + r.parentRule.conditionText + ' ' : '') + r.selectorText + ' { width:' + r.style.width + '; min:' + r.style.minWidth + '; max:' + r.style.maxWidth + ' }');
    } })(rules);
  }
  return out;
})())"""
QTimer.singleShot(14000, lambda: w.watch_view.page().runJavaScript(JS, 0, lambda r: print(r, flush=True)))
QTimer.singleShot(16000, lambda: os._exit(0))
app.exec()
