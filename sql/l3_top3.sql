-- SQL 第 3 课 练习 7：分班排名——每种路况各自排名次，只留前 3
-- PARTITION BY：按路况分成 4 个“班”，每个班里各排各的
-- QUALIFY：对排名结果再筛（DuckDB 的写法；别的数据库要套一层子查询，第 5 课讲）
SELECT noise_y_m, delay_s, predict_s, confirm_frames, accel,
       count_if(missed) * 10 + count_if(false_brake) AS cost,
       rank() OVER (PARTITION BY noise_y_m, delay_s
                    ORDER BY count_if(missed) * 10 + count_if(false_brake)) AS rk
FROM grid
WHERE question_seed = 2
GROUP BY noise_y_m, delay_s, predict_s, confirm_frames, accel
QUALIFY rk <= 3
ORDER BY noise_y_m, delay_s, rk
