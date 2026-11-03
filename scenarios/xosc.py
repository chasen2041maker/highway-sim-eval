"""读 OpenSCENARIO（.xosc）题目文件，变成我们自己的场景（现在只支持前车急刹 → LeadBrake）。

.xosc 是 XML：一层套一层的标签。用 Python 自带的 xml.etree 读，find 后面写“路径”找标签：
  ".//Init//Private[@entityRef='hero']" = 任意深处的 Init 里面、entityRef 属性是 hero 的 Private 标签。
文件里的值可以是数字，也可以是 "$参数名"（引用 ParameterDeclarations 里的参数）。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scenarios.lead_brake import LeadBrake


def read_params(root: ET.Element, overrides: dict | None = None) -> dict[str, float]:
    """文件开头 ParameterDeclarations 里的参数 → {名字: 数}；overrides 可以临时改（不改文件）。"""
    params = {p.get("name"): float(p.get("value")) for p in root.find("ParameterDeclarations")}
    for name, value in (overrides or {}).items():
        if name not in params:
            raise KeyError(f"文件里没有参数 {name}，有的是 {sorted(params)}")
        params[name] = float(value)
    return params


def value_of(element: ET.Element, attr: str, params: dict[str, float]) -> float:
    """取标签的一个属性：写的是 "$gap" 就去参数表里查，写的是数字就直接转成数。"""
    text = element.get(attr)
    return params[text[1:]] if text.startswith("$") else float(text)


def load_lead_brake(path: str | Path, **overrides) -> LeadBrake:
    """读前车急刹的 .xosc → LeadBrake（四个数都是前车开始刹车那一刻的）。"""
    root = ET.parse(path).getroot()
    p = read_params(root, overrides)
    trigger = root.find(".//Event[@name='LeadBrakes']//RelativeDistanceCondition")
    brake = root.find(".//Event[@name='LeadBrakes']//SpeedActionDynamics")
    ego_init = root.find(".//Init//Private[@entityRef='hero']//AbsoluteTargetSpeed")
    lead_init = root.find(".//Init//Private[@entityRef='adversary']//AbsoluteTargetSpeed")
    if trigger.get("freespace") != "true" or brake.get("dynamicsDimension") != "rate":
        raise ValueError("要求：触发距离按车头到车尾（freespace）、刹车按每秒减多少（rate）")
    return LeadBrake(
        gap_m=value_of(trigger, "value", p),
        ego_speed_mps=value_of(ego_init, "value", p),
        lead_speed_mps=value_of(lead_init, "value", p),
        lead_decel_mps2=value_of(brake, "value", p),
    )
