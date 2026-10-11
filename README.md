# highway-sim-eval

面向驾驶策略的**闭环仿真评测工具**，基于 [HighwayEnv](https://github.com/Farama-Foundation/HighwayEnv)。

它做三件事：在同一组场景里批量运行策略，计算安全和效率指标，自动挑出失败案例。然后用它比较规则策略和强化学习策略。

## 要回答的问题

- 同一组场景下，哪种策略更安全、更快？
- 策略在什么情况下会失败，失败前发生了什么？
- 改完策略以后，是真的变好了，还是只是这次的路况更容易？

## 计划

项目分两部分。

### 第一部分：从零实现的传统模块化智驾栈（`ads/`）

自己的简化世界（多车道直路 + 他车），不依赖 HighwayEnv。

- [ ] 车辆运动学模型（自行车模型）
- [ ] 纵向控制：PID 速度控制
- [ ] 横向控制：Pure Pursuit、Stanley
- [ ] 参考线与 Frenet 坐标
- [ ] 世界：多车道道路、他车（匀速 / IDM）、碰撞检测
- [ ] 感知与预测（简化）：他车状态 + 匀速预测
- [ ] 行为决策：有限状态机（巡航、跟车、变道）
- [ ] 轨迹规划：Frenet 撒点 + 多项式轨迹
- [ ] 轨迹评价：代价函数 + 碰撞检查
- [ ] 闭环整合与场景：慢车挡路、前车急刹、邻车加塞

### 第二部分：闭环仿真评测

- [x] HighwayEnv 环境入口与检查脚本（`sim_env.py`、`check_env.py`）
- [ ] 评测器：批量场景与种子，碰撞率、最小 TTC、最小车距、舒适性、通行效率
- [ ] 调参种子与测试种子分开，碰撞率置信区间
- [ ] 同一套评测比较：第一部分的规划器、IDM/MOBIL 规则、DQN
- [ ] 失败库与回归：批量跑出的失败场景存档，每次改动先回归
- [ ] 失败分析报告：指标由程序计算，Agent 只负责分类和说明

## 设计约定

- 第二部分里，只有 `sim_env.py` 直接接触 HighwayEnv。
- 策略只用观察表（obs）决定动作，不读模拟器内部状态。
- 指标只从运行记录计算。
- 场景配置和随机种子固定，结果可以复现。

## 运行

```powershell
pip install -r requirements.txt      # 已经装好 highway-env 的环境可以跳过
python check_env.py                  # 不开窗口跑 10 步
python check_env.py --show           # 打开窗口看
```

## 目录

```text
ads/              第一部分：传统模块化智驾栈
sim_env.py        HighwayEnv 环境配置与创建
check_env.py      HighwayEnv 环境检查
requirements.txt  依赖（固定版本）
```

## HighwayEnv 场景设置（第二部分）

| 项 | 值 |
| --- | --- |
| 环境 | `highway-fast-v0`，4 车道，20 辆背景车 |
| 时长 | 每局最长 40 秒 |
| 频率 | 物理 5 Hz，决策 1 Hz（一次决策推进 1 秒） |
| 观察 | Kinematics，5 辆车 × [presence, x, y, vx, vy]，单位米、米/秒，不归一化 |
| 动作 | 0 左变道、1 保持、2 右变道、3 加速、4 减速 |

具体数值在 `sim_env.py` 的 `CONFIG` 里。
