"""只读解析 Edge 扩展 chrome.storage.local 的 LevelDB 日志，按顺序列出每次写入。用法：python dump_ext_storage.py [扩展ID]"""
import json, os, struct, sys

ext_id = sys.argv[1] if len(sys.argv) > 1 else "lagikhdcibhkdfjpibelemdjeebcpdhn"
d = os.path.join(os.environ["LOCALAPPDATA"], r"Microsoft\Edge\User Data\Default\Local Extension Settings", ext_id)


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7F) << s; s += 7
        if c < 0x80: return r, i


def records(data):
    buf = b""
    for blk in range(0, len(data), 32768):
        i, end = blk, min(blk + 32768, len(data))
        while i + 7 <= end:
            n, t = struct.unpack_from("<HB", data, i + 4)
            if n == 0 and t == 0: break
            frag = data[i + 7:i + 7 + n]; i += 7 + n
            if t == 1: yield frag
            elif t == 2: buf = frag
            elif t == 3: buf += frag
            elif t == 4: yield buf + frag


def summary(v):
    try: x = json.loads(v)
    except Exception: return v[:80]
    if isinstance(x, list):
        return f"{len(x)} 只: " + " ".join(e.get("stockCode", "?") for e in x if isinstance(e, dict))
    return json.dumps(x, ensure_ascii=False)[:120]


for name in sorted(f for f in os.listdir(d) if f.endswith(".log")):
    with open(os.path.join(d, name), "rb") as fh: data = fh.read()
    for rec in records(data):
        seq, cnt = struct.unpack_from("<QI", rec, 0); i = 12
        for _ in range(cnt):
            tag = rec[i]; i += 1
            kl, i = varint(rec, i); k = rec[i:i + kl].decode(); i += kl
            if tag == 1:
                vl, i = varint(rec, i); v = rec[i:i + vl].decode("utf-8", "replace"); i += vl
                print(f"#{seq} PUT {k}: {summary(v)}")
            else:
                print(f"#{seq} DEL {k}")
