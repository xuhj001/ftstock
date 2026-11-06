import pathlib
import sys

f, pos, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
s = (pathlib.Path(__file__).parent / f).read_text(encoding="utf-8", errors="ignore")
print(s[pos + a:pos + b])
