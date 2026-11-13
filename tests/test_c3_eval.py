"""C3 3e：对答案的计数（不连模型、不读 nuScenes）。"""

from examples.c_review.c3_eval import model_scores, rule_scores


def task(i, scene="s", frame=1, source="均匀", rule=None):
    return {"id": i, "scene": scene, "frame": frame, "source": source, "rule": rule}


def test_rule_recall_by_frame_and_by_event():
    # 答案：s 第 13 帧值得看（均匀）；规则挑中 s 第 14 帧（也值得看）→ 逐帧 0 / 1，按事件 1 / 1；精确 1 / 1
    tasks = [task("a", frame=13), task("b", frame=14, source="规则", rule={"rule": "急刹"}), task("c", frame=5)]
    labels = {"a": {"verdict": "值得看"}, "b": {"verdict": "值得看"}, "c": {"verdict": "没事"}}
    r = rule_scores(tasks, labels)
    assert len(r["pos"]) == 1 and len(r["by_frame"]) == 0 and len(r["by_event"]) == 1
    assert len(r["picks"]) == 1 and len(r["right"]) == 1


def test_model_scores_counts():
    tasks = [task(x) for x in "abcd"]
    labels = {"a": {"verdict": "值得看", "cause": "横穿"}, "b": {"verdict": "值得看", "cause": "行人或骑车人"},
              "c": {"verdict": "没事", "cause": None}, "d": {"verdict": "没事", "cause": None}}
    rows = [{"id": "a", "valid": True, "verdict": "值得看", "cause": "横穿", "tokens": 10},
            {"id": "b", "valid": True, "verdict": "没事", "cause": None, "tokens": 10},          # 漏了
            {"id": "c", "valid": True, "verdict": "危险", "cause": "其他", "tokens": 10},        # 多报
            {"id": "d", "valid": False, "verdict": None, "cause": None, "tokens": 10}]           # 无效算错
    s = model_scores(tasks, labels, rows)
    assert (s["n"], s["right"], s["tp"], s["fp"], s["fn"], s["cause_ok"], s["invalid"]) == (4, 1, 1, 1, 1, 1, 1)
    assert s["conf"]["没事"]["无效"] == 1 and s["conf"]["值得看"]["没事"] == 1 and s["tokens"] == 40
