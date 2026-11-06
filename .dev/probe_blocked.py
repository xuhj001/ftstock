import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).resolve().parent
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"

HOOK = r"""
(function(){
  var oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(m, url){
    if (/quote-api/.test(url)) this.addEventListener('load', function(){
      var ct = this.getResponseHeader('content-type') || '';
      if (!/json/.test(ct)) console.log('__NONJSON__ ' + this.status + ' ' + ct + ' ' + url.slice(0, 90) + ' | ' + String(this.responseText).slice(0, 120).replace(/\s+/g, ' '));
    });
    return oo.apply(this, arguments);
  };
})();
"""
T0 = time.time()
_orig = futu_app.FutuPage.javaScriptConsoleMessage


def console(self, level, msg, line, src):
    if msg.startswith("__NONJSON__"):
        print(f"{time.time() - T0:5.1f} [{self.role}] {msg}", flush=True)
        return
    return _orig(self, level, msg, line, src)


futu_app.FutuPage.javaScriptConsoleMessage = console
app = QApplication(sys.argv)
profile = futu_app.create_profile(app)
profile.scripts().insert(futu_app.page_script("nonjson", HOOK))
w = futu_app.MainWindow(profile, "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
_msg = w.statusBar().showMessage
w.statusBar().showMessage = lambda m, t=0: (print(f"{time.time() - T0:5.1f} STATUS", m, flush=True), _msg(m, t))[1]
QTimer.singleShot(25000, lambda: os._exit(0))
app.exec()
