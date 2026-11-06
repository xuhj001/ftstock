import json
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FutuProbe/1.0"
kw = sys.argv[1] if len(sys.argv) > 1 else "TSLA"
url = "https://www.futunn.com/search-stock/predict?" + urllib.parse.urlencode(
    {"keyword": kw, "lang": "zh-cn", "site": "cn"})
req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=15) as r:
    body = r.read().decode("utf-8", "ignore")
    print(r.status, r.headers.get("content-type"))
    try:
        data = json.loads(body)
        print(json.dumps(data, ensure_ascii=False)[:2500])
    except ValueError:
        print(body[:300])
