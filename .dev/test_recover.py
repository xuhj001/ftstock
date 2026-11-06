"""故障自动恢复：页面加载失败自动重试、页面进程被杀自动重载、断网时行情快速放弃、正常关闭无报错"""
import json
import os
import shutil
import signal
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
import local_watchlist  # noqa: E402
from PyQt6.QtCore import Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
TMP = HERE / "local_recover.json"
shutil.copy(HERE.parent / "local_watchlist.json", TMP)
futu_app.PROFILE_DIR = HERE / "qt_profile_minute"
(futu_app.PROFILE_DIR / "window.ini").unlink(missing_ok=True)
futu_app.LocalWatchlist = lambda: local_watchlist.LocalWatchlist(TMP)
futu_app.log_uncaught_exceptions()
errors = []
real_hook = sys.excepthook
sys.excepthook = lambda *a: (errors.append(a[1]), real_hook(*a))

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
w.show()
w.act_auto.setChecked(False)
fails = []
messages = []
w.statusBar().messageChanged.connect(lambda m: m and messages.append(m))


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
    if not ok:
        fails.append(name)


def step1():
    w._show_detail()
    w.detail_view.load(QUrl("https://127.0.0.1:9/"))  # 连接被拒绝，立即失败
    QTimer.singleShot(9000, step2)


def step2():
    url = w.detail_view.url()
    check("failed load: retry message", any("自动重试" in m for m in messages), [m for m in messages if "重试" in m][:2])
    check("failed load: recovered to futunn", futu_app.is_futu_page(url), url.toString())
    v = w.watch_view
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    v.load = lambda url: (print("   retry load", url.toString(), "failures", w.load_failures, flush=True),
                          QWebEngineView.load(v, url))
    v.loadFinished.connect(lambda ok: print("   watch loadFinished", ok, "failures", w.load_failures, flush=True))
    v.loadStarted.connect(lambda: print("   watch loadStarted", flush=True))
    pid = w.watch_view.page().renderProcessPid()
    print("   killing renderer pid", pid, flush=True)
    messages.clear()
    os.kill(pid, signal.SIGTERM)
    QTimer.singleShot(12000, step3)


def step3(tries=0):
    if tries == 0:
        check("renderer killed: retry message", any("进程意外退出" in m for m in messages), messages[:2])

    def got(ok):
        if ok or tries >= 10:
            check("renderer killed: list back", bool(ok), f"after ~{12 + tries * 2}s")
            step4()
        else:
            w.watch_view.page().runJavaScript(
                "JSON.stringify({fa: !!window.__fa, role: window.__faRole, st: typeof window.__faState,"
                " title: document.title, modal: !!document.querySelector('section.watchlist-modal'),"
                " tb: !!document.querySelector('section.tool-bar'), body: (document.body||{}).innerText?.slice(0,80)})",
                0, lambda r: print("   waiting", r, flush=True))
            QTimer.singleShot(2000, lambda: step3(tries + 1))

    w.watch_view.page().runJavaScript("!!document.querySelector('section.watchlist-modal .list-item')", 0, got)


calls = []


def step4():
    import threading

    def boom(self, *a):
        calls.append(threading.get_ident())
        raise urllib.error.URLError("模拟断网")

    futu_app.FutuClient.stock_quote = boom
    messages.clear()
    w.local_busy = False
    w._refresh_local_quotes()
    QTimer.singleShot(1500, step5)


def step5():
    per_run = {t: calls.count(t) for t in calls}
    check("network down: each run gave up after first stock", calls and max(per_run.values()) == 1,
          f"calls per run={list(per_run.values())}，共 {len(w.local.entries)} 只")
    check("network down: message", any("网络连接失败" in m for m in messages), messages[:1])
    w.close()
    QTimer.singleShot(1500, step6)


def step6():
    check("close: geometry saved", (futu_app.PROFILE_DIR / "window.ini").exists())
    check("no uncaught exceptions", not errors, errors)
    print("ALL PASS" if not fails else f"FAILED: {fails}", flush=True)
    os._exit(0)


QTimer.singleShot(18000, step1)
QTimer.singleShot(90000, lambda: (print("TIMEOUT", flush=True), os._exit(1)))
app.exec()
