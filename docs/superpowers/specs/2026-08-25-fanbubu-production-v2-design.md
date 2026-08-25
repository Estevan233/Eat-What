# 饭卜卜生产增强版设计

状态：待用户书面审阅后进入实施。

本规格的权威需求、技术设计和执行清单位于：

- `.trellis/tasks/08-25-fanbubu-production-v2/prd.md`
- `.trellis/tasks/08-25-fanbubu-production-v2/design.md`
- `.trellis/tasks/08-25-fanbubu-production-v2/implement.md`

核心决策：

1. CloudBase 可信 openid + 项目 JWT 完成身份认证；头像昵称是可跳过的主动资料完善，不再误当作微信登录凭证。
2. 菜谱由 60 扩为 120（50 主菜、50 蔬菜、20 主食），严格校验量化食材、步骤、营养、来源和基本熟制安全。
3. 推荐只在高质量分数带内做用户稳定的有界探索，同 request id 幂等，硬忌口永不放宽。
4. 天气采用 QWeather 主源、Open-Meteo 备用、1 小时新鲜缓存、12 小时陈旧兜底和 neutral 末级降级。
5. AI 首版只把自然语言解析为 MealIntent；FastAPI 仍控制候选、过滤、营养、菜谱和写入。AI 不可用时基础推荐照常运行。
6. 生产数据库继续使用 CloudBase HTTP 数据网关，不恢复公网 MySQL；实际部署与微信上传必须另过部署确认闸门。

