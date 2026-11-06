from pathlib import Path
import re

text = Path(__file__).with_name("app.cf1f9907b2.js").read_text(encoding="utf-8", errors="ignore")
for m in re.finditer(r"col change ellipsis.{0,1200}", text):
    print("--- MATCH ---")
    print(m.group(0))
    print()

# also hunt for status / 盘前 rendering near change
for pat in [
    r"priceDirect.{0,200}status.{0,200}",
    r"status.{0,80}盘前.{0,80}",
    r"session.{0,120}change",
    r"preTrade.{0,200}",
    r"baopan.{0,200}",
    r"tradeStatus.{0,200}",
]:
    ms = list(re.finditer(pat, text))
    print(f"PAT {pat!r}: {len(ms)}")
    for m in ms[:3]:
        print(" ", m.group(0)[:300])
