"""Measure left/right edges of close% vs pre-market% in the change column."""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).parent / "qt_profile_dump"
OUT = Path(__file__).with_name("dump_change_align.json")

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
# Match typical left-pane width (~880) and a narrow pane that hits the 620 media query
w.resize(1000, 900)
w.show()

JS = r"""
(function () {
  function box(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return {left: Math.round(r.left*10)/10, right: Math.round(r.right*10)/10,
            width: Math.round(r.width*10)/10, text: (el.textContent||'').trim().replace(/\s+/g,' ')};
  }
  var rows = [];
  document.querySelectorAll('section.watchlist-modal .list-item').forEach(function (row, i) {
    if (i > 12) return;
    var change = row.querySelector('.col.change');
    if (!change) return;
    var main = change.querySelector(':scope > span:not(.disc-change)');
    var disc = change.querySelector('.disc-change');
    var discPct = disc && disc.querySelector('span.ellipsis');
    var badge = disc && disc.querySelector('.disc-status');
    var name = ((row.querySelector('.col.name')||{}).textContent||'').trim().split(/\s+/)[0];
    rows.push({
      name: name,
      col: box(change),
      closePct: box(main),
      discPct: box(discPct),
      badge: box(badge),
      disc: box(disc),
      deltaRight: (main && discPct) ? Math.round((main.getBoundingClientRect().right - discPct.getBoundingClientRect().right)*10)/10 : null
    });
  });
  return {
    vw: window.innerWidth,
    changeWidthRule: getComputedStyle(document.querySelector('.col.change')||document.body).width,
    rows: rows.filter(function (r) { return r.discPct; })
  };
})()
"""


def dump():
    def got(res):
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2), flush=True)
        os._exit(0)

    w.watch_view.page().runJavaScript(JS, got)


n = [0]


def tick():
    n[0] += 1
    if n[0] >= 14:
        dump()
        return
    QTimer.singleShot(1000, tick)


QTimer.singleShot(2000, tick)
app.exec()
