"""A3：PID 速度控制，在 A1 的自行车模型上跑。"""
from ads.control import PID
from ads.vehicle import VehicleState, step

TARGET_MPS = 10.0  # 目标车速
DT_S = 0.1  # 每帧 0.1 秒
DURATION_S = 10.0  # 一共开 10 秒
HILL_MPS2 = -0.5  # 坡道往后拽的力：0 = 平路，-0.5 = 上坡

def run(pid: PID) -> list[float]:
    state = VehicleState()
    speeds = [state.speed_mps]
    for _ in range(round(DURATION_S / DT_S)):
        error = TARGET_MPS - state.speed_mps          # 1. 看差距
        accel = pid.update(error,DT_S)         # 2. PID 算加速度      
        state = step(state, accel + HILL_MPS2, 0.0, DT_S)          # 3. 车开 0.1 秒（方向盘 0，直行）
        speeds.append(state.speed_mps)       # 4. 记下车速，下一圈再看差距
    return speeds

def main() -> None:
    speeds = run(PID(kp=1.0, ki=0.2))
    for t in (1, 2, 5, 10):
        print(f"{t:>2} 秒：车速 {speeds[round(t / DT_S)]:.2f} m/s")
    print(f"最高车速：{max(speeds):.2f} m/s")


if __name__ == "__main__":
    main()