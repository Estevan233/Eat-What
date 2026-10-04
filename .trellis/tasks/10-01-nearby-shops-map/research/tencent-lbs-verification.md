# 腾讯位置服务核验报告（2026-10-01）

PRD R3 要求：地图展示、地点搜索、微信审核、商业授权分别核验。以下为逐项结论，全部附来源。

## 1. 地图展示（map 组件）— 免费可用

- 基础地图展示**免费**，无需购买任何能力；个性化地图样式自 2023-06-29 起付费，本需求不需要。
- 官方建议注册腾讯位置服务 KEY 经 `subkey` 传入（来源：[map 组件文档](https://developers.weixin.qq.com/miniprogram/dev/component/map.html)）。
- **坐标系坑（已发现）**：map 组件使用 gcj02（火星坐标），而现有 `miniapp/src/composables/useLocation.ts` 调 `uni.getLocation({ type: 'wgs84' })`。接入地图/选点前必须统一为 gcj02，否则定位点会偏移数百米。

## 2. 选点能力 — 两条路线，都有明确门槛

### 路线 A：原生 wx.chooseLocation（推荐先试）

- 需在小程序管理后台「开发-开发管理-接口设置」**自助开通**，官方口径"暂只针对具备与地理位置强相关的使用场景的小程序开放"；代码提审环节检测，未开通将被拦截（来源：[wx.chooseLocation 文档](https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.chooseLocation.html)）。
- 需在 `app.json` 声明：`permission.scope.userLocation`（**项目已有**，manifest.json mp-weixin 段）+ `requiredPrivateInfos` 追加 `"chooseLocation"`（当前只有 `["getLocation"]`）。uni-app 在 `miniapp/src/manifest.json` 的 mp-weixin 节点改。
- 不依赖腾讯 LBS KEY，不触发第 4 节的商业授权条款。
- **待实测**：饭卜卜（appid wx59c5620b7a894f8e）的后台能否直接开通该接口——取决于小程序类目与场景说明，餐饮推荐场景通过概率高，但必须以后台实测为准。

### 路线 B：腾讯位置服务地图选点插件（退路）

- 插件 appid `wx76a9a06e5b4e693e`，在 MP 后台「设置-第三方服务-插件管理」添加即可，**不需要开通原生位置接口**（绕开路线 A 的开通审核）。
- 功能更强：关键词搜索、POI 分类（最多 3 个）、主子点，返回 name/address/经纬度/省市区（来源：[插件文档](https://lbs.qq.com/miniProgram/plugin/pluginGuide/locationPicker)）。
- **必须申请腾讯 LBS KEY** → 与第 4 节商业授权条款产生关联，需留痕评估。

## 3. 地点搜索（WebService API）— 免费但个人配额收紧，必须缓存节流

> **2025-04-17 配额调整（重要变更）**：腾讯 2025-03-18 公告调整个人开发者部分接口额度
> （来源：[配额调整公告](https://lbs.qq.com/news/lbs/DeveloperInterfaceQuotaUpdated)、
> [配额说明页 2025-11-13 更新](https://lbs.qq.com/dev/console/quotaImprove)）。
> 此前"1 万次/日/接口"的口径**已失效**，以下为现行个人开发者配额（每日PV/并发，账号下全部 KEY 共享）：

| 接口 | 个人开发者 | 企业-技术公益 | 用途 |
|------|-----------|--------------|------|
| **地点搜索** place/v1/search | **200 / 5** | 2,000 / 5 | 附近店铺主接口，最紧 |
| 周边推荐 place/v1/explore | 200 / 5 | 2,000 / 5 | 备选（按分类推荐附近 POI） |
| POI 详情 place/v1/detail | 200 / 5 | 2,000 / 5 | 点开单店详情时才用 |
| 逆地址解析 geocoder | 6,000 / 5 | 30 万 / 100 | 选点结果转地址，充足 |
| 关键词输入提示 suggestion | 6,000 / 5 | 30 万 / 100 | 搜索框联想，充足 |
| 坐标转换 coord/translate | 6,000 / 5 | 300 万 / 100 | 坐标系兜底 |

- 需注册开发者 + 创建 KEY；小程序需把 `apis.map.qq.com` 加入 request 合法域名（来源：[小程序调用指南](https://lbs.qq.com/service/webService/webServiceGuide/miniprogram)）。
- **200 次/日对饭卜卜够用但无余量**（主力用户外食事件 251 次/周期，即使每次点"看看附近"也约 10-20 次/日），前提是配缓存节流：锚点取 ~3 位小数网格（约 100-200m）+ 分类 + 半径作缓存键，TTL 15-30 分钟；同会话同锚点重复点击直接复用；配额耗尽错误按 R2 降级。
- 多边形搜索对个人开发者额度为 0（不可用）；不要按 ID 逐店查 POI 详情（200/日 会快速耗尽），列表数据够用。
- **安全与架构**：KEY 放小程序前端会被抓包盗用配额。应走后端（CloudBase 云托管）代理持有 KEY——与现有架构和 PRD R8（不引入公网 MySQL、沿用 CloudBase HTTP Repository）一致。

## 4. 商业授权 — 条款存在且有收紧趋势，当前大概率不适用，需留痕

- 配额说明页明确开发者身份三档：个人开发者（学习/非组织使用）／企业-技术公益（180 天测试额度，**上线后须办商业授权**）／商业授权。个人账户不允许迁移 KEY 到企业账户。
- map 组件文档原文："若开发者使用通过 LBS 开放平台自行申请的服务账号，在小程序连接并调用位置服务产品用于商业行为（政府公共事务及公益组织事务除外），腾讯位置服务有权收取商业授权费"。
- 价格：基础版 **50,000 元/年**、高级版 **70,000 元/年**；判定标准为"以商业化目的使用并直接或间接获取收益"（来源：[商业授权 FAQ](https://mapapi.qq.com/web/lbs/wechatOfficialAccount/wxArticles/newFaq/authorization_faq.html)、[lbs.qq.com 报价页](https://lbs.qq.com/sem/consult/?fromgeoarticle=page1140)）。
- **对饭卜卜的适用性**：当前无付费/广告/导流等收益行为，按"直接或间接获取收益"口径大概率不构成商业行为；但这是法务口径而非技术结论，且"有权收取"意味着腾讯保留裁量权。若走原生 wx.chooseLocation + 后端代理搜索，KEY 仅服务端持有、调用量小，风险敞口最小。
- **红线**：若未来小程序增加任何变现功能，需重新评估本条款。

## 结论

| 核验项 | 结论 |
|--------|------|
| 地图展示 | ✅ 免费，无门槛 |
| 选点 | ⚠️ 两条路线均可；原生接口需后台实测开通；插件需 LBS KEY |
| 地点搜索 | ⚠️ 个人配额 200 次/日（2025-04-17 收紧），够用但须缓存节流；必须后端代理保 KEY |
| 商业授权 | ⚠️ 条款存在（5万/年），当前无收益大概率不适用，留痕备查 |

**建议路线**：原生 wx.chooseLocation（无 KEY、无授权条款牵连）→ 后端代理 WebService 地点搜索（云托管持 KEY）→ map 组件展示附近结果。全部满足 R2（地图不可用时基础推荐独立可用）：选点失败/未授权时降级为现有推荐。

## 待办（进入方案阶段前）

1. MP 后台实测开通 wx.chooseLocation（5 分钟，无代码）。
2. manifest.json 追加 requiredPrivateInfos；统一 useLocation 坐标系为 gcj02。
3. 云托管新增地点搜索代理端点（KEY 入环境变量，复用 specialty_ai 的开关/超时/缓存降级模式）。

## 5. 接口变更监测（2026-10-01 复查）

- **wx.chooseLocation 无废弃公告**：现行有效，规则仍按 2022 调整（接口开通 + requiredPrivateInfos 声明 + 提审拦截）。
- **新接口 wx.choosePoi**（[文档](https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.choosePoi.html)）：
  POI 列表选点，支持模糊到市 + 精确混选；同样需接口开通与声明。注意其返回坐标标注
  "gcj02（**即将废弃**）"——微信坐标系口径酝酿变更，接入后需跟踪；本任务暂用 chooseLocation。
- **配额政策趋势**：2025-04-17 个人配额已收紧一次（旧"1 万次/日"口径失效），且"未办商业授权将停止服务"
  的表述只针对企业/非公益身份；个人开发者身份与无变现现状仍是合规基线，但政策风向偏收紧，
  设计时保持代理层可整体关闭（母任务 R8 开关原则）。
