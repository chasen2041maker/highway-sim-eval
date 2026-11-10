-- SQL 第 5 课 练习 11：WITH——把一条长 SQL 拆成几步，每一步起个名字
-- 和第 3 课练习 7 一样（每种路况的第一名），但不用 DuckDB 才有的 QUALIFY：别的数据库都这么写
WITH per_group AS (                          -- 第 1 步：每种路况 × 每种考生设置，算代价
    SELECT noise_y_m, delay_s, predict_s, confirm_frames, accel,
           count_if(missed) * 10 + count_if(false_brake) AS cost
    FROM results
    WHERE question_seed = 2
    GROUP BY noise_y_m, delay_s, predict_s, confirm_frames, accel
),
ranked AS (                                  -- 第 2 步：在第 1 步的结果上，每种路况各排名次
    SELECT *,
           rank() OVER (PARTITION BY noise_y_m, delay_s ORDER BY cost) AS rk
    FROM per_group
)
SELECT *                                     -- 第 3 步：只留第一名
FROM ranked
WHERE rk = 1
ORDER BY noise_y_m, delay_s
