-- SQL 第 5 课 练习 13（面试常考：和上一行比 / 环比）：lag() 取“上一行”的值
-- 第二批、干净路况、1 帧、匀加速：往前看 0 → 0.5 → 1.0 → 1.5 秒，每多看 0.5 秒，漏刹少了几次、误刹多了几次
WITH by_predict AS (
    SELECT predict_s,
           count_if(missed)      AS missed_n,
           count_if(false_brake) AS false_n
    FROM results
    WHERE question_seed = 2 AND noise_y_m = 0 AND delay_s = 0 AND confirm_frames = 1 AND accel
    GROUP BY predict_s
)
SELECT predict_s, missed_n, false_n,
       missed_n - lag(missed_n) OVER (ORDER BY predict_s) AS missed_change,   -- 比上一行（少看 0.5 秒）多了几次漏刹
       false_n  - lag(false_n)  OVER (ORDER BY predict_s) AS false_change     -- 比上一行多了几次误刹
FROM by_predict
ORDER BY predict_s
