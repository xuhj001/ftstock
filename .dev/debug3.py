import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).with_name("qt_profile_test4")
app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "TSLA-US")
w.login_prompted = True
w.want_watch = False
w.show()

JS = r"""
(async () => {
  const u = '/quote-api/quote-v2/get-stock-quote?stockId=201335';
  const a = await fetch(u, {credentials: 'omit'});
  const b = await fetch(u);
  const d = navigator.userAgentData;
  return JSON.stringify({
    omit: a.headers.get('content-type'), include: b.headers.get('content-type'),
    brands: d && d.brands, webdriver: navigator.webdriver, qt: typeof window.qt,
    plugins: navigator.plugins.length, langs: navigator.languages
  });
})()
"""


def run():
    w.page.runJavaScript("window.__dbg=null;(" + JS.strip() + ").then(v=>window.__dbg=v)")
    QTimer.singleShot(4000, lambda: w.page.runJavaScript("window.__dbg", 0, lambda v: (print("RES:", v, flush=True), app.quit())))


QTimer.singleShot(12000, run)
app.exec()
