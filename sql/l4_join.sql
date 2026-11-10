-- SQL 第 4 课 练习 8：把结果表和题目表拼起来（JOIN）
-- results 里只有题号，没有题目参数；按“出题种子 + 题号”这两把钥匙，去 questions 里把参数找回来
SELECT r.question, r.noise_y_m, r.delay_s, r.predict_s, r.confirm_frames, r.accel, r.missed,   -- r. 开头的来自结果表
       q.gap_m, q.ego_speed_mps, q.cut_speed_mps          -- q. 开头的来自题目表
FROM results r                                            -- r 是结果表的简称
JOIN questions q                                          -- q 是题目表的简称
  ON r.question_seed = q.question_seed                    -- 钥匙 1：哪一批
 AND r.question = q.question                              -- 钥匙 2：第几道题
WHERE r.question_seed = 2 AND r.question = 545
ORDER BY r.noise_y_m, r.delay_s, r.predict_s, r.confirm_frames, r.accel
LIMIT 6
