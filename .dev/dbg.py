import sys, urllib.request, urllib.error
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import futu_api as f

ck = f.anonymous_cookies()
print("cookies:", list(ck))
c = f.FutuClient(ck)
import time, urllib.parse
params = {"page": 0, "page_size": 20, "t": int(time.time() * 1000)}
url = f.QUOTE_API + "/get-watch-list?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers=c._headers(f.params_payload(params)))
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(r.status, dict(r.headers))
        print(r.read()[:500])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, dict(e.headers))
    print(e.read()[:500])
