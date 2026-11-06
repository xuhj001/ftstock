"""本地自选整个流程的健壮性：拖动 / 添加 / 删除 / 启动校对 / 外部手改 json 交织在一起时数据不丢、不被覆盖"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

HERE = Path(__file__).resolve().parent
D = HERE / "flow_test"
F = D / "local_watchlist.json"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name, detail)
    if not ok:
        fails.append(name)


def fresh():
    shutil.rmtree(D, ignore_errors=True)
    D.mkdir()
    return lw.LocalWatchlist(F)  # 默认 6 只：NQmain QQQ GOOGL AAPL MSFT SOXX


def codes(entries=None):
    return [e["stockCode"] for e in (entries if entries is not None else lw.read_entries(F))]


def ids_of(w):
    return [e["stockId"] for e in w.entries]


def info(e, **kw):
    d = {"stock_id": e["stockId"], "symbol": f"{e['stockCode']}.US", "sc_name": e["name"],
         "instrument_type_v2": e["instrumentType"], "sub_instrument_type_v2": e["subInstrumentType"]}
    d.update(kw)
    return d


NEW = dict(lw.DEFAULT_ENTRIES[1], stockId="999999", stockCode="NEW", name="新股")

# 1. 拖动期间添加了一只：页面发来的顺序里没有它 → 排序生效，新股接在最后，不丢
w = fresh()
page = ids_of(w)
w.add(dict(NEW))
w.reorder(page[1:] + page[:1])
check("drag + concurrent add: merged", codes() == ["QQQ", "GOOGL", "AAPL", "MSFT", "SOXX", "NQmain", "NEW"], codes())

# 2. 页面顺序里有已删除的股票 → 忽略它，不会复活
w = fresh()
page = ids_of(w)
w.remove(page[2])
w.reorder(page[::-1])
check("drag with removed stock: not resurrected", codes() == ["SOXX", "MSFT", "AAPL", "QQQ", "NQmain"], codes())

# 3. 重复 id / 未知 id / 格式不对
w = fresh()
page = ids_of(w)
w.reorder([page[3], page[3], "nope"] + page)
check("dup / unknown ids ignored", codes() == ["AAPL", "NQmain", "QQQ", "GOOGL", "MSFT", "SOXX"], codes())
before = F.read_bytes()
for bad in (None, "x", [1, 2], [{"a": 1}]):
    try:
        w.reorder(bad)
        check(f"bad order {bad!r} rejected", False)
    except lw.SaveError:
        pass
check("bad orders rejected, file untouched", F.read_bytes() == before)

# 4. 启动校对改了名 → 再拖动，改过的名称保留
w = fresh()
page = ids_of(w)
w.sync([info(e, sc_name="改名后") if e["stockCode"] == "GOOGL" else info(e) for e in w.entries], page)
w.reorder(page[::-1])
by = {e["stockCode"]: e for e in lw.read_entries(F)}
check("sync then drag: renamed kept", by["GOOGL"]["name"] == "改名后" and codes()[0] == "SOXX")

# 5. 校对请求在路上时拖动了 → 校对结果只改资料，不动拖好的顺序
w = fresh()
checked = ids_of(w)
w.reorder(checked[::-1])
w.sync([info(e, sc_name="新名") if e["stockCode"] == "AAPL" else info(e) for e in w.entries], checked)
by = {e["stockCode"]: e for e in lw.read_entries(F)}
check("drag then late sync: order kept", codes()[0] == "SOXX" and by["AAPL"]["name"] == "新名", codes())

# 6. 在编辑器里手改了 json（合法）→ 之后的拖动 / 添加都基于手改后的内容，手改不被覆盖
w = fresh()
page = ids_of(w)
edited = lw.read_entries(F)
edited[0]["name"] = "我手改的名字"
del edited[5]  # 手动删掉 SOXX
F.write_text(json.dumps(edited, ensure_ascii=False, indent=2), encoding="utf-8")
w.reorder(page[1:] + page[:1])  # 页面还是旧的 6 只
saved = lw.read_entries(F)
check("manual edit kept through drag", saved[-1]["name"] == "我手改的名字" and "SOXX" not in codes(saved), codes(saved))
check("manual edit notice", any("外部修改" in n for n in w.notices), w.notices)
w.notices.clear()
w.add(dict(NEW))
check("then add on top of manual edit", codes() == ["QQQ", "GOOGL", "AAPL", "MSFT", "NQmain", "NEW"], codes())

# 7. 轮询发现手改：合法的立即载入，不写文件
w = fresh()
edited = lw.read_entries(F)
edited.reverse()
raw = json.dumps(edited, ensure_ascii=False).encode()
F.write_bytes(raw)
check("poll picks up valid edit", w.external_change() and codes(w.entries)[0] == "SOXX" and F.read_bytes() == raw)

# 8. 手改到一半（格式有误）：第一次不提示，第二次提示；不载入；之后保存先另存坏文件再覆盖
w = fresh()
good = codes(w.entries)
F.write_text('[{"stockId": "1", "stockCode": ', encoding="utf-8")
w.notices.clear()
first = (w.external_change(), list(w.notices))
second = (w.external_change(), list(w.notices))
third = (w.external_change(), list(w.notices))
check("half edit: first poll silent", first == (False, []), first)
check("half edit: second poll warns once", not second[0] and len(second[1]) == 1, second)
check("half edit: no repeat warning", len(third[1]) == 1)
check("half edit: memory kept", codes(w.entries) == good)
w.reorder(ids_of(w)[::-1])
corrupt = sorted(D.glob("local_watchlist.corrupt-*.json"))
check("save over half edit: copy preserved", len(corrupt) == 1
      and corrupt[0].read_text(encoding="utf-8").startswith('[{"stockId": "1"'), corrupt)
check("save over half edit: main valid", codes() == good[::-1])

# 9. 更新 .bak 这一步失败：不算保存失败，正式文件是新版，备份仍是完整的上一版
w = fresh()
prev = lw.read_entries(F)
real = lw._atomic_write
calls = {"n": 0}


def flaky(path, data):
    if path.name.endswith(".bak"):
        calls["n"] += 1
        if calls["n"] == 2:  # 第 1 次是备份旧版，第 2 次是把备份更新为新版
            raise OSError(32, "共享冲突")
    real(path, data)


lw._atomic_write = flaky
try:
    w.reorder(ids_of(w)[::-1])
    ok = True
except lw.SaveError as exc:
    ok = False
    print("   ", exc)
lw._atomic_write = real
check("bak update failure is non-fatal", ok and codes() == codes(prev)[::-1]
      and lw.read_entries(F.with_name(F.name + ".bak")) == prev)
check("no false external change after own save", not w.external_change())

shutil.rmtree(D)
print("ALL PASS" if not fails else f"FAILED: {fails}")
