"""截图涨跌幅列，检查所有行的涨跌幅右边缘一致、盘前/盘后标签在右侧可见且不压住涨跌额"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

futu_app.PROFILE_DIR = Path(__file__).parent / "qt_profile_dump"
HERE = Path(__file__).parent

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.resize(1100, 1600)
w.show()

JS = r"""
(function () {
  function box(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return {l: +r.left.toFixed(1), r: +r.right.toFixed(1), t: r.top, b: r.bottom,
            text: (el.textContent || '').trim().replace(/\s+/g, ' ')};
  }
  var rows = [];
  document.querySelectorAll('section.watchlist-modal .list-item').forEach(function (row) {
    var change = row.querySelector('.col.change');
    if (!change) return;
    var main = change.querySelector(':scope > span:not(.disc-change)');
    var disc = change.querySelector('.disc-change > span.ellipsis');
    var badge = change.querySelector('.disc-status');
    var value = row.querySelector('.col.change-value');
    var heart = row.querySelector('.col.watchlist .icon');
    var visible = null;
    var list = row.closest('.list') || document.documentElement;
    var lr = list.getBoundingClientRect();
    var b0 = badge && badge.getBoundingClientRect();
    if (badge && b0.top >= Math.max(lr.top, 0) && b0.bottom <= Math.min(lr.bottom, innerHeight)) {
      var b = b0;
      var hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
      visible = !!(hit && badge.contains(hit));
    }
    var vb = value && getComputedStyle(value).display !== 'none' ? box(value.firstChild && value.firstChild.nodeType === 3 ? value : value) : null;
    var valueText = null;
    if (value && getComputedStyle(value).display !== 'none') {
      var range = document.createRange(); range.selectNodeContents(value);
      var rr = range.getBoundingClientRect(); valueText = {l: +rr.left.toFixed(1), r: +rr.right.toFixed(1)};
    }
    rows.push({
      name: ((row.querySelector('.col.name') || {}).textContent || '').trim().split(/\s+/)[0],
      close: box(main), disc: box(disc), badge: box(badge), badgeVisible: visible,
      valueText: valueText, heart: box(heart)
    });
  });
  return {vw: innerWidth, rows: rows};
})()
"""


def check(tag, info):
    rows = [r for r in info["rows"] if r["close"]]
    edges = sorted({r["close"]["r"] for r in rows} | {r["disc"]["r"] for r in rows if r["disc"]})
    ok = len(edges) == 1 or (edges and edges[-1] - edges[0] <= 1)
    print(f"[{tag}] vw={info['vw']} rows={len(rows)} pct right edges={edges} -> {'OK' if ok else 'FAIL'}")
    disc_rows = [r for r in rows if r["badge"]]
    for r in disc_rows:
        clash = ""
        if r["valueText"] and r["badge"]["r"] > r["valueText"]["l"] - 2:
            clash = " OVERLAP 涨跌额"
            ok = False
        if r["heart"] and r["badge"]["r"] > r["heart"]["l"]:
            clash += " OVERLAP 心形"
            ok = False
        if r["badgeVisible"] is False:
            clash += " 标签被裁掉"
            ok = False
        elif r["badgeVisible"] is None:
            clash += " (在屏幕外，未检查是否可见)"
        print(f"   {r['name']:<6} {r['close']['text']:>8} / {r['disc']['text']:>7} {r['badge']['text']}"
              f" badge {r['badge']['l']}-{r['badge']['r']}"
              f" 涨跌额 {r['valueText']}{clash}")
    if not disc_rows:
        print("   (当前没有盘前/盘后行)")
    return ok


results = {}


def run(tag, then):
    def got(info):
        (HERE / f"shot_change_{tag}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), "utf-8")
        w.watch_view.grab().save(str(HERE / f"shot_change_{tag}.png"))
        results[tag] = check(tag, info)
        then()
    w.watch_view.page().runJavaScript(JS, got)


def narrow():
    w.watch_view.setFixedWidth(560)
    QTimer.singleShot(1500, lambda: run("narrow", done))


def done():
    print("ALL PASS" if all(results.values()) else "FAIL", flush=True)
    os._exit(0)


QTimer.singleShot(15000, lambda: run("wide", narrow))
app.exec()
