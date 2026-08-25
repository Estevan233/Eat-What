# 实施计划

全程 TDD：每一阶段先写失败测试，再写最小实现，局部通过后才进入下一阶段。除用户明确批准的部署闸门外，不自动上传小程序或更新 Cloud Run。

## 0. 基线与契约

- [ ] 记录干净工作树、分支、后端/前端基线结果和当前 60 道菜谱摘要。
- [ ] 为新增 API/WeatherData/MealIntent 写契约测试，确认旧请求和旧缓存兼容。
- [ ] 再次确认生产路径不引用 `DATABASE_URL`，HTTP Repository 测试保持全绿。

验证：`git status --short`，后端全量 pytest，前端 test/type-check/lint。

## 1. 微信身份与资料完善

- [ ] 后端先写 profile account PATCH 的鉴权、校验、隔离和 Repository 双后端测试。
- [ ] 实现 UserRead 的计算型 `profile_complete` 与公开资料更新服务。
- [ ] 前端先写登录完成判定、跳过、本地标记、头像上传和状态同步测试。
- [ ] 实现资料完善组件并复用到登录后与 Mine 页；不改 cloud-login 的可信身份主路径。
- [ ] 模拟头像上传失败、保存 401/5xx、跳过和二次登录。

回滚点：只关闭资料 UI；后端新增接口是加法变更。

## 2. 120 道菜谱

- [ ] 先把验证器测试改为 120、50/50/20 和新增安全/质量规则，观察当前 60 数据按预期失败。
- [ ] 审计现有 60 条，修复模板化、食材与步骤不一致项。
- [ ] 从现有 Food 中选取并编写 60 条新增菜谱，逐批运行验证器；建立 review manifest。
- [ ] 验证幂等导入、recipe-ready catalog 数量、菜谱 API 与历史快照兼容。
- [ ] 抽查至少 20 道新增菜谱：食材能覆盖步骤、时间可执行、肉蛋水产有熟制、营养口径为每份估算。

回滚点：保留旧数据版本，不执行清表或破坏性迁移。

## 3. 推荐个性化与轮换

- [ ] 写稳定种子、同请求幂等、跨用户差异、60% 换餐、收藏/历史偏好和硬过滤优先测试。
- [ ] 实现 PreferenceSnapshot 与质量带内的确定性加权探索。
- [ ] 将 AI MealIntent 的硬/软约束接入评分器，但先使用手工构造输入测试。
- [ ] 跑个人/家庭、自己做/外食、极端忌口和 CloudBase HTTP Repository 回归。

回滚点：通过引擎版本/开关回到现有 `rules_v4` 选择器。

## 4. QWeather 双源天气

- [ ] 写 QWeather/高德响应映射、配置成对校验、超时、fallback、fresh/stale/neutral 四级路径测试，并断言生产默认不调用 Open-Meteo。
- [ ] 提取 WeatherProvider 边界并实现 WeatherService；控制串行时间预算。
- [ ] 扩展 WeatherData 与前端 Badge/缓存逻辑，验证旧缓存反序列化。
- [ ] 在本地 mock 后，用 Cloud Run WebShell 分别执行 QWeather 与高德连通性/时延诊断；Open-Meteo 只做可选对照；凭据只来自环境变量。

回滚点：移除 QWeather 配置自动使用高德；移除两者配置自动使用 stale/neutral；WeatherData 新字段保持兼容。

## 5. AI 用餐意图

- [ ] 先做 CloudBase 成长计划、Token、模型组和具体模型预检；把结果记录到任务 research。
- [ ] 写流式文本收集、JSON fence 清理、schema 校验、超时和禁用回退测试。
- [ ] 实现 Today 紧凑输入、标签复核与 MealIntent 提交；前端不保存任何模型密钥。
- [ ] 后端验证并应用 MealIntent，测试 AI 不可绕过硬过滤或写入伪造营养。
- [ ] 预检不通过则保持发布开关关闭，仍完成降级验收。

回滚点：关闭 `VITE_AI_MEAL_INTENT_ENABLED`，后端可选字段继续兼容。

## 6. 全量验证与部署准备

- [ ] 后端：`pytest`、Ruff、mypy、菜谱校验、CloudBase Repository 契约、Docker build/run `/health`。
- [ ] 前端：Vitest、ESLint、vue-tsc、H5 与 mp-weixin 生产构建。
- [ ] 微信开发者工具：登录/跳过/保存资料、授权/拒绝定位、连续换餐、菜谱、收藏、AI 成功/失败。
- [ ] 真机至少一台完成同一主链路；记录 Cloud Run request id、天气 source 和响应时延，不记录秘密。
- [ ] 输出 Cloud Run 环境变量清单、数据导入步骤、上线/回滚清单和版本说明。
- [ ] 在执行 Cloud Run 部署或微信上传前，单独展示影响面、测试证据、环境变量和回滚方案，等待用户确认。

## 完成门槛

- 自动化全绿不等于全链路跑通；必须同时有 Cloud Run WebShell、开发者工具模拟器和真机证据。
- 任一真实链路无法验证时，报告“本地完成/线上待验收”，不得使用“已经上线可用”之类的魔法咒语糊弄过去。
