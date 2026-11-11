"""B5 第 3 步：回归报告网页——总账、怎么变的、有变化的每一道题两个版本的动画对比。

步骤：① 读两个版本的结果表、逐题对比（b5_compare）；② 有变化的那些对（变差 + 变好），两个版本各重跑一遍，
边考边录每一帧（重跑的撞没撞要和表里对得上，对不上就提醒）；③ 把数据塞进网页模板，存成一个 .html 文件。
运行（在项目根目录，先 conda activate py310；先跑过 b5_run v1 和 v2）：
    python -m examples.b_eval.b5_report            v1 → v2
    python -m examples.b_eval.b5_report v2 v1      反过来
结果：outputs/regression/report_<旧>_<新>.html，双击用浏览器打开（不用联网也能看，只是字体会换成系统字体）。
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from examples.b_eval.b5_compare import NAMES, compare, load
from examples.b_eval.b5_look import frames_of
from examples.b_eval.b5_run import N_QUESTIONS, OUT_DIR, ROADS, SEED, VERSIONS

np.seterr(divide="ignore")
TEMPLATE = Path(__file__).with_name("b5_report_template.html")
SHOW_S = 5.0                          # 网页只放前 5 秒
SCENARIO = ("gap_m", "ego_speed_mps", "cut_speed_mps", "cut_time_s", "cut_depth_m")


def record(task: tuple) -> dict:
    """(版本, 题号, 噪声, 延迟) → 这一次考试前 5 秒每一帧（数组按帧排好），外加撞没撞。"""
    version, q, noise_y_m, delay_s = task
    _, _, s, frames = frames_of(version, q, noise_y_m, delay_s)
    fr = [f for f in frames if f["t_s"] <= SHOW_S + 1e-9]
    return {
        "crashed": bool(s["crashed"]),
        "t": [round(f["t_s"], 1) for f in fr],
        "ex": [round(f["ego_x"], 2) for f in fr], "ey": [round(f["ego_y"], 3) for f in fr],
        "ev": [round(f["ego_v"], 2) for f in fr],
        "cx": [round(f["cutter_x"], 2) for f in fr], "cy": [round(f["cutter_y"], 3) for f in fr],
        "lead": [bool(f["lead_seen"]) for f in fr], "a": [round(f["accel_cmd"], 2) for f in fr],
    }


def changed_pairs(pairs: list[dict]) -> list[dict]:
    """有变化的对：变差在前（新版本越糟越靠前），再是变好（旧版本越糟越靠前），同一级按题号。"""
    worse = sorted((p for p in pairs if p["change"] == "变差"), key=lambda p: (-p["new"], p["key"]))
    better = sorted((p for p in pairs if p["change"] == "变好"), key=lambda p: (-p["old"], p["key"]))
    return worse + better


def report_data(old_v: str, new_v: str, pairs: list[dict], runs: dict) -> dict:
    """网页要的全部数据：两个版本的设置、考试题、总账、怎么变的、有变化的每一对（带两边每一帧）。"""
    counts = Counter(p["change"] for p in pairs)
    moves = Counter((NAMES[p["old"]], NAMES[p["new"]]) for p in pairs if p["change"] in ("变差", "变好"))
    items = []
    for p in changed_pairs(pairs):
        q, noise_y_m, delay_s = p["key"]
        row = p["old_row"]
        items.append({
            "q": q, "noise": noise_y_m, "delay": delay_s, "change": p["change"],
            "old": NAMES[p["old"]], "new": NAMES[p["new"]], "comes_in": bool(row["comes_in"]),
            "sc": {k: row[k] for k in SCENARIO},
            "runs": {old_v: runs[(old_v, p["key"])], new_v: runs[(new_v, p["key"])]},
        })
    return {
        "old": old_v, "new": new_v, "versions": {old_v: VERSIONS[old_v], new_v: VERSIONS[new_v]},
        "exam": {"n": N_QUESTIONS, "seed": SEED, "roads": ROADS},
        "counts": {c: counts[c] for c in ("变差", "变好", "不变", "躲不开")},
        "moves": [[a, b, n] for (a, b), n in moves.most_common()],
        "items": items,
    }


def write_html(data: dict, path: Path) -> None:
    body = (TEMPLATE.read_text(encoding="utf-8")
            .replace("__TITLE__", f"{data['old']} → {data['new']}")
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    html = ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<style>body{margin:0}</style>\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    path.write_text(html, encoding="utf-8")


def main():
    old_v, new_v = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("v1", "v2")
    workers = os.cpu_count() or 4
    pairs = compare(load(old_v), load(new_v))
    todo = changed_pairs(pairs)
    tasks = [(v, *p["key"]) for p in todo for v in (old_v, new_v)]
    print(f"{old_v} → {new_v}：{len(todo)} 对有变化，两个版本各重跑一遍录下每一帧（{len(tasks)} 次），开 {workers} 个进程……")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(record, tasks, chunksize=4))
    runs = {(task[0], tuple(task[1:])): r for task, r in zip(tasks, results)}

    mismatch = 0                                                  # 重跑的撞没撞，要和结果表对得上
    for p in todo:
        for v, row in ((old_v, p["old_row"]), (new_v, p["new_row"])):
            if runs[(v, p["key"])]["crashed"] != bool(row["crashed"]):
                mismatch += 1
    print(f"重跑和结果表对不上的：{mismatch} 次" + ("" if mismatch == 0 else "（代码改过？先重跑 b5_run）"))

    path = OUT_DIR / f"report_{old_v}_{new_v}.html"
    write_html(report_data(old_v, new_v, pairs, runs), path)
    print(f"报告：{path}（{path.stat().st_size / 1000:.0f} KB），双击用浏览器打开")


if __name__ == "__main__":
    main()
