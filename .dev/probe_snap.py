import json
import sys
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FutuProbe/1.0"
ids = sys.argv[1] if len(sys.argv) > 1 else "205189"
for host in ("https://q.futunn.com", "https://news.futunn.com", "https://www.futunn.com"):
    url = f"{host}/api/stock/list?stock_ids={ids}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "x-futu-nnq-new-website": "nnq",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "ignore")
            print(host, r.status, r.headers.get("content-type"))
            try:
                print(json.dumps(json.loads(body), ensure_ascii=False)[:1500])
            except ValueError:
                print(body[:200])
    except Exception as e:  # noqa: BLE001
        print(host, "ERR", e)
