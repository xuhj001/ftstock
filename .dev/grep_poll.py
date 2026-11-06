import re
from pathlib import Path

HERE = Path(__file__).parent
for name, alias in [("6891.0c0fb0e4ab.js", "E"), ("751.98f01d7fc0.js", "l"), ("app.cf1f9907b2.js", "ie")]:
    s = (HERE / name).read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r"\(0,%s\.(qk|P|lw|mn|py|ju|Ew|xH)\)|%s\.(qk|P|lw|mn|py|ju|Ew|xH)\b" % (alias, alias), s):
        print(f"== {name} @{m.start()} {m.group(0)}")
        print(s[max(0, m.start() - 350):m.end() + 250].replace("\n", " "))
