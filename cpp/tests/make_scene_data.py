"""生成 cpp/tests/scene_data.hpp：A6 第 3 步那段假路况（sim/fake_traffic.py），
加上 Python 版 MultiTracker（max_misses 10 和 3）每帧每张纸条的编号和位置，
让 C++ 版跑同一段路况、逐帧对答案。

运行（在仓库根目录）：python cpp/tests/make_scene_data.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ads.tracking import MultiTracker  # noqa: E402
from sim.fake_traffic import make_scene  # noqa: E402


def tracks_rows(scene, max_misses):
    mt = MultiTracker(max_misses=max_misses)
    rows = []
    for k, det in enumerate(scene.detections):
        for t in mt.step(det):
            rows.append((k, t.id, float(t.xy[0]), float(t.xy[1])))
    return rows


def main():
    scene = make_scene()
    dets = [(k, float(x), float(y)) for k, det in enumerate(scene.detections) for x, y in det]
    out = [
        "// 自动生成，别手改：python cpp/tests/make_scene_data.py",
        "// A6 第 3 步那段假路况（sim/fake_traffic.py，seed 12）：51 帧，每帧雷达框中心（顺序是乱的），",
        "// 以及 Python 版 MultiTracker 每帧处理完以后手里的纸条（编号、位置），max_misses 10 和 3 各一份。",
        "#pragma once",
        "",
        f"constexpr int kSceneFrames = {len(scene.detections)};",
        "",
        "struct DetRow { int frame; double x; double y; };",
        "struct TrackRow { int frame; int id; double x; double y; };",
        "",
        "constexpr DetRow kSceneDets[] = {",
    ]
    out += [f"    {{{k}, {x!r}, {y!r}}}," for k, x, y in dets]
    out.append("};")
    for mm in (10, 3):
        out += ["", f"constexpr TrackRow kPythonTracksMaxMisses{mm}[] = {{"]
        out += [f"    {{{k}, {i}, {x!r}, {y!r}}}," for k, i, x, y in tracks_rows(scene, mm)]
        out.append("};")
    path = ROOT / "cpp" / "tests" / "scene_data.hpp"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {path}: {len(dets)} boxes")


if __name__ == "__main__":
    main()
