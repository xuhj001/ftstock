"""Dump change-column DOM/CSS from the live watchlist page."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import futu_app  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

# Reuse the running profile so we share cookies/login; don't fight the lock —
# launch a second window with a temp profile instead.
futu_app.PROFILE_DIR = Path(__file__).parent / "qt_profile_dump"

app = QApplication(sys.argv)
w = futu_app.MainWindow(futu_app.create_profile(app), "AAPL-US")
w.resize(1400, 900)
w.show()

JS = r"""
(function () {
  var items = document.querySelectorAll('section.watchlist-modal .list-item');
  var out = [];
  items.forEach(function (row, i) {
    if (i > 8) return;
    var change = row.querySelector('.col.change');
    if (!change) return;
    var name = (row.querySelector('.col.name') || {}).textContent || '';
    var cs = getComputedStyle(change);
    var disc = change.querySelector('.disc-change');
    var main = change.querySelector(':scope > span:not(.disc-change)');
    var discCs = disc ? getComputedStyle(disc) : null;
    var mainCs = main ? getComputedStyle(main) : null;
    var badge = change.querySelector('.disc-status');
    out.push({
      name: name.trim().slice(0, 40),
      html: change.innerHTML.slice(0, 500),
      change: {
        w: change.offsetWidth, textAlign: cs.textAlign,
        display: cs.display, flex: cs.flexDirection + '/' + cs.alignItems + '/' + cs.justifyContent,
        pad: cs.padding, font: cs.fontSize
      },
      main: main && {
        text: (main.textContent || '').trim(),
        w: main.offsetWidth, textAlign: mainCs.textAlign,
        display: mainCs.display, margin: mainCs.margin, pad: mainCs.padding
      },
      disc: disc && {
        text: (disc.textContent || '').trim().replace(/\s+/g, ' '),
        w: disc.offsetWidth, textAlign: discCs.textAlign,
        display: discCs.display, flex: discCs.flexDirection + '/' + discCs.alignItems + '/' + discCs.justifyContent,
        margin: discCs.margin, pad: discCs.padding, gap: discCs.gap,
        font: discCs.fontSize
      },
      badge: badge && {
        text: (badge.textContent || '').trim(),
        w: badge.offsetWidth, className: badge.className
      }
    });
  });
  var sheet = Array.from(document.styleSheets).flatMap(function (s) {
    try { return Array.from(s.cssRules || []); } catch (e) { return []; }
  }).filter(function (r) {
    return r.selectorText && /disc-change|disc-status|\.col\.change/.test(r.selectorText);
  }).map(function (r) { return r.cssText; });
  return {count: items.length, rows: out, css: sheet.slice(0, 40)};
})()
"""


OUT = Path(__file__).with_name("dump_change_result.json")


def dump():
    def got(res):
        import json
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print("WROTE", OUT, "rows", (res or {}).get("count"), flush=True)
        os._exit(0)

    print("dumping...", flush=True)
    w.watch_view.page().runJavaScript(JS, got)


def tick(n=0):
    state = w.states.get("watch") or {}
    print(f"tick {n} ready={state.get('ready')} title={state.get('title')}", flush=True)
    # wait for list items; disc info appears in pre/post market
    if n >= 12:
        dump()
        return
    if n > 45:
        print("TIMEOUT", w.states, flush=True)
        os._exit(1)
    QTimer.singleShot(1000, lambda: tick(n + 1))


QTimer.singleShot(2000, lambda: tick(0))
app.exec()
