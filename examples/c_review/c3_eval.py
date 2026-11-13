"""C3 第 3e 步（下）：拿答案卷（outputs/c3/label/labels.json）考规则和模型。

  rules   规则：均匀抽的 50 帧里答案是“危险 / 值得看”的，规则挑中了几个（召回，逐帧和按事件两种算法）；
          规则挑中的里有几个答案真是“危险 / 值得看”（精确）。不调模型。
  single  一个模型（3c）把 51 条都复核一遍。
  multi   分开做（3d：看图员 / 读数员 / 裁判）把 51 条都复核一遍。
  report  把跑过的模型都对一遍答案：准确率、混淆矩阵、“值得看”的精确和召回、原因对不对、花了多少 token。

模型的回答边跑边存进 outputs/c3/eval/<single|multi>.jsonl；断网中途停了，再跑一次会跳过答过的（B2 的断点续跑）。
mini 只有 51 条、正样本 3 条，所有比例都带 95% 置信区间（B4），区间很宽是正常的：这一步是把流程跑通。

运行（项目根目录，conda activate py310；先跑过 c3_label_tasks，答案卷放在 outputs/c3/label/labels.json）：
    python -m examples.c_review.c3_eval rules
    python -m examples.c_review.c3_eval single
    python -m examples.c_review.c3_eval multi
    python -m examples.c_review.c3_eval report
换了提示词 / 规范再跑一轮，加一个轮次名，结果另存、不盖掉上一轮：
    python -m examples.c_review.c3_eval single v2          → outputs/c3/eval/single_v2.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluation.confidence import wilson_interval
from examples.c_review.c3_pick import scene_frames
from examples.c_review.c3_review import build_prompt, facts, parse_answer, picked, review_photo
from examples.c_review.c3_review_multi import ask_text, judge_prompt, looker_prompt, reader_prompt
from examples.c_review.c3_vlm_hello import ask
from examples.c_review.llm_client import config
from examples.c_review.nuscenes_tables import load

ROOT = Path(__file__).resolve().parents[2]
LABEL_DIR = ROOT / "outputs" / "c3" / "label"
EVAL_DIR = ROOT / "outputs" / "c3" / "eval"
VERDICTS = ["危险", "值得看", "没事", "看不出"]
POSITIVE = ("危险", "值得看")


def load_answer_key():
    tasks = json.loads((LABEL_DIR / "tasks.json").read_text(encoding="utf-8"))
    labels = json.loads((LABEL_DIR / "labels.json").read_text(encoding="utf-8"))["labels"]
    return tasks, labels


def ci(k: int, n: int) -> str:
    if n == 0:
        return "—（0 个）"
    lo, hi = wilson_interval(k, n)
    return f"{k}/{n} = {k / n:.0%}（95% 区间 {lo:.0%}–{hi:.0%}）"


# ---------- 规则 ----------

def rule_scores(tasks, labels) -> dict:
    """均匀抽的帧上算规则的召回（逐帧 / 按事件：前后 0.5 秒内挑中就算抓到），所有规则挑中的帧上算精确。"""
    picked_k = {}
    for t in tasks:
        if t["rule"]:
            picked_k.setdefault(t["scene"], set()).add(t["frame"])
    pos = [t for t in tasks if "均匀" in t["source"] and labels[t["id"]]["verdict"] in POSITIVE]
    by_frame = [t for t in pos if t["frame"] in picked_k.get(t["scene"], set())]
    by_event = [t for t in pos if any(abs(f - t["frame"]) <= 1 for f in picked_k.get(t["scene"], set()))]
    picks = [t for t in tasks if t["rule"]]
    right = [t for t in picks if labels[t["id"]]["verdict"] in POSITIVE]
    return {"pos": pos, "by_frame": by_frame, "by_event": by_event, "picks": picks, "right": right}


def report_rules(tasks, labels):
    r = rule_scores(tasks, labels)
    print("规则（真实的路 + 同方向 + TTC < 3 秒 + 急刹 < −3）")
    print(f"  均匀抽的帧里，答案是危险 / 值得看的：{[t['id'] for t in r['pos']]}")
    print(f"  召回（逐帧）：{ci(len(r['by_frame']), len(r['pos']))}")
    print(f"  召回（按事件，前后 0.5 秒内挑中就算）：{ci(len(r['by_event']), len(r['pos']))}")
    print(f"  精确（挑中的里真值得看的）：{ci(len(r['right']), len(r['picks']))}")


# ---------- 模型 ----------

def results_path(mode: str) -> Path:
    """mode 可以带轮次名：single、single_v2、multi……"""
    return EVAL_DIR / f"{mode}.jsonl"


def done_ids(mode: str) -> set:
    p = results_path(mode)
    if not p.exists():
        return set()
    return {json.loads(line)["id"] for line in p.read_text(encoding="utf-8").splitlines() if line.strip()}


def tokens(*usages) -> int:
    return sum(u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usages)


def review_one(mode, model, T, frames, k) -> dict:
    mode = mode.partition("_")[0]
    """复核一帧，返回要存的一行（答案、依据、token；分开做还存两份报告）。"""
    p = picked(frames, k, True, True)
    fact_text = facts(frames, k, True, True)
    photo = review_photo(T, frames, k, True, True)
    row = {}
    if mode == "single":
        text, u = ask(model, build_prompt(fact_text, p is not None), photo)
        row["tokens"] = tokens(u)
    else:
        look, u1 = ask(model, looker_prompt(p), photo)
        read, u2 = ask_text(model, reader_prompt(fact_text, p is not None))
        text, u3 = ask(model, judge_prompt(look.strip(), read.strip(), p is not None), photo)
        row.update(tokens=tokens(u1, u2, u3), look=look.strip(), read=read.strip())
    r = parse_answer(text)
    row.update(raw=text.strip(), valid=r["valid"], verdict=r.get("verdict"), cause=r.get("cause"),
               evidence=r.get("evidence", ""), why=r.get("why", ""))
    return row


def run(mode: str):
    _, _, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    tasks, _ = load_answer_key()
    skip = done_ids(mode)
    todo = [t for t in tasks if t["id"] not in skip]
    print(f"{mode}：{len(tasks)} 条，已答 {len(skip)}，这次要答 {len(todo)}（模型 {model}）")
    if not todo:
        return
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    T = load()
    scenes = {s["name"]: s for s in T["scene"].values()}
    frames_cache = {}
    with results_path(mode).open("a", encoding="utf-8") as f:
        for n, t in enumerate(todo, 1):
            if t["scene"] not in frames_cache:
                frames_cache[t["scene"]] = scene_frames(T, scenes[t["scene"]])
            try:
                row = review_one(mode, model, T, frames_cache[t["scene"]], t["frame"] - 1)
            except RuntimeError as e:                      # 断网、中转挂了：停下，已经答的都存着
                print(f"  第 {n} 条 {t['id']} 出错，先停：{e}\n  再跑一次同样的命令会接着答。")
                return
            row = {"id": t["id"], "model": model, **row}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()                                      # 边答边存
            shown = f"{row['verdict']}{' / ' + row['cause'] if row['cause'] else ''}" if row["valid"] else f"无效（{row['why']}）"
            print(f"  [{n}/{len(todo)}] {t['id']}：{shown}（{row['tokens']} token）")


# ---------- 对答案 ----------

def model_scores(tasks, labels, rows) -> dict:
    """对答案。无效回答算错。返回计数，方便测试。"""
    by_id = {r["id"]: r for r in rows}
    seen = [t for t in tasks if t["id"] in by_id]
    conf = {h: {m: 0 for m in VERDICTS + ["无效"]} for h in VERDICTS}
    right = tp = fp = fn = cause_ok = 0
    wrong = []
    for t in seen:
        h, r = labels[t["id"]], by_id[t["id"]]
        m = r["verdict"] if r["valid"] else "无效"
        conf[h["verdict"]][m] += 1
        if m == h["verdict"]:
            right += 1
        else:
            wrong.append((t["id"], h, r))
        hp, mp = h["verdict"] in POSITIVE, m in POSITIVE
        tp += hp and mp
        fp += (not hp) and mp
        fn += hp and not mp
        if hp and mp and r["cause"] == h["cause"]:
            cause_ok += 1
    return {"n": len(seen), "right": right, "conf": conf, "tp": tp, "fp": fp, "fn": fn, "cause_ok": cause_ok,
            "tokens": sum(by_id[t["id"]]["tokens"] for t in seen), "wrong": wrong,
            "invalid": sum(1 for t in seen if not by_id[t["id"]]["valid"])}


def report_model(mode, tasks, labels):
    p = results_path(mode)
    if not p.exists():
        print(f"\n{mode}：还没跑")
        return
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    s = model_scores(tasks, labels, rows)
    base, _, tag = mode.partition("_")
    name = {"single": "一个模型（3c）", "multi": "分开做（3d）"}[base] + (f"·{tag}" if tag else "·第一轮")
    print(f"\n{name}：答了 {s['n']} / {len(tasks)} 条，无效 {s['invalid']} 条，一共 {s['tokens']:,} token（每条约 {s['tokens'] // max(s['n'], 1):,}）")
    print(f"  第 1 题全对（4 选 1）：{ci(s['right'], s['n'])}")
    print(f"  值得看 / 危险 —— 精确（它说值得看的里真值得看）：{ci(s['tp'], s['tp'] + s['fp'])}")
    print(f"                   召回（真值得看的里它抓到）：{ci(s['tp'], s['tp'] + s['fn'])}")
    print(f"  两边都说值得看时，原因也对：{ci(s['cause_ok'], s['tp'])}")
    print("  混淆矩阵（行 = 答案，列 = 模型）：")
    cols = VERDICTS + ["无效"]
    print("    " + "".join(f"{c:>6}" for c in [""] + cols))
    for h in VERDICTS:
        print("    " + f"{h:>6}" + "".join(f"{s['conf'][h][c]:>7}" for c in cols))
    if s["wrong"]:
        print("  答错的：")
        for tid, h, r in s["wrong"]:
            m = f"{r['verdict']}{' / ' + r['cause'] if r['cause'] else ''}" if r["valid"] else "无效"
            print(f"    {tid}：答案 {h['verdict']}{' / ' + h['cause'] if h['cause'] else ''}，模型 {m}。依据：{(r['evidence'] or r['raw'])[:80]}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    tasks, labels = load_answer_key()
    if mode == "rules":
        report_rules(tasks, labels)
    elif mode in ("single", "multi"):
        tag = sys.argv[2] if len(sys.argv) > 2 else ""
        run(mode + (f"_{tag}" if tag else ""))
    elif mode == "report":
        report_rules(tasks, labels)
        files = sorted(EVAL_DIR.glob("*.jsonl")) if EVAL_DIR.exists() else []
        for p in files:
            report_model(p.stem, tasks, labels)
        if not files:
            print("\n模型：还没跑")
    else:
        print("用法：python -m examples.c_review.c3_eval rules | single | multi | report")


if __name__ == "__main__":
    main()
