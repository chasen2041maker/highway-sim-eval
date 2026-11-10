"""B3 第 2 步：导出带“来源”的数据集。

每张网格结果表（outputs/b2_grid_*.csv）导出成 outputs/datasets/<同名>.parquet，每一行前面多几列“来源”：
  dataset           数据集名字（= 文件名）
  question_seed     出题种子；n_questions：出了几道题
  commit            跑它的代码版本（git 提交号）；没有运行清单的老表是空的 = 来源不明
  uncommitted       跑的时候有没有没提交的改动（有的话，光看提交号说不全是哪版代码）
  code_fingerprint  代码指纹（运行清单或边考边存日志里有；没有就是空的）
  run_started_at    什么时候开跑
来源从同名的运行清单（.json）和边考边存日志（.jsonl）里取；都没有，就老老实实写空，不编。
同一个数据集每一行的来源都一样：Parquet 按列压缩，重复 64,000 遍也几乎不占地方。
最后用一条 SQL 列出“数据集目录”：每个数据集几行、哪版代码跑的、来源全不全。
运行（在项目根目录，先 conda activate py310）：
    python -m examples.b_eval.b3_export
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
NAME = re.compile(r"b2_grid_(\d+)(?:_seed(\d+))?$")        # b2_grid_<题数>[_seed<种子>]

CATALOG = """
SELECT dataset,
       any_value(question_seed) AS seed,                   -- 同一个数据集里每行都一样，随便拿一个
       any_value(n_questions)   AS n,
       count(*)                 AS n_rows,
       any_value(commit)        AS commit,
       any_value(code_fingerprint) AS fingerprint,
       CASE WHEN any_value(commit) IS NULL THEN '来源不明'
            WHEN any_value(uncommitted)    THEN '有没提交的改动'
            ELSE '可追溯'
       END AS provenance
FROM read_parquet($files, union_by_name = true)
GROUP BY dataset
ORDER BY dataset
"""


def provenance(csv: Path) -> dict:
    """从同名的运行清单和边考边存日志里找来源；找不到的就是 None（导出后是空）。"""
    info = {"commit": None, "uncommitted": None, "code_fingerprint": None, "run_started_at": None}
    manifest = csv.with_suffix(".json")
    if manifest.exists():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        info["commit"] = m.get("commit") or None
        info["uncommitted"] = len(m.get("uncommitted_changes", [])) > 0
        info["code_fingerprint"] = m.get("code_fingerprint")          # 11-10 以后的清单才有
        info["run_started_at"] = m.get("started_at")
    log = csv.with_suffix(".jsonl")
    if info["code_fingerprint"] is None and log.exists():
        last = ""
        with log.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
        try:
            info["code_fingerprint"] = json.loads(last).get("code")    # 最后一次跑的代码指纹
        except json.JSONDecodeError:
            pass
    return info


def export(con, csv: Path, out_dir: Path) -> Path:
    """一张结果表 → 带来源的 Parquet，返回导出的文件。"""
    m = NAME.match(csv.stem)
    n = int(m.group(1))
    seed = int(m.group(2)) if m.group(2) else 1
    info = provenance(csv)
    rel = con.sql("""
        SELECT CAST($dataset AS VARCHAR)            AS dataset,
               CAST($seed AS INTEGER)               AS question_seed,
               CAST($n AS INTEGER)                  AS n_questions,
               CAST($commit AS VARCHAR)             AS commit,
               CAST($uncommitted AS BOOLEAN)        AS uncommitted,
               CAST($fingerprint AS VARCHAR)        AS code_fingerprint,
               CAST($started AS TIMESTAMPTZ)        AS run_started_at,
               *
        FROM read_csv($csv, types = {'min_gap_m': 'DOUBLE'})
    """, params={"dataset": csv.stem, "seed": seed, "n": n, "commit": info["commit"],
                 "uncommitted": info["uncommitted"], "fingerprint": info["code_fingerprint"],
                 "started": info["run_started_at"], "csv": csv.as_posix()})
    out = out_dir / f"{csv.stem}.parquet"
    rel.write_parquet(out.as_posix())
    return out


def main():
    out_dir = OUT_DIR / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    files = []
    for csv in sorted(OUT_DIR.glob("b2_grid_*.csv")):
        if NAME.match(csv.stem):
            files.append(export(con, csv, out_dir).as_posix())
    print(f"导出了 {len(files)} 个数据集到 {out_dir}\n")
    print("数据集目录：")
    con.sql(CATALOG, params={"files": files}).show(max_width=200)


if __name__ == "__main__":
    main()
