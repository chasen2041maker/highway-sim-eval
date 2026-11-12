"""C3 3c：模型回答的解析和校验（不连模型）。"""

from examples.c_review.c3_review import build_prompt, parse_answer


def test_parse_plain_and_fenced_json():
    r = parse_answer('{"verdict": "值得看", "cause": "横穿", "evidence": "左边黑车横穿"}')
    assert r["valid"] and r["verdict"] == "值得看" and r["cause"] == "横穿"
    r = parse_answer('好的：\n```json\n{"verdict": "误挑", "cause": null, "evidence": "工人在安全岛上"}\n```')
    assert r["valid"] and r["verdict"] == "误挑" and r["cause"] is None


def test_reject_words_outside_the_boxes():
    assert not parse_answer('{"verdict": "有点危险", "cause": null}')["valid"]            # 不是格子里的词
    assert not parse_answer('{"verdict": "值得看", "cause": "左侧车辆切入"}')["valid"]    # 原因不是格子里的词
    assert not parse_answer('{"verdict": "值得看", "cause": null}')["valid"]             # 值得看必须给原因
    assert not parse_answer("我觉得不危险")["valid"]                                       # 没有 JSON


def test_extra_cause_on_misfire_is_dropped():
    r = parse_answer('{"verdict": "误挑", "cause": "其他", "evidence": "x"}')
    assert r["valid"] and r["cause"] is None


def test_prompt_lists_every_box_and_has_no_conclusion():
    p = build_prompt("这是第 6.4 秒。")
    for word in ("危险", "值得看", "误挑", "看不出", "前车急刹", "加塞", "横穿", "行人或骑车人", "迎面来车", "静止障碍物", "其他"):
        assert word in p
    assert "规则会挑错" in p and "这是第 6.4 秒。" in p
    assert "可能不准" in p and "这些数字可信" not in p          # TTC 是规则的估计，不能说成可信
    assert "我停着等，别人从我前面正常经过" in p                 # 3d：值得看 / 误挑的边界例子
