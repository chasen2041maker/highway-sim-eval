-- SQL 第 4 课 练习 10：LEFT JOIN 找“没跑的题”（完整性检查）
-- 题目表放左边：每道题都留下；结果表里对不上的，结果那几格是 NULL（空）
-- 下面查“往前看 2.0 秒”这组设置——我们根本没跑过这组；把 2.0 改成 1.0 再跑一次对比
SELECT count(*) AS missing_n
FROM questions q
LEFT JOIN results r
  ON r.question_seed = q.question_seed
 AND r.question = q.question
 AND r.predict_s = 2.0 AND r.confirm_frames = 1 AND r.accel           -- 只拿这一组设置的结果来对
 AND r.noise_y_m = 0 AND r.delay_s = 0
WHERE r.question IS NULL                                               -- 对不上 = 这道题在这组设置下没有结果
