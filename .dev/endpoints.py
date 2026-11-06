import pathlib
import re

d = pathlib.Path(__file__).parent
found = set()
for f in d.glob("*.js"):
    s = f.read_text(encoding="utf-8", errors="ignore")
    found.update(re.findall(r"[\"'`](/[a-zA-Z0-9_\-/]*(?:get|search|batch|stock)[a-zA-Z0-9_\-/]*)[\"'`]", s))
print("\n".join(sorted(found)))
