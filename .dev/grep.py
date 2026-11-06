import re, sys, pathlib
pat = re.compile(sys.argv[1])
w = int(sys.argv[2]) if len(sys.argv) > 2 else 250
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 40
n = 0
for f in pathlib.Path(__file__).parent.glob('*.js'):
    s = f.read_text(encoding='utf-8', errors='ignore')
    for m in pat.finditer(s):
        print(f'== {f.name} @{m.start()}')
        print(s[max(0, m.start()-w):m.end()+w].replace('\n', ' '))
        n += 1
        if n >= lim:
            sys.exit()
