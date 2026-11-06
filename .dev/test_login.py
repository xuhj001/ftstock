import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QPoint, Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "shots_login"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
futu_app.PROFILE_DIR = HERE / "qt_profile_login"
shutil.rmtree(futu_app.PROFILE_DIR, ignore_errors=True)

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "TSLA-US")
w.show()


def shot(name):
    w.grab().save(str(OUT / f"{name}.png"))
    print(name, "|", w.view.url().toString()[:110], "|", {k: w.state.get(k) for k in ("watch", "isLogin")}, flush=True)


def click(js_selector_expr, label):
    js = ("(function(){var e=%s;if(!e)return null;var r=e.getBoundingClientRect();"
          "return JSON.stringify([r.left+r.width/2,r.top+r.height/2]);})()") % js_selector_expr

    def do(raw):
        if not raw:
            print("NOT FOUND:", label, flush=True)
            return
        x, y = json.loads(raw)
        QTest.mouseClick(w.view.focusProxy(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(x), int(y)))
        print("clicked", label, int(x), int(y), flush=True)

    w.page.runJavaScript(js, 0, do)


def tab(text):
    return ("[...document.querySelectorAll('a.switch-btn')].find(a=>a.offsetWidth>0&&a.innerText.trim()==%s)"
            % json.dumps(text))


def popups():
    wins = [c for c in w.findChildren(futu_app.PopupWindow)]
    print("popups:", [p.view.url().toString()[:100] for p in wins], flush=True)


steps = [
    (14000, lambda: shot("1_start")),
    (15000, lambda: click("document.querySelector('section.watchlist-modal .list-item .col.watchlist')", "heart")),
    (24000, lambda: shot("2_login")),
    (25000, lambda: click(tab("手机"), "phone tab")),
    (27000, lambda: shot("3_phone")),
    (28000, lambda: click(tab("邮箱/牛牛号"), "email tab")),
    (30000, lambda: shot("4_email")),
    (31000, lambda: click("[...document.querySelectorAll('a.wechat')].find(a=>a.offsetWidth>0)", "wechat")),
    (39000, lambda: (shot("5_wechat"), popups())),
    (40000, lambda: os._exit(0)),
]
for t, fn in steps:
    QTimer.singleShot(t, fn)
app.exec()
