"""C3 第 3c 步：让模型凭数据说话、按 JSON 回答“这个片段放哪一格、为什么”。

一次调用 = 一个片段：前视照片 + 程序算好的事实（车速、减速度、规则为什么挑中它）+ 3b 定的两把尺子。
模型只能从格子里选，按固定的 JSON 回答；代码再检查它选的是不是格子里的词（不是就记“无效”）。
3a 的三条规矩都用上：问题里不塞结论，只给量出来的事实；允许答“没事”“看不出”；回答拿格子校验。
第一版说“这些数字可信”、“危险”定义成“TTC < 1.5”，模型就信了规则在我停着时算错的 TTC 1.0，把 scene-1100 判成危险
（deepseek-flash 1 / 3）。现在分开说：测量值可信，TTC 是规则的估计、可能不准。
注意：这 3 条只是调参题，别改提示词改到它们全对；真正的分数在 3e 用另一批片段考（B4 第 5 步）。
3d 发现“值得看 / 误挑”的边界没写清（我停着让它过，裁判当成“减速”），补了边界例子——这是澄清标注规范，人标的时候也守这条。
3e 起“误挑”改叫“没事”（3e 有随机抽查的帧，不是规则挑的，谈不上挑错），并按本人 11-13 定的规范补上：
平稳跟车减速、防御性减速（斑马线、路口、施工区前）都算没事。随机抽查的帧，提示词里说“随机抽查”、照片不画框。
规范第 2 版（3e 第一轮之后，本人 11-13 选 B）：第一轮 5 条多报都是“路口有车横着过 + 我轻轻减速”，而答案卷里
行人横穿（−0.24）算值得看、车横穿（−0.53）算没事——规矩没写出来。v2：行人、骑车人进我前面的路，我在动就算值得看；
车要我明显减速（比 −1.5 猛）才算。同时修了第一轮的小毛病：随机抽查的帧不再提 TTC 和对象位置。
注意：看着这 51 条的错改的规范，这 51 条从此是调参题，v2 在它们上面的分数不算数；真分数要换新数据（nuScenes 全量）。
v2 在这 51 条上：5 条多报都没了，冒出 1 条新的（scene-0655 第 13 帧，很远处的行人）——“走进我前面的路”没写多远。
下一版要补“几秒内会走到我的路上”，但不在这 51 条上再调了，留到换新数据时一起改。

先拿 3 个人看过照片、答案已知的片段试（2d）：
  scene-0103 第 14 帧：急刹 −3.24，左边黑车横穿 → 值得看 / 横穿
  scene-0061 第 15 帧：直尺版 TTC 2.7 挑中安全岛上的工人 → 没事（规则挑错了）
  scene-1100 第 4 帧：我停着，TTC 1.0 挑中对面拐过来的车 → 没事（规则挑错了）

运行（项目根目录，conda activate py310；.env 里填好 key、地址、模型）：
    python -m examples.c_review.c3_review
"""

from __future__ import annotations

import json
import re

from PIL import Image

from examples.c_review.c3_pick import accel, draw_box, pick_scene, scene_frames
from examples.c_review.c3_scene_view import ZH
from examples.c_review.c3_vlm_hello import ask
from examples.c_review.llm_client import config
from examples.c_review.nuscenes_tables import ROOT as NUSCENES, load

