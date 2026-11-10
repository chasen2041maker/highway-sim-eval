-- SQL 第 5 课 练习 12：CASE WHEN——SQL 里的 if / else
-- 把“会切进来的题”按开始切那一刻的车距分成 4 档，看每档漏刹的比例（第二批，64 组旋钮都算上）
SELECT CASE WHEN q.gap_m < 8  THEN '1 很近 <8m'               -- 车距 < 8 米
            WHEN q.gap_m < 15 THEN '2 近 8-15m'               -- 前面没中的里面，< 15 米
            WHEN q.gap_m < 22 THEN '3 中 15-22m'
            ELSE                   '4 远 >=22m'                -- 上面都不是
       END AS gap_band,
       count(DISTINCT question) AS questions_n,               -- 这一档有几道题
       count(*) AS runs_n,                                     -- 一共考了几次（题数 × 64）
       count_if(r.missed) AS missed_n,
       round(100.0 * count_if(r.missed) / count(*), 1) AS missed_pct   -- 漏刹占几成（百分比）
FROM results r
JOIN questions q USING (question_seed, question)              -- 第 4 课：拼回题目参数
WHERE question_seed = 2 AND q.comes_in                        -- 第二批、会切进来的题
GROUP BY gap_band
ORDER BY gap_band
