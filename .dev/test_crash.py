"""模拟保存过程中程序被强杀（os._exit，不执行任何清理），检查重启后数据仍完整一致。
覆盖三种保存：添加一只股票（add），拖动排序（reorder），启动校对更新代码 / 名称（sync）。"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_watchlist as lw  # noqa: E402

HERE = Path(__file__).resolve().parent
NEW = dict(lw.DEFAULT_ENTRIES[1], stockId="999999", stockCode="NEWONE")
OLD = [dict(e) for e in lw.DEFAULT_ENTRIES]
# 拖动：第 1 只拖到第 4 位
MOVED = OLD[1:4] + OLD[:1] + OLD[4:]
# 启动校对：QQQ 换了代码、GOOGL 改了名
SYNCED = [dict(e) for e in OLD]
SYNCED[1]["stockCode"], SYNCED[2]["name"] = "QQQM", "Alphabet-A"
SYNC_INFOS = [{"stock_id": e["stockId"], "symbol": f"{e['stockCode']}.US", "sc_name": e["name"],
               "instrument_type_v2": e["instrumentType"], "sub_instrument_type_v2": e["subInstrumentType"]}
              for e in SYNCED]
EXPECT = {"add": OLD + [NEW], "reorder": MOVED, "sync": SYNCED}


def child(directory: str, op: str, func: str, n: int, mode: str):
    calls = {"write": 0, "replace": 0}
    real_write, real_replace = lw._write_durable, lw._replace

    def write(path, data):
        calls["write"] += 1
        if func == "write" and calls["write"] == n:
            if mode == "half":
                with open(path, "wb") as f:
                    f.write(data[: len(data) // 2])
                    f.flush()
                    os.fsync(f.fileno())
                os._exit(9)
            real_write(path, data)
            os._exit(9)
        real_write(path, data)

    def replace(src, dst):
        calls["replace"] += 1
        if func == "replace" and calls["replace"] == n and mode == "before":
            os._exit(9)
        real_replace(src, dst)
        if func == "replace" and calls["replace"] == n and mode == "after":
            os._exit(9)

    lw._write_durable, lw._replace = write, replace
    w = lw.LocalWatchlist(Path(directory) / "local_watchlist.json")
    if op == "add":
        w.add(dict(NEW))
    elif op == "reorder":
        w.reorder([e["stockId"] for e in MOVED])
    else:
        w.sync(SYNC_INFOS, [e["stockId"] for e in OLD])
    os._exit(0)  # 没有触发中断点（保存已完整结束）


def main():
    ok = True
    for op in ("add", "reorder", "sync"):
        new = EXPECT[op]
        for func in ("write", "replace"):
            for n in (1, 2, 3):
                for mode in (("half", "after") if func == "write" else ("before", "after")):
                    d = HERE / "crash_test"
                    shutil.rmtree(d, ignore_errors=True)
                    d.mkdir()
                    w0 = lw.LocalWatchlist(d / "local_watchlist.json")
                    w0.entries = [dict(e) for e in OLD]
                    w0.save()
                    r = subprocess.run([sys.executable, __file__, "child", str(d), op, func, str(n), mode])
                    w = lw.LocalWatchlist(d / "local_watchlist.json")
                    state = "old" if w.entries == OLD else "new" if w.entries == new else "BROKEN"
                    main_ok = lw.read_entries(d / "local_watchlist.json") == w.entries
                    bak_ok = lw.read_entries(d / "local_watchlist.json.bak") in (OLD, new)
                    # 历史数据一只都不能少
                    kept = {e["stockId"] for e in OLD} <= {e["stockId"] for e in w.entries}
                    left = sorted(f.name for f in d.iterdir() if f.suffix == ".tmp" or ".corrupt-" in f.name)
                    good = state != "BROKEN" and main_ok and bak_ok and kept and not left and not w.warning
                    ok &= good
                    print(f"{'PASS' if good else 'FAIL'} {op:7s} 中断点 {func}#{n} {mode:6s} exit={r.returncode} "
                          f"→ 数据={state} 正式文件完整={main_ok} 备份完整={bak_ok} 股票无丢失={kept} "
                          f"残留={left} {w.warning}", flush=True)
                    shutil.rmtree(d)
    print("ALL PASS" if ok else "SOME FAILED")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        child(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6])
    else:
        main()
