-- SQL 第 4 课 练习 9：少写一把钥匙会怎样
-- 和练习 8 一样，只是 ON 里只按题号对，没按出题种子对；数一数拼出来多少行
SELECT count(*) AS n
FROM results r
JOIN questions q
  ON r.question = q.question                              -- 只有一把钥匙
WHERE r.question_seed = 2 AND r.question = 545
