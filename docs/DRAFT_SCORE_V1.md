# draft_score_v1

`draft_score_v1` 分为基础数据构建和英雄推荐两个阶段。

## 第一阶段：构建基础数据

运行：

```bash
dota-build-v1 \
  --matches-dir data/raw/ranked_matches_260802_260825 \
  --output data/derived/draft_score_v1.sqlite3
```

如果需要覆盖已有数据库：

```bash
dota-build-v1 \
  --matches-dir data/raw/ranked_matches_260802_260825 \
  --output data/derived/draft_score_v1.sqlite3 \
  --overwrite
```

脚本按 `batch_*.json` 顺序逐批读取比赛，每次只在内存中保留一个批次。
没有 `avg_rank_tier` 或字段不完整的比赛不会进入分段统计。

输出使用 SQLite，包含以下表：

- `heroes`：英雄 ID 和名称。
- `base_stats`：每个分段、每个英雄的出场次数、胜场数和胜率。
- `synergy_matrix`：英雄与队友组合时的出场次数、胜场数和胜率。
- `counter_matrix`：英雄面对敌方英雄时的出场次数、胜场数和胜率。
- `metadata`：数据来源、生成时间和比赛数量。

`synergy_matrix[A, B]` 表示英雄 A 和英雄 B 同队时，A 所在队伍的胜率。
这个矩阵是对称的。

`counter_matrix[A, B]` 表示英雄 A 面对英雄 B 时，A 所在队伍的胜率。
这个矩阵是有方向的。

每个矩阵单元格都保留 `appearances`、`wins` 和 `win_rate`，后续版本可以在此基础上增加最小样本量、贝叶斯平滑或时间衰减。

## 第二阶段：计算推荐

计算公式：

```text
score = alpha * base_score
      + beta  * sum(counter(candidate, enemy))
      + gamma * sum(synergy(candidate, ally))
      + delta * proficiency(candidate)
```

其中：

```text
counter(candidate, enemy)
    = matchup_win_rate(candidate, enemy) - base_win_rate(candidate)

synergy(candidate, ally)
    = teammate_win_rate(candidate, ally) - base_win_rate(candidate)

proficiency(candidate)
    = -1（不会）、0（还行）、1（绝活）
```

如果组合没有比赛数据，该组合的增量按 `0` 处理。

推荐 Top 10：

```bash
dota-score-v1 \
  --data data/derived/draft_score_v1.sqlite3 \
  --rank Archon \
  --allies 1 2 \
  --enemies 3 4 \
  --alpha 1 \
  --beta 1 \
  --gamma 1 \
  --delta 0.05 \
  --proficiency 5=1 10=-1 \
  --top-k 10
```

只计算一个候选英雄：

```bash
dota-score-v1 \
  --data data/derived/draft_score_v1.sqlite3 \
  --rank Archon \
  --hero-id 5 \
  --allies 1 2 \
  --enemies 3 4 \
  --alpha 1 \
  --beta 1 \
  --gamma 1 \
  --delta 0.05 \
  --proficiency 5=1
```

也可以从 Python 调用：

```python
from algorithms.v1 import DraftScoreV1

scorer = DraftScoreV1(
    "data/derived/draft_score_v1.sqlite3",
    "Archon",
)

recommendations = scorer.recommend(
    allies=[1, 2],
    enemies=[3, 4],
    alpha=1.0,
    beta=1.0,
    gamma=1.0,
    delta=0.05,
    hero_proficiencies={5: 1, 10: -1},
    top_k=10,
)
```

## 分段

- `Herald`：10-15
- `Guardian`：20-25
- `Crusader`：30-35
- `Archon`：40-45
- `Legend`：50-55
- `Ancient`：60-65
- `Divine`：70-75
- `Immortal`：80

## V1 限制

- 使用原始胜率，没有样本量平滑。
- 所有历史比赛权重相同，没有时间衰减。
- 不考虑先后手、版本和阵容功能完整性。
- `score` 是排序分数，不是最终预测胜率，数值可能小于 `0` 或大于 `1`。
