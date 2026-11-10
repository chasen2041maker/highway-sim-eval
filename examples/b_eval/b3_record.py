"""B3 第 3 步（上）：逐帧录像。

B1 的 5 道加塞题（陪跑、切入 10 米、切入 5 米、压线、靠线），让“不预测”的老考生（往前看 0 秒）考一遍，
每 0.1 秒录一帧：考生看到了什么（过了噪声和延迟以后的样子）、真实世界怎样、考生做了什么决定。
一帧一行，存成 outputs/recordings/b1_bank_p0.parquet。“考生看到的那张小表”（几辆车 × 5 个数）直接当一个数组存在一格里。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b3_record
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np

from examples.b_eval.b1_cut_in import BANK, run

np.seterr(divide="ignore")
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "recordings"
PREDICT_S = 0.0                   # 录的是“不预测”的老考生


def record(predict_s: float = PREDICT_S) -> list[dict]:
    """5 道题各考一遍，返回所有帧（一帧一个字典，带上第几题、考生设置、这道题最后撞没撞）。"""
    rows = []
    for n, sc in enumerate(BANK, start=1):
        frames = []
        s = run(sc, predict_s, frames=frames)
        for f in frames:
            rows.append({"question": n, "predict_s": predict_s, "confirm_frames": 1, "accel": False,
                         "crashed": bool(s["crashed"]), **f})
        print(f"  第 {n} 题：录了 {len(frames)} 帧（{len(frames) * 0.1:.1f} 秒），撞了：{'是' if s['crashed'] else '否'}")
    return rows


def save(rows: list[dict], path: Path) -> None:
    """先写成 JSON Lines，再用 DuckDB 转成 Parquet（seen 那一列会自动变成“数组的数组”）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    duckdb.sql(f"COPY (SELECT * FROM read_json('{tmp.as_posix()}')) TO '{path.as_posix()}' (FORMAT parquet)")
    tmp.unlink()


def main():
    print(f"录像：5 道题，考生往前看 {PREDICT_S:g} 秒")
    rows = record()
    path = OUT_DIR / "b1_bank_p0.parquet"
    save(rows, path)
    print(f"一共 {len(rows)} 帧 → {path}（{path.stat().st_size / 1000:.0f} KB）")


if __name__ == "__main__":
    main()
