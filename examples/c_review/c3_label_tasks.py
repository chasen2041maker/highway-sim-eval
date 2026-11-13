"""C3 第 3e 步（上）：抽出要人工标答案的帧，生成一个本地标注网页。

抽法：每段每 4 秒取 1 帧（第 5、13、21、29、37 帧，10 段 = 50 帧，不靠规则挑），再加上规则挑中的那几条。
均匀抽的帧能量出规则漏挑了几个（召回率）；所有帧都能拿来考模型复核得准不准。
标的人只看到照片（规则挑中的东西画橙框）、前后 0.5 秒的小图、车速和加速度，看不到规则怎么判的，免得被带偏。
2026-11-13：本人选“模型预标注 + 人工复核”：c3_prelabels.json 是 Claude 看照片标的（拿不准的标了 review），
网页先显示预标注，人只改要改的；导出时每条记明是“人”确认过的还是“预标注”。
规范（本人 11-13 定）：平稳跟车减速、防御性减速（斑马线、路口、施工区前）都算“没事”。

两把尺子（3b，3e 起“误挑”改叫“没事”：均匀抽的帧不是规则挑的，谈不上挑错）：
  值不值：危险 / 值得看 / 没事 / 看不出
  原因（危险、值得看才填）：前车急刹 / 加塞 / 横穿 / 行人或骑车人 / 迎面来车 / 静止障碍物 / 其他

mini 只有 10 段，真正值得看的时刻很少，这一步是把流程跑通，数字要带置信区间、写明样本小。

运行（项目根目录，conda activate py310）：
    python -m examples.c_review.c3_label_tasks
输出（outputs 不进 git）：
    outputs/c3/label/c3_label.html   双击打开就能标；进度存在浏览器里，标完点“导出答案”
    outputs/c3/label/tasks.json      每条任务的来源和规则怎么判的（算分时用，网页里不显示）
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from examples.c_review.c3_pick import accel, draw_box, pick_scene, scene_frames
from examples.c_review.nuscenes_tables import load

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "c3" / "label"
TEMPLATE = Path(__file__).with_name("c3_label_template.html")
PRELABELS = Path(__file__).with_name("c3_prelabels.json")   # Claude 的预标注；网页里没标过的条目先显示它，等人复核
UNIFORM_K = [4, 12, 20, 28, 36]          # 第 5、13、21、29、37 帧（从 0 数），每 4 秒一帧；前两帧加速度算不出来，避开

VERDICTS = ["危险", "值得看", "没事", "看不出"]
CAUSES = ["前车急刹", "加塞", "横穿", "行人或骑车人", "迎面来车", "静止障碍物", "其他"]
VERDICT_HELP = {
    "危险": "照片加数字能看出：不刹车就会撞上；或减速度比 −5 m/s² 还猛",
    "值得看": "有车或人在和我抢路、我在动，但没到“危险”。行人、骑车人进我前面的路，我在动就算；车要我明显减速（比 −1.5 m/s² 猛）才算",
    "没事": "正常驾驶，看不出需要我反应的东西。例：平稳跟着前车减速；斑马线、路口、施工区前的防御性减速；"
          "我停着等、别人从前面正常经过；人或车在隔离栏、安全岛、路缘后面；车从路口横着经过、我只是轻轻减速（不比 −1.5 猛）",
    "看不出": "照片看不清：太黑、被挡住",
}
CAUSE_HELP = {
    "前车急刹": "我车道里前面的车突然减速", "加塞": "旁边车道的车切进我的车道",
    "横穿": "车从侧面横着穿过我要走的路", "行人或骑车人": "人、自行车、摩托车走进我的路（先看是谁：是人或两轮车就选这个）",
    "迎面来车": "对面的车冲我开过来，或在路口转弯冲着我来", "静止障碍物": "停着的车、施工区挡在我的路上", "其他": "上面都不是",
}


def jpeg_b64(img, size) -> str:
    buf = io.BytesIO()
    img.convert("RGB").resize(size).save(buf, format="JPEG", quality=72)
    return base64.b64encode(buf.getvalue()).decode()


def build_tasks(T: dict) -> list[dict]:
    tasks = []
    for scene in sorted(T["scene"].values(), key=lambda s: s["name"]):
        frames = scene_frames(T, scene)
        picks = {p["k"]: p for p in pick_scene(frames, use_path=True, same_dir=True)}
        ks = sorted(set(k for k in UNIFORM_K if k < len(frames)) | set(picks))
        for k in ks:
            p = picks.get(k)
            who = p["who"] if p else None
            a = accel(frames, k)
            tasks.append({
                "id": f"{scene['name']}_{k + 1:02d}", "scene": scene["name"], "frame": k + 1,
                "t": round(frames[k]["t"], 2),
                "v": None if frames[k]["v"] is None else round(frames[k]["v"], 2),
                "a": None if a is None else round(a, 2),
                "source": ("均匀" if k in UNIFORM_K else "") + ("+规则" if p and k in UNIFORM_K else ("规则" if p else "")),
                "rule": None if p is None else {"rule": p["rule"], "value": round(p["value"], 2),
                                                "who": who["cat"] if who else None},
                "boxed": who is not None,
                "_frames": (frames, k, who),
            })
    return tasks


def main():
    T = load()
    tasks = build_tasks(T)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page_tasks = []
    for t in tasks:
        frames, k, who = t.pop("_frames")
        main_img = draw_box(T, frames[k], who)
        prev_img = draw_box(T, frames[k - 1], None) if k > 0 else None
        next_img = draw_box(T, frames[k + 1], None) if k + 1 < len(frames) else None
        page_tasks.append({
            "id": t["id"], "scene": t["scene"], "frame": t["frame"], "t": t["t"], "v": t["v"], "a": t["a"],
            "boxed": t["boxed"],                                   # 不放 source / rule：标的人看不到规则怎么判的
            "img": jpeg_b64(main_img, (800, 450)),
            "prev": jpeg_b64(prev_img, (400, 225)) if prev_img else None,
            "next": jpeg_b64(next_img, (400, 225)) if next_img else None,
        })
    (OUT_DIR / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    pre = json.loads(PRELABELS.read_text(encoding="utf-8")) if PRELABELS.exists() else {"by": "", "labels": {}}
    data = {"tasks": page_tasks, "verdicts": VERDICTS, "causes": CAUSES, "pre": pre["labels"], "pre_by": pre["by"],
            "verdict_help": VERDICT_HELP, "cause_help": CAUSE_HELP}
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = OUT_DIR / "c3_label.html"
    out.write_text(html, encoding="utf-8")
    n_rule = sum(1 for t in tasks if t["rule"])
    print(f"{len(tasks)} 条（均匀 {sum(1 for t in tasks if '均匀' in t['source'])}，规则挑中 {n_rule}）"
          f" → {out}（{out.stat().st_size / 1e6:.1f} MB）")


if __name__ == "__main__":
    main()
