"""C3 第 3d 步：分开做（三个角色）和 3c 一个模型做，同一批片段各跑一遍，比对错和花费。

三个角色：
  看图员：只给照片（规则挑中的东西用橙色框框出来）+ “看框里的”，不给规则的结论 → 描述画面，不判危险。
  读数员：不给照片，只给测量值 + 规则挑中的原因 → 判断规则的推论站不站得住（比如我停着时 TTC 的假设不成立）。
  裁判：  照片 + 两份报告 + 3b 的两把尺子 → 填答题卡（同 3c 的 JSON，同样校验）。报告冲突时看照片核对。
先用 3c 那 3 条调参题跑通（不算真分数，真分数在 3e）。

运行（项目根目录，conda activate py310；.env 里填好 key、地址、模型）：
    python -m examples.c_review.c3_review_multi
"""

from __future__ import annotations

from examples.c_review.c3_pick import scene_frames
from examples.c_review.c3_review import (CASES, CAUSE_RULE, CAUSES, VERDICTS, build_prompt, facts, parse_answer,
                                         picked, review_photo)
from examples.c_review.c3_vlm_hello import ask
from examples.c_review.llm_client import call, config
from examples.c_review.nuscenes_tables import load


def ask_text(model: str, prompt: str) -> tuple[str, dict]:
    """只有文字、没有图的提问（读数员用）。"""
    out = call("/chat/completions", {"model": model, "messages": [{"role": "user", "content": prompt}]})
    return out["choices"][0]["message"]["content"], out.get("usage", {})


# ---------- 三个角色的提示词 ----------

def looker_prompt(p) -> str:
    """看图员：只说看哪儿（照片上的橙色框），不说规则为什么挑它、不说 TTC。
    第一版用“前方 14.8 米、右边 1.2 米”指路，看图员两次找错东西（模型看照片估不准距离），所以改成画框。"""
    if p and p["who"] is not None:
        target = "重点看照片上橙色框框出来的那个东西，"
    else:
        target = "看整条路面，"
    return (f"这是一辆车前视摄像头的照片。{target}用 3–4 句中文描述你看到的：那是什么；在干嘛（停着、在动、往哪个方向动）；"
            "它在不在我要走的路上；它和我之间有没有东西挡着（隔离栏、安全岛、路缘）；路上还有没有别的车或人在和我抢路。"
            "只描述看到的，不要判断危不危险。")


def reader_prompt(fact_text: str, picked: bool = True) -> str:
    """读数员：没有照片，只看测量值和规则的理由，判断规则的推论站不站得住。随机抽查的帧没有规则的理由，就只说测量值。"""
    if not picked:
        return f"""你是读数员，看不到照片，只看下面这些测量值（可信）。这一刻是随机抽查的，不是规则挑出来的。

{fact_text}

用 2–3 句中文回答：我在不在动；有没有明显减速（比 −1 m/s² 猛）或急刹（比 −3 m/s² 猛）；单看这些数，这一刻像不像发生了需要我反应的事。"""
    return f"""你是读数员，看不到照片，只看下面这些数。车速、加速度、对象的位置是测量值，可信；TTC 是规则估出来的，
它假设“我在追它”：它在我前面、和我同方向走、我比它快。

{fact_text}

用 2–3 句中文回答：规则挑中这一刻的理由站不站得住？先写结论“成立 / 不成立 / 说不准”，再说为什么（比如 TTC 的假设在这些数下成不成立、急刹是不是真的）。"""


def judge_prompt(looker: str, reader: str, picked: bool = True) -> str:
    """裁判：照片 + 两份报告 + 两把尺子，填答题卡。"""
    head = ("你是裁判，在审一段自动驾驶路采数据里被规则挑出来的一刻。规则会挑错。" if picked
            else "你是裁判，在审一段自动驾驶路采数据里随机抽查的一刻（不是规则挑的）。")
    verdicts = "\n".join(f"- {k}：{v}" for k, v in VERDICTS.items())
    causes = "\n".join(f"- {k}：{v}" for k, v in CAUSES.items())
    return f"""{head}
下面有两份报告，还有那一刻的前视照片。两份报告说法冲突时，看照片核对。

看图员（看了照片，没看规则的数）：
{looker}

读数员（看了测量值，没看照片）：
{reader}

请用两把尺子判断，只能从下面的格子里选：
尺子一，值不值（必选一个）：
{verdicts}
尺子二，原因（只有选了“危险”或“值得看”才填，否则填 null）：
{causes}
{CAUSE_RULE}

只回答一个 JSON，不要别的字：
{{"verdict": "尺子一里的一个词", "cause": "尺子二里的一个词或 null", "evidence": "一句话：你依据什么这么判"}}"""


def tokens(*usages) -> int:
    return sum(u.get("prompt_tokens", 0) + u.get("completion_tokens", 0) for u in usages)


def main():
    _, _, model = config()
    if not model:
        print("先在 .env 里填 OPENAI_MODEL")
        return
    T = load()
    scenes = {s["name"]: s for s in T["scene"].values()}
    score = {"一个模型": [0, 0], "分开做": [0, 0]}          # [对了几条, 一共多少 token]
    for name, frame_no, (use_path, same_dir), (h_verdict, h_cause) in CASES:
        frames = scene_frames(T, scenes[name])
        k = frame_no - 1
        photo = review_photo(T, frames, k, use_path, same_dir)
        fact_text = facts(frames, k, use_path, same_dir)
        p = picked(frames, k, use_path, same_dir)
        print(f"\n{name} 第 {frame_no} 帧    人的答案：{h_verdict}{' / ' + h_cause if h_cause else ''}")

        # 3c：一个模型
        text, u = ask(model, build_prompt(fact_text), photo)
        r = parse_answer(text)
        ok = r["valid"] and r["verdict"] == h_verdict and r["cause"] == h_cause
        score["一个模型"][0] += ok
        score["一个模型"][1] += tokens(u)
        shown = f"{r['verdict']}{' / ' + r['cause'] if r['cause'] else ''}" if r["valid"] else f"无效（{r['why']}）"
        print(f"  一个模型：{shown}  {'✓' if ok else '✗'}  （{tokens(u)} token）")

        # 3d：分开做
        look, u1 = ask(model, looker_prompt(p), photo)
        read, u2 = ask_text(model, reader_prompt(fact_text))
        text, u3 = ask(model, judge_prompt(look.strip(), read.strip()), photo)
        r = parse_answer(text)
        ok = r["valid"] and r["verdict"] == h_verdict and r["cause"] == h_cause
        score["分开做"][0] += ok
        score["分开做"][1] += tokens(u1, u2, u3)
        shown = f"{r['verdict']}{' / ' + r['cause'] if r['cause'] else ''}" if r["valid"] else f"无效（{r['why']}）"
        print(f"  分开做：  {shown}  {'✓' if ok else '✗'}  （{tokens(u1, u2, u3)} token）")
        print(f"    看图员：{' '.join(look.split())[:160]}")
        print(f"    读数员：{' '.join(read.split())[:160]}")
        if r["valid"]:
            print(f"    裁判依据：{r['evidence']}")

    print(f"\n{'':6}{'对了几条':>8}{'一共多少 token':>16}")
    for k, (right, tok) in score.items():
        print(f"{k:6}{right:>6} / {len(CASES)}{tok:>14}")


if __name__ == "__main__":
    main()
