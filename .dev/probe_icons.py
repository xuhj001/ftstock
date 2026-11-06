import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer, QUrl  # noqa: E402
from PyQt6.QtWebEngineCore import QWebEnginePage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).parent / "qt_profile_minute"
app = QApplication(sys.argv)
page = QWebEnginePage(futu_app.create_profile(app))
JS = """JSON.stringify([...document.querySelectorAll('link[rel*=icon], meta[property="og:image"], img[src*=logo], [class*=logo] img')]
  .map(e => (e.tagName + ' ' + (e.rel || e.getAttribute('property') || e.className) + ' ' + (e.sizes || '') + ' ' + (e.href || e.content || e.src))))"""
page.loadFinished.connect(lambda ok: QTimer.singleShot(3000, lambda: page.runJavaScript(
    JS, 0, lambda r: (print(r, flush=True), os._exit(0)))))
page.load(QUrl("https://www.futunn.com/quote/us"))
QTimer.singleShot(30000, lambda: os._exit(1))
app.exec()
