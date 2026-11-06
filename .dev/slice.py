import sys, pathlib
f, needle, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
s = (pathlib.Path(__file__).parent / f).read_text(encoding='utf-8', errors='ignore')
i = s.find(needle)
print(i)
print(s[i + a:i + b])
