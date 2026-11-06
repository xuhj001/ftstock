"""本地自选启动校对（LocalWatchlist.sync）的离线测试"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

HERE = Path(__file__).resolve().parent
D = HERE / "sync_test"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail)
    if not ok:
        fails.append(name)


def info(e, **kw):
    base = {"stock_id": e["stockId"], "symbol": f"{e['stockCode']}.US", "sc_name": e["name"],
            "instrument_type_v2": e["instrumentType"], "sub_instrument_type_v2": e["subInstrumentType"]}
    base.update(kw)
    return base


def fresh():
    shutil.rmtree(D, ignore_errors=True)
    D.mkdir()
    w = lw.LocalWatchlist(D / "local_watchlist.json")  # 默认 6 只：NQmain QQQ GOOGL AAPL MSFT SOXX
    return w


w = fresh()
nq, qqq, googl, aapl, msft, soxx = [dict(e) for e in w.entries]
ids = [e["stockId"] for e in w.entries]

# 1. 全部一致（期货名称带合约月份也算一致）→ 不写文件
mtime = (D / "local_watchlist.json").stat().st_mtime_ns
infos = [info(nq, sc_name=nq["name"] + " (2612)"), info(qqq), info(googl), info(aapl), info(msft), info(soxx)]
changes, missing = w.sync(infos, ids)
check("no change -> nothing saved", not changes and not missing
      and (D / "local_watchlist.json").stat().st_mtime_ns == mtime, (changes, missing))

# 2. 改代码、改名、改类型、缺失、垃圾值
infos = [
    info(nq, sc_name="纳斯达克100指数期货主连 (2703)"),
    info(qqq, symbol="QQQM.US"),                     # 换代码
    info(googl, sc_name="Alphabet-A"),               # 改名
    info(aapl, instrument_type_v2=4, sub_instrument_type_v2=4002),  # 类型变化
    info(msft, symbol=None, sc_name="", instrument_type_v2=True, sub_instrument_type_v2=-1),  # 垃圾值全忽略
    # soxx 缺失
]
changes, missing = w.sync(infos, ids)
print("  changes:", changes, "missing:", missing)
saved = lw.read_entries(D / "local_watchlist.json")
by = {e["stockId"]: e for e in saved}
check("code updated", by[qqq["stockId"]]["stockCode"] == "QQQM")
check("name updated", by[googl["stockId"]]["name"] == "Alphabet-A")
check("type updated", (by[aapl["stockId"]]["instrumentType"], by[aapl["stockId"]]["subInstrumentType"]) == (4, 4002))
check("futures month ignored", by[nq["stockId"]]["name"] == nq["name"])
check("garbage ignored", by[msft["stockId"]] == msft)
check("missing kept, reported", by[soxx["stockId"]] == soxx and missing == ["SOXX"])
check("order and ids unchanged", [e["stockId"] for e in saved] == ids)
check("3 changes reported", len(changes) == 3, changes)
check("bak == main", lw.read_entries(D / "local_watchlist.json.bak") == saved)

# 3. 校对期间新加的股票（不在 checked_ids 里）不算缺失、不动
w = fresh()
extra = dict(qqq, stockId="999999", stockCode="NEW")
w.entries.append(extra)
w.save()
changes, missing = w.sync([info(e) for e in w.entries[:6]], ids)
check("entries added during check untouched", not missing and w.entries[-1] == extra, missing)

# 4. 保存失败 → 内存回滚，文件不变
w = fresh()
before = (D / "local_watchlist.json").read_bytes()
real = lw._replace
lw._replace = lambda *a: (_ for _ in ()).throw(OSError(5, "拒绝访问"))
try:
    w.sync([info(qqq, sc_name="改名")], ids)
    check("save error raised", False)
except lw.SaveError as exc:
    check("save error raised", True, str(exc))
lw._replace = real
check("memory rolled back", w.find(qqq["stockId"])["name"] == qqq["name"])
check("file unchanged", (D / "local_watchlist.json").read_bytes() == before)

shutil.rmtree(D)
print("ALL PASS" if not fails else f"FAILED: {fails}")
