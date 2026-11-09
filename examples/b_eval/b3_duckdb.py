"""B3 第 1 步：结果表进 Parquet，用 DuckDB 写 SQL 查。

DuckDB：装进 Python 就能用的分析型小数据库，直接对 CSV / Parquet 文件写 SQL（筛、分组算、排、拼）。
Parquet：按列存、带类型、压缩的表格文件；只读需要的列。
这里做三件事：
  ① 两批网格的结果表（种子 1、种子 2，各 64,000 行）从 CSV 转成 Parquet，比大小和读取速度
  ② b2_balance 里一大段数漏刹 / 误刹的 Python，换成一条 GROUP BY，挑出每种路况的 ★
  ③ 一条 SQL 把两批的排名并排列出来（窗口函数 rank）
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b3_duckdb          权重 10（漏刹 1 道 = 误刹 10 道）
    python -m examples.b_eval.b3_duckdb 30       换个权重
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
SEEDS = [1, 2]                                    # 出题种子：两批 1000 道题


def csv_path(seed: int) -> Path:
    """b2_grid 存的表：种子 1 叫 b2_grid_1000.csv，种子 2 叫 b2_grid_1000_seed2.csv。"""
    if seed == 1:
        return OUT_DIR / "b2_grid_1000.csv"
    return OUT_DIR / f"b2_grid_1000_seed{seed}.csv"


def to_parquet(con, csv: Path, parquet: Path, seed: int) -> None:
    """CSV → Parquet。多加一列 question_seed（出题种子），两批放在一起查时分得开。
    min_gap_m 要说清是小数：没挑到前车时它是 inf，CSV 里是文字 "inf"，DuckDB 自己猜会猜成文字。"""
    con.execute(f"""
        COPY (
            SELECT {seed} AS question_seed, *
            FROM read_csv('{csv.as_posix()}', types = {{'min_gap_m': 'DOUBLE'}})
        ) TO '{parquet.as_posix()}' (FORMAT parquet)
    """)


ROAD_STARS = """
WITH per_group AS (                                        -- ① 分组算：每种路况 × 每种考生设置，漏刹几道、误刹几道
    SELECT noise_y_m, delay_s, predict_s, confirm_frames, accel,
           count_if(missed)      AS missed_n,
           count_if(false_brake) AS false_n,
           count_if(missed) * $weight + count_if(false_brake) AS cost
    FROM read_parquet($file)
    WHERE status = 'ok'                                    -- 只数交了卷的
    GROUP BY noise_y_m, delay_s, predict_s, confirm_frames, accel
),
ranked AS (                                                -- ② 排：每种路况里，按代价从小到大排名
    SELECT *, rank() OVER (PARTITION BY noise_y_m, delay_s ORDER BY cost) AS rk
    FROM per_group
)
SELECT noise_y_m, delay_s, predict_s, confirm_frames, accel, missed_n, false_n, cost
FROM ranked
WHERE rk = 1                                               -- ③ 筛：只留每种路况的第一名（★）
ORDER BY noise_y_m, delay_s
"""

BOTH_SEEDS = """
WITH per_setting AS (                                      -- 每批题 × 每种考生设置：四种路况加起来的代价
    SELECT question_seed, predict_s, confirm_frames, accel,
           count_if(missed) * $weight + count_if(false_brake) AS cost
    FROM read_parquet($files)                              -- 两个文件一起读
    WHERE status = 'ok'
    GROUP BY question_seed, predict_s, confirm_frames, accel
),
ranked AS (
    SELECT *, rank() OVER (PARTITION BY question_seed ORDER BY cost) AS rk   -- 每批题里各排各的名次
    FROM per_setting
)
SELECT predict_s, confirm_frames, accel,                   -- 把两批并排：一行一种考生设置
       max(CASE WHEN question_seed = 1 THEN cost END) AS cost_1,
       max(CASE WHEN question_seed = 1 THEN rk END)   AS rank_1,
       max(CASE WHEN question_seed = 2 THEN cost END) AS cost_2,
       max(CASE WHEN question_seed = 2 THEN rk END)   AS rank_2,
       sum(cost) AS total
FROM ranked
GROUP BY predict_s, confirm_frames, accel
ORDER BY total
"""

ROAD_NAMES = {(0.0, 0.0): "干净", (0.0, 0.3): "延迟 0.3 秒", (0.2, 0.0): "噪声 0.2 米", (0.2, 0.3): "噪声 + 延迟"}


def setting_name(predict_s: float, confirm_frames: int, accel: bool) -> str:
    return f"{predict_s:.1f} 秒 · {confirm_frames} 帧 · {'匀加速' if accel else '匀速  '}"


def main():
    weight = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    con = duckdb.connect()                                 # 不给文件名 = 只在内存里，用完就没
    parquets = []

    print("① CSV → Parquet")
    for seed in SEEDS:
        csv = csv_path(seed)
        parquet = csv.with_suffix(".parquet")
        to_parquet(con, csv, parquet, seed)
        rows = con.execute("SELECT count(*) FROM read_parquet($f)", {"f": parquet.as_posix()}).fetchone()[0]
        print(f"  种子 {seed}：{csv.name} {csv.stat().st_size / 1e6:.1f} MB → {parquet.name} "
              f"{parquet.stat().st_size / 1e6:.2f} MB（{rows} 行）")
        parquets.append(parquet.as_posix())

    print("\n② 同一个查询（种子 2 每种路况的 ★），读 CSV 和读 Parquet 各用多久")
    for name, source in (("CSV", f"read_csv('{csv_path(2).as_posix()}', types = {{'min_gap_m': 'DOUBLE'}})"),
                         ("Parquet", f"read_parquet('{parquets[1]}')")):
        sql = ROAD_STARS.replace("read_parquet($file)", source)
        start = time.perf_counter()
        stars = con.execute(sql, {"weight": weight}).fetchall()
        print(f"  {name:8s}{(time.perf_counter() - start) * 1000:6.0f} 毫秒")

    print(f"\n③ 种子 2 每种路况的 ★（代价 = 漏刹 × {weight:g} + 误刹）")
    stars = con.execute(ROAD_STARS, {"weight": weight, "file": parquets[1]}).fetchall()
    for noise, delay, p, c, a, missed, false, cost in stars:
        print(f"  {ROAD_NAMES[(noise, delay)]:10s} {setting_name(p, c, a)}  漏刹 {missed:3d}  误刹 {false:3d}  代价 {cost:g}")

    print("\n④ 两批题并排：四种路况加起来的代价和名次（按两批合计排序，前 6 名）")
    print("  考生设置                   种子 1（名次）   种子 2（名次）   合计")
    rows = con.execute(BOTH_SEEDS, {"weight": weight, "files": parquets}).fetchall()
    for p, c, a, cost_1, rank_1, cost_2, rank_2, total in rows[:6]:
        print(f"  {setting_name(p, c, a)}    {cost_1:6g}（第 {rank_1:2d}）  {cost_2:6g}（第 {rank_2:2d}）  {total:6g}")


if __name__ == "__main__":
    main()
