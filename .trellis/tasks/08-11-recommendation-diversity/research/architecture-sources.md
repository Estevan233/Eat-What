# 架构研究摘要

## 当前实现证据

- `backend/app/services/recommender.py` 中天气最高 30 分；雨天汤粥 30 分、其他菜 8 分，单维度产生 22 分差距。
- 同文件先截取 `scored[:6]` 再做多样性选择，候选池过早收窄。
- 相同输入使用 `score desc + food.id asc` 固定排序，且没有近期曝光惩罚。
- `backend/app/models/daily_log.py` 对 `(user_id, log_date)` 设唯一约束，一天仅保存一行，刷新会覆盖上一批 `recommended_food_ids_json`。

## 外部参考

- Google 推荐系统课程将推荐拆成候选生成、评分、重排三个阶段；新鲜度和多样性适合在最终重排阶段处理：
  - https://developers.google.com/machine-learning/recommendation/overview/types
  - https://developers.google.com/machine-learning/recommendation/dnn/re-ranking
- OpenAI Agents SDK 支持基于 Python 类型/Pydantic 的结构化工具输入；未来可以约束 Agent 只返回候选菜品 ID，而不是允许其凭空生成菜品：
  - https://openai.github.io/openai-agents-python/tools/
  - https://openai.github.io/openai-agents-python/agents/#output-types

## 结论

当前问题不是“随机性不够”，而是评分尺度失衡、候选池提前截断、缺少曝光历史三者叠加。修复应保持硬过滤的确定性，将 Agent 预留在规则评分和最终安全重排之间。
