# 技术设计

权威执行计划：`docs/superpowers/plans/2026-08-17-product-modes-mysql.md`。

数据流：

```text
today.vue
  -> Pinia decision context
  -> cook: POST /daily/recommend -> existing recommender/meal builder
  -> eat_out: POST /dining/recommend -> deterministic external dining service
  -> DiningMemory API -> exact normalized shop+dish private preference
  -> FastAPI -> SQLModel/Alembic -> CloudBase MySQL
```

关键边界：外食实体不复用 `Food/Recipe`；旧自炊响应保持稳定；家庭 MVP 仅有 audience/party_size，不收集未授权成员敏感档案；坐标只在请求内使用且不落库。