# ---------- 3b 定的两把尺子 ----------
VERDICTS = {
    "危险": "照片加测量值能看出：不刹车就会撞上；或者减速度比 −5 m/s² 还猛（紧急制动）。TTC 只作参考",
    "值得看": "有车或人在和我抢路、我在动，但没到“危险”。人和车分开看：行人、骑车人走进我前面的路，只要我在动就算，不管减了多少；车横着经过或切进来，要我明显为它减速（比 −1.5 m/s² 猛）才算",
    "没事": "正常驾驶，照片里看不出需要我反应的东西（规则挑中的话，就是规则挑错了）。边界例子：我停着等，别人从我前面正常经过；"
            "人或车在隔离栏、安全岛、路缘后面；平稳跟着前车减速；斑马线、路口、施工区前的防御性减速；"
            "车从路口横着经过、我只是轻轻减速（不比 −1.5 m/s² 猛）",
    "看不出": "照片看不清：太黑、被挡住",
}
CAUSES = {
    "前车急刹": "我车道里前面的车突然减速",
    "加塞": "旁边车道的车切进我的车道",
    "横穿": "车从侧面横着穿过我要走的路",
    "行人或骑车人": "人、自行车、摩托车走进我的路",
    "迎面来车": "对面的车冲我开过来，或在路口转弯冲着我来",
    "静止障碍物": "停着的车、施工区挡在我的路上",
    "其他": "上面都不是",
}
WHY_PICKED = ("规则把这一刻挑出来，是因为它“可能”值得看；规则会挑错，你要看照片判断。\n"
              "照片上的橙色框，框出的是规则挑中的那个东西（因为急刹挑中时没有框）。")
WHY_RANDOM = "这一刻是随机抽查的，不是规则挑出来的，照片上没有框。你要看照片判断。"
TRUST_PICKED = "车速、加速度、对象的位置是测量值，可信；TTC 是规则按“我在追它”估出来的，可能不准（比如我停着、它从旁边经过时），要对照照片判断。"
TRUST_RANDOM = "车速、加速度是测量值，可信。"
CAUSE_RULE = "先看是谁，再看怎么动：只要是人、自行车、摩托车，一律选“行人或骑车人”；是汽车，才按它怎么动来分。"

# ---------- 3 个答案已知的片段（场景、第几帧、当时用哪版规则挑中的、人的答案） ----------
CASES = [
    ("scene-0103", 14, (True, True), ("值得看", "横穿")),
    ("scene-0061", 15, (False, False), ("没事", None)),
    ("scene-1100", 4, (True, False), ("没事", None)),
]


def facts(frames, k, use_path, same_dir) -> str:
    """程序算好的事实，写成几行字。只写量出来的数，不写“危险”“为什么”这种结论。"""
    f = frames[k]
    a = accel(frames, k)
    if a is not None:
        a = round(a, 2) + 0.0                             # 免得打印出 −0.00
    lines = [f"这是第 {f['t']:.2f} 秒。",
             f"我的车速：{f['v']:.1f} m/s。" if f["v"] is not None else "我的车速：不知道。",
             f"我的加速度：{a:.2f} m/s²（负数 = 在减速）。" if a is not None else "我的加速度：不知道。"]
    for p in pick_scene(frames, use_path, same_dir):
        if p["k"] != k:
            continue
        if p["rule"] == "TTC":
            o = p["who"]
            side = f"左边 {o['ey']:.1f} 米" if o["ey"] >= 0 else f"右边 {-o['ey']:.1f} 米"
            lines.append(f"规则挑中它的原因：规则估的 TTC {p['value']:.1f} 秒（按“我在追它”估的，可能不准），"
                         f"对象是{ZH.get(o['cat'], o['cat'])}，在我前方 {o['ex']:.1f} 米、{side}。")
        else:
            lines.append(f"规则挑中它的原因：急刹，减速度 {p['value']:.2f} m/s²。")
    return "\n".join(lines)


def build_prompt(fact_text: str, picked: bool = True) -> str:
    verdicts = "\n".join(f"- {k}：{v}" for k, v in VERDICTS.items())
    causes = "\n".join(f"- {k}：{v}" for k, v in CAUSES.items())
    trust = TRUST_PICKED if picked else TRUST_RANDOM
    return f"""你在审一段自动驾驶路采数据。下面是一辆车的前视摄像头照片，以及程序给的事实。
{trust}
{WHY_PICKED if picked else WHY_RANDOM}

事实：
{fact_text}

请用两把尺子判断，只能从下面的格子里选：
尺子一，值不值（必选一个）：
{verdicts}
尺子二，原因（只有选了“危险”或“值得看”才填，否则填 null）：
{causes}
{CAUSE_RULE}

只回答一个 JSON，不要别的字：
{{"verdict": "尺子一里的一个词", "cause": "尺子二里的一个词或 null", "evidence": "一句话：照片里看到了什么，让你这么判"}}"""


