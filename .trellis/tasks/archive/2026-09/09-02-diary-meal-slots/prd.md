# PRD: 餐食日记与三餐化大修（含评审修正版）

## 目标
1. 原「历史记录」原地改造为「餐食日记」：按天分组（早/中/晚/外食四段）、搜索、编辑、删除、AI 一句话自记、连续打卡徽章
2. "就吃这个"三餐化：早/中/晚各存一套，recommendation upsert、manual 追加（一餐可多条）
3. 收藏升级：搜索、备注编辑、自定义收藏（无关联菜谱降级展示）
4. 外食 AI 本地特色菜：按城市生成 3-5 道真实当地菜，缓存 24h，静默降级，标注"AI 推荐·仅供参考"
5. 外食小本仅加搜索，表结构不动

## 已确认决策
- 自记用 AI 一句话解析（两段式：parse 不落库 → 前端修正 → manual 落库）
- 早餐仅记录层三餐化，推荐算法结构不变
- 餐食日记与外食小本双入口并存；dining_memories 不进日记（日记外食段来自 daily_logs.source=manual + shop_name）

## 验收标准
- 后端 pytest 全绿（含新增：三餐独立保存、upsert 覆盖语义、manual 追加、parse 降级、收藏搜索/自定义、merge 兼容 meal_slot）
- history API 返回 meal_slot/source/shop_name/note/streak_days，支持 ?query=
- choose 接受 meal_slot，cook/eat_out 统一
- 前端 type-check/lint/test 通过，构建 mp-weixin 成功
- wechat-devtools 模拟器逐页验证无 console 错误
- CloudBase 部署后 /health 正常，推送 GitHub main

## 关键约束
- 数据库：daily_logs 删 (user_id, log_date) 唯一约束 → 普通索引 (user_id, log_date, meal_slot, source)；新增 meal_slot/source/shop_name/note；favorites.food_id 可空 + custom_name/note
- log_date 一律前端传；PATCH 权限按 source 区分（recommendation 快照不可改菜品）
- AI 失败降级不阻塞核心记录功能；输入限长 100 字
