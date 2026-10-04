# 附近店铺参考：地图选点与附近搜索（10-01 独立任务）

## 目标与状态
在外食推荐结果页提供"看看附近"可选辅助：用户选点后展示附近店铺参考，帮助决策"去哪吃"。
2026-10-01：腾讯位置服务核验完成（research/tencent-lbs-verification.md）；用户确认三项边界——
入口在外食推荐结果页（`pages/today/today.vue` external-result 区块，today.vue:207）、选点仅当次锚点不落库、
先写 PRD 不动代码。小程序后台 wx.chooseLocation 接口审核中；腾讯位置服务 KEY 已申请。
权威源码 /root/miniapp-trellis；本任务为 09-30-dining-decision-jev Phase 3 拆分，R1–R5/R8 继承母任务口径。

## 已确认需求
- R1：入口为外食推荐结果页的"看看附近"辅助操作；不新增地图首页，不改变主推荐流程。
- R2：可选辅助、独立降级。不授权位置、接口未开通/审核中、搜索失败时，基础推荐不受影响；
  降级时给出明确提示而非报错或空白。
- R3：腾讯位置服务核验结论（详见 research/tencent-lbs-verification.md）：
  map 组件展示免费；**个人开发者地点搜索配额 200 次/日、并发 5（2025-04-17 起收紧，旧"1万/日"口径失效）**，
  逆地址解析/关键词提示 6,000 次/日；当前用户量级够用，但必须配缓存节流（锚点网格化 + TTL 15-30 分钟
  + 同会话复用）；商业授权条款（自行申请 KEY + 直接或间接收益，5 万/年）当前无变现大概率不适用，留痕备查。
- R4：地图结果不代表全部餐厅；无可靠菜单时只给点单方向，不声称某店必售某菜、实时营业或可配送。
- R5：复用个人店＋菜记忆，允许没有地图 POI 的食堂、小店参与私人推荐；不建设公开商家库。
- R6（隐私）：选点坐标仅作当次搜索锚点，不落库、不追踪、不保存常去地点；服务端不记录用户标识与坐标的绑定关系。
- R7（安全）：腾讯 LBS KEY 只存云托管环境变量，由后端代理调用；小程序代码包与前端请求均不出现 KEY。
- R8（坐标系）：定位、选点、搜索、展示全链路统一 gcj02。现有 `useLocation.ts` 用 wgs84，接入前必须修正
  （map 组件官方要求 gcj02，混用会偏移数百米）。
- R9（合规状态机）：wx.chooseLocation 审核通过前提审；审核期间开发与体验版预览不受限，真机调用未开通
  接口会 fail，按 R2 降级。若审核被拒，转插件路线（appid wx76a9a06e5b4e693e）并重新评估商业授权敞口。

## 现状证据
- 入口锚点：外食结果区块在 `miniapp/src/pages/today/today.vue:207-221`（external-result / external-place /
  external-disclaimer），today.vue:414 已有"拒绝定位不阻断、可手填城市"的降级先例可复用。
- 定位能力：`miniapp/src/composables/useLocation.ts` 已封装 uni.getLocation + 拒绝授权引导
  （permissionDenied / requestPermission），但坐标系为 wgs84，违反 R8。
- 权限声明：`miniapp/src/manifest.json` mp-weixin 段已有 `permission.scope.userLocation`
  （desc：获取当地天气给出饮食推荐）与 `requiredPrivateInfos: ["getLocation"]`；
  接入选点需追加 "chooseLocation"，并更新用户隐私保护指引中的位置用途说明（选点/附近搜索）。
- 后端模式：specialty_ai（core/config.py:50-57）已有"可配置开关＋超时＋缓存降级"模式，搜索代理沿用；
  云托管部署，PRD R8 沿用 CloudBase HTTP Repository，不引入公网 MySQL。
- 接口审核：wx.chooseLocation 2026-10-01 提交，状态审核中；审核结果决定选点路线（R9）。
- KEY 状态：腾讯位置服务开发者与 KEY 已申请（2026-10-01），待配置进云托管环境变量。

## 阶段化路线
- Phase 0 接口审核：✅ 2026-10-02 审核通过，路线 A（原生 wx.chooseLocation）生效。
- Phase 1 后端代理：✅ 2026-10-02 代码完成并部署上线（app/services/tencent_lbs_client.py +
  api/v1/nearby.py，网格缓存/陈旧降级/开关，测试 4 项）；云托管版本已切全量流量。
  线上验证（guest-login 直连）：/health 正常、附近搜索返回真实 POI（北京西站 20 家，
  距离 16-437m 合理）、网格缓存命中（坐标微差同键）、radius/lat 越界 422、无 token 401、
  keyword=咖啡 返回咖啡店。
- Phase 2 前端链路：✅ 2026-10-02 代码完成（today.vue 入口+列表+降级、api/nearby.ts、
  manifest chooseLocation 声明、useLocation gcj02 修正）；type-check 通过。
- Phase 3 提审发布：待用户 MP 后台更新隐私指引位置用途，build:mp-weixin 后体验版真机验证
  （坐标系 R8、降级链路 R2、AC8 检查清单）再提审。
- Phase 3 提审发布：审核通过为前提（R9）；提交前核对隐私指引、requiredPrivateInfos、体验版真机
  验证坐标系（R8）与降级链路（R2）。

## 验收标准
- AC1：不授权位置、不选点、未开通接口三种状态下，原有家庭/外食推荐均正常（R1/R2）。
- AC2：选点失败、搜索超时/失败时页面有明确提示并可回到推荐结果，无白屏无卡死（R2）。
- AC3：小程序代码包、前端网络请求、版本库中均检索不到 LBS KEY（R7）。
- AC4：服务端不存储用户标识与选点坐标的绑定；请求日志脱敏（R6）。
- AC5：全链路 gcj02：同一位置下定位点、选点结果、搜索锚点、展示偏差肉眼不可辨（R8）。
- AC6：店铺列表标注"地图结果，不代表全部餐厅"口径；无来源不声称店内有具体菜品（R4/R5/母任务 AC7）。
- AC7：搜索代理具备开关关闭能力：开关关闭时前端入口隐藏或提示，不影响其他功能（母任务 R8）。
- AC8：提审前检查清单：接口已开通、隐私指引已更新、requiredPrivateInfos 已声明、体验版真机验证通过（R9）。

## 不做
多地图聚合、商家入驻/评论、配送承诺、菜单抓取、常去地点保存、长期位置轨迹、路线规划/导航、
付费或变现功能（避免触发商业授权重评估）、独立地图首页。

## 待决策
- wx.chooseLocation 审核结果：通过→路线 A（原生）；被拒→路线 B（腾讯选点插件）并重评商业授权敞口（R9）。
- 结果展示形态：先店铺列表（成本低、满足 R2）；map 组件 markers 展示作为二期可选项。
- 搜索关键词策略：固定餐饮分类 vs 按当次推荐菜匹配 POI 分类（ Phase 1 先用固定"美食/餐厅"分类跑通）。
- 搜索半径与排序默认值（建议半径 1000m、按距离排序，联调时按实际密度调）。