def parse_answer(text: str) -> dict:
    """从回答里取出 JSON 并校验：verdict 必须是尺子一的词；值得看 / 危险 必须带尺子二的词，其余 cause 必须是 null。
    不合格的记 valid=False 和原因，不硬猜。"""
    m = re.search(r"\{.*\}", text, re.S)                 # 模型有时会包在 ```json ... ``` 里
    if not m:
        return {"valid": False, "why": "回答里没有 JSON"}
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"valid": False, "why": "JSON 格式不对"}
    return check_answer(d)


def check_answer(d: dict) -> dict:
    """校验一张答题卡（3c 从文字里取出的 JSON，或 4b 智能体交卷工具的参数）。"""
    v, c = d.get("verdict"), d.get("cause")
    if c in ("null", "", "无"):
        c = None
    if v not in VERDICTS:
        return {"valid": False, "why": f"verdict 不在格子里：{v}"}
    if v in ("危险", "值得看") and c not in CAUSES:
        return {"valid": False, "why": f"选了 {v} 却没给格子里的原因：{c}"}
    if v in ("没事", "看不出") and c is not None:
        c = None                                          # 多给的原因不算错，丢掉
    return {"valid": True, "verdict": v, "cause": c, "evidence": d.get("evidence", "")}


def front_photo(T, frame) -> Image.Image:
    return Image.open(NUSCENES / frame["cam"]["filename"]).resize((800, 450))


def picked(frames, k, use_path, same_dir):
    """这一帧被规则挑中的那一条（规则名、数值、对象）；没挑中返回 None。"""
    for p in pick_scene(frames, use_path, same_dir):
        if p["k"] == k:
            return p
    return None


def review_photo(T, frames, k, use_path, same_dir) -> Image.Image:
    """给模型看的照片：把规则挑中的那个东西用橙色框框出来（急刹没有对象，就不画框），缩到 800×450。
    3d 发现：用“前方 14.8 米、右边 1.2 米”指路，模型在照片上估不准距离，会找错东西；框出来就不用估。"""
    p = picked(frames, k, use_path, same_dir)
    return draw_box(T, frames[k], p["who"] if p else None).resize((800, 450))


def main():
    _, _, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    T = load()
    scenes = {s["name"]: s for s in T["scene"].values()}
    right = 0
    for name, frame_no, (use_path, same_dir), (h_verdict, h_cause) in CASES:
        frames = scene_frames(T, scenes[name])
        k = frame_no - 1
        fact_text = facts(frames, k, use_path, same_dir)
        text, u = ask(model, build_prompt(fact_text), review_photo(T, frames, k, use_path, same_dir))
        r = parse_answer(text)
        print(f"\n{name} 第 {frame_no} 帧    人的答案：{h_verdict}{' / ' + h_cause if h_cause else ''}")
        print("  给模型的事实：" + fact_text.replace("\n", " "))
        if not r["valid"]:
            print(f"  模型：无效（{r['why']}）  原话：{text.strip()[:200]}")
            continue
        ok = r["verdict"] == h_verdict and r["cause"] == h_cause
        right += ok
        print(f"  模型：{r['verdict']}{' / ' + r['cause'] if r['cause'] else ''}    {'✓' if ok else '✗'}"
              f"    （token：{u.get('prompt_tokens', '?')} + {u.get('completion_tokens', '?')}）")
        print(f"  依据：{r['evidence']}")
    print(f"\n两把尺子都对：{right} / {len(CASES)}")


if __name__ == "__main__":
    main()
