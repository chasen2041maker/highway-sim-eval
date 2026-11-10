-- SQL 第 3 课 练习 6：三种排名，看“并列”时有什么不同
-- 第二批题、干净路况：16 种考生设置各自的代价（漏刹 × 10 + 误刹），再排名
SELECT predict_s, confirm_frames, accel,
       count_if(missed) * 10 + count_if(false_brake) AS cost,
       row_number() OVER (ORDER BY count_if(missed) * 10 + count_if(false_brake)) AS rn,    -- 1,2,3,4… 一人一个号，并列也硬分先后
       rank()       OVER (ORDER BY count_if(missed) * 10 + count_if(false_brake)) AS rk,    -- 并列同名次，后面跳号：1,1,3
       dense_rank() OVER (ORDER BY count_if(missed) * 10 + count_if(false_brake)) AS drk    -- 并列同名次，后面不跳：1,1,2
FROM grid
WHERE question_seed = 2 AND noise_y_m = 0 AND delay_s = 0
GROUP BY predict_s, confirm_frames, accel
ORDER BY cost, predict_s, confirm_frames, accel
